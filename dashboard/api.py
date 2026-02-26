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
from shared.data_manager import get_notes_dir  # noqa: E402
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


# ── Notes CRUD ────────────────────────────────────────────────────────────────

_NOTE_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9 _-]*\.md$')


def _validate_note_filename(filename: str) -> str | None:
    """Return an error string if the filename is invalid, else None."""
    if not filename:
        return "Filename is required."
    if "/" in filename or "\\" in filename or ".." in filename:
        return "Filename must not contain path separators."
    if not _NOTE_NAME_PATTERN.match(filename):
        return "Filename must end in .md and contain only letters, digits, spaces, hyphens, or underscores."
    return None


def _resolve_note_path(project_name: str, filename: str):
    """
    Resolve (notes_dir, note_path, error) for a project note.
    Returns (notes_dir, note_path, None) on success or (None, None, error_string).
    """
    registry = _registry()
    if project_name not in registry.projects:
        return None, None, f"Project '{project_name}' not found."

    project = registry.projects[project_name]
    notes_dir = get_notes_dir(project_name, project.scope)
    notes_dir.mkdir(parents=True, exist_ok=True)

    err = _validate_note_filename(filename)
    if err:
        return None, None, err

    note_path = notes_dir / filename
    # Security: ensure resolved path is still inside notes_dir
    try:
        note_path.resolve().relative_to(notes_dir.resolve())
    except ValueError:
        return None, None, "Invalid file path."

    return notes_dir, note_path, None


def _note_to_dict(note_path: Path) -> dict:
    stat = note_path.stat()
    return {
        "filename": note_path.name,
        "modified": stat.st_mtime,
        "size_bytes": stat.st_size,
    }


def list_notes(project_name: str) -> dict:
    registry = _registry()
    if project_name not in registry.projects:
        return {"error": f"Project '{project_name}' not found."}, 404

    project = registry.projects[project_name]
    notes_dir = get_notes_dir(project_name, project.scope)
    notes_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(notes_dir.glob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True)
    return {"notes": [_note_to_dict(f) for f in files]}


def get_note(project_name: str, filename: str) -> dict:
    notes_dir, note_path, err = _resolve_note_path(project_name, filename)
    if err:
        return {"error": err}, 404

    if not note_path.exists():
        return {"error": f"Note '{filename}' not found."}, 404

    return {
        "filename": filename,
        "content": note_path.read_text(encoding="utf-8"),
        "modified": note_path.stat().st_mtime,
    }


def create_note(project_name: str, data: dict) -> tuple:
    name = (data.get("name") or "").strip()
    if not name:
        return {"error": "Note name is required."}, 400

    # Ensure .md extension
    if not name.endswith(".md"):
        name = name + ".md"

    notes_dir, note_path, err = _resolve_note_path(project_name, name)
    if err:
        return {"error": err}, 400

    if note_path.exists():
        return {"error": f"Note '{name}' already exists."}, 409

    content = data.get("content", "")
    note_path.write_text(content, encoding="utf-8")
    _regenerate_dashboard()
    return {**_note_to_dict(note_path), "content": content}, 201


def update_note(project_name: str, filename: str, data: dict) -> tuple:
    notes_dir, note_path, err = _resolve_note_path(project_name, filename)
    if err:
        return {"error": err}, 400

    if not note_path.exists():
        return {"error": f"Note '{filename}' not found."}, 404

    content = data.get("content", "")
    note_path.write_text(content, encoding="utf-8")
    _regenerate_dashboard()
    return {**_note_to_dict(note_path), "content": content}, 200


def delete_note(project_name: str, filename: str) -> tuple:
    notes_dir, note_path, err = _resolve_note_path(project_name, filename)
    if err:
        return {"error": err}, 400

    if not note_path.exists():
        return {"error": f"Note '{filename}' not found."}, 404

    note_path.unlink()
    _regenerate_dashboard()
    return {"deleted": filename}, 200


def improve_note_api(project_name: str, filename: str) -> tuple:
    """Call NoteBot to improve a note's content. Returns suggested text without saving."""
    notes_dir, note_path, err = _resolve_note_path(project_name, filename)
    if err:
        return {"error": err}, 400

    if not note_path.exists():
        return {"error": f"Note '{filename}' not found."}, 404

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return {"error": "ANTHROPIC_API_KEY is not set."}, 400

    try:
        NOTEBOT_PKG = REPO_ROOT / "bots" / "notebot"
        if str(NOTEBOT_PKG) not in sys.path:
            sys.path.insert(0, str(NOTEBOT_PKG))
        from notebot.analyzer import improve_note  # noqa: E402
        content = note_path.read_text(encoding="utf-8")
        improved = improve_note(content, title=filename)
        return {"improved": improved}, 200
    except Exception as e:
        return {"error": f"Improve failed: {e}"}, 500
