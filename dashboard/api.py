"""REST API handlers for project CRUD operations."""

import os
import re
import sys
from pathlib import Path

# Ensure orchestrator and shared packages are importable
REPO_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR_PKG = REPO_ROOT / "bots" / "orchestrator"
SHARED_PKG = REPO_ROOT / "shared"
for _pkg in (ORCHESTRATOR_PKG, SHARED_PKG):
    if str(_pkg) not in sys.path:
        sys.path.insert(0, str(_pkg))

from orchestrator.registry import ProjectRegistry  # noqa: E402
from generate_data import DashboardDataGenerator  # noqa: E402
from shared.bot_registry import all_bots as _all_bots  # noqa: E402
from shared.models import ProjectScope  # noqa: E402

NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')


def _registry():
    return ProjectRegistry()


def _regenerate_dashboard():
    """Regenerate static JSON files after a mutation."""
    gen = DashboardDataGenerator()
    gen.run()


def _validate_name(name):
    if not name or not NAME_PATTERN.match(name):
        return "Name must start with a letter/digit and contain only letters, digits, hyphens, underscores."
    return None


def _project_to_dict(project):
    """Convert a Project to a JSON-safe dict, excluding tokens."""
    d = project.to_dict()
    d.pop("gitlab_token", None)
    d.pop("github_token", None)
    return d


def list_projects():
    registry = _registry()
    projects = registry.list_projects()
    return {"projects": [_project_to_dict(p) for p in projects]}


def get_project(name):
    registry = _registry()
    if name not in registry.projects:
        return None
    return _project_to_dict(registry.projects[name])


def _parse_scope(data):
    try:
        return ProjectScope(data.get("scope", "team"))
    except ValueError:
        return ProjectScope.TEAM


def _resolve_path(path_str, scope):
    """Resolve and validate a project path. Personal projects may omit path."""
    path_str = (path_str or "").strip()
    if not path_str:
        if scope == ProjectScope.PERSONAL:
            return Path.home(), None  # default to home dir
        return None, "Path is required for team projects."
    path_obj = Path(path_str).expanduser()
    if not path_obj.exists():
        return None, f"Path does not exist: {path_str}"
    return path_obj, None


def create_project(data):
    name = data.get("name", "").strip()
    err = _validate_name(name)
    if err:
        return {"error": err}, 400

    scope = _parse_scope(data)
    path_obj, err = _resolve_path(data.get("path", ""), scope)
    if err:
        return {"error": err}, 400

    registry = _registry()
    if name in registry.projects:
        return {"error": f"Project '{name}' already exists."}, 409

    registry.add_project(
        name=name,
        path=str(path_obj),
        description=data.get("description", ""),
        language=data.get("language", "python"),
        scope=scope,
        gitlab_project_id=data.get("gitlab_project_id") or None,
        gitlab_url=data.get("gitlab_url") or None,
        github_repo=data.get("github_repo") or None,
        notes_dir=data.get("notes_dir") or None,
        task_file=data.get("task_file") or None,
        habit_file=data.get("habit_file") or None,
    )

    _regenerate_dashboard()
    return _project_to_dict(registry.projects[name]), 201


def update_project(name, data):
    registry = _registry()
    if name not in registry.projects:
        return {"error": f"Project '{name}' not found."}, 404

    project = registry.projects[name]

    # Update allowed fields
    if "path" in data and data["path"]:
        new_path, err = _resolve_path(data["path"], project.scope)
        if err:
            return {"error": err}, 400
        project.path = new_path

    if "description" in data:
        project.description = data["description"]
    if "language" in data:
        project.language = data["language"]
    if "gitlab_project_id" in data:
        project.gitlab_project_id = data["gitlab_project_id"] or None
    if "gitlab_url" in data:
        project.gitlab_url = data["gitlab_url"] or None
    if "github_repo" in data:
        project.github_repo = data["github_repo"] or None
    if "notes_dir" in data:
        project.notes_dir = data["notes_dir"] or None
    if "task_file" in data:
        project.task_file = data["task_file"] or None
    if "habit_file" in data:
        project.habit_file = data["habit_file"] or None

    registry._save()
    _regenerate_dashboard()
    return _project_to_dict(project), 200


def delete_project(name):
    registry = _registry()
    if name not in registry.projects:
        return {"error": f"Project '{name}' not found."}, 404

    registry.remove_project(name)
    _regenerate_dashboard()
    return {"deleted": name}, 200


def generate_reports(name, data):
    """Run selected bots for a project and return results."""
    from orchestrator.bot_invoker import invoke_bot

    registry = _registry()
    if name not in registry.projects:
        return {"error": f"Project '{name}' not found."}, 404

    project = registry.projects[name]

    bots = data.get("bots", [])
    if not bots:
        return {"error": "No bots selected."}, 400

    valid_bots = set(_all_bots())
    invalid = [b for b in bots if b not in valid_bots]
    if invalid:
        return {"error": f"Unknown bots: {', '.join(invalid)}"}, 400

    # Pre-flight: check API key before spending time on git reads
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {
            "error": "ANTHROPIC_API_KEY is not set. Add it to your .env file and restart the server."
        }, 400

    since = data.get("since") or None
    until = data.get("until") or None
    pmbot_mode = data.get("pmbot_mode", "analyze")

    results = {}
    completed = 0
    failed = 0

    for bot_name in bots:
        try:
            kwargs = {"bot_name": bot_name, "project": project}
            if bot_name == "gitbot":
                kwargs["since"] = since
                kwargs["until"] = until
            elif bot_name == "pmbot":
                kwargs["pmbot_mode"] = pmbot_mode

            result = invoke_bot(**kwargs)
            status_str = str(result.status.value) if hasattr(result.status, 'value') else str(result.status)
            results[bot_name] = {
                "status": status_str,
                "summary": result.summary,
            }
            if status_str in ("error", "failed"):
                failed += 1
            else:
                completed += 1
        except Exception as e:
            results[bot_name] = {"status": "error", "summary": str(e)}
            failed += 1

    _regenerate_dashboard()
    return {"results": results, "completed": completed, "failed": failed}, 200
