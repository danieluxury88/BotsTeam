"""REST API handlers for project CRUD operations."""

import re
import sys
from pathlib import Path

# Ensure orchestrator package is importable
REPO_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR_PKG = REPO_ROOT / "bots" / "orchestrator"
if str(ORCHESTRATOR_PKG) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_PKG))

from orchestrator.registry import ProjectRegistry  # noqa: E402
from generate_data import DashboardDataGenerator  # noqa: E402

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


def create_project(data):
    name = data.get("name", "").strip()
    err = _validate_name(name)
    if err:
        return {"error": err}, 400

    path = data.get("path", "").strip()
    if not path:
        return {"error": "Path is required."}, 400

    path_obj = Path(path).expanduser()
    if not path_obj.exists():
        return {"error": f"Path does not exist: {path}"}, 400

    registry = _registry()
    if name in registry.projects:
        return {"error": f"Project '{name}' already exists."}, 409

    registry.add_project(
        name=name,
        path=str(path_obj),
        description=data.get("description", ""),
        language=data.get("language", "python"),
        gitlab_project_id=data.get("gitlab_project_id") or None,
        gitlab_url=data.get("gitlab_url") or None,
        github_repo=data.get("github_repo") or None,
    )

    _regenerate_dashboard()
    return _project_to_dict(registry.projects[name]), 201


def update_project(name, data):
    registry = _registry()
    if name not in registry.projects:
        return {"error": f"Project '{name}' not found."}, 404

    project = registry.projects[name]

    # Update allowed fields
    if "path" in data:
        new_path = Path(data["path"]).expanduser()
        if not new_path.exists():
            return {"error": f"Path does not exist: {data['path']}"}, 400
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
