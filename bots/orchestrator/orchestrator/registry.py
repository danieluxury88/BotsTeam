"""Project registry — maintains list of known projects."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from shared.models import ProjectScope


@dataclass
class Project:
    """A registered project."""
    name: str
    path: Path
    description: str = ""
    language: str = "python"
    scope: ProjectScope = ProjectScope.TEAM

    # Team integrations (optional)
    gitlab_project_id: str | None = None
    gitlab_url: str | None = None
    gitlab_token: str | None = None
    github_repo: str | None = None
    github_token: str | None = None

    # Personal bot data sources (optional — for journalbot, taskbot, habitbot)
    notes_dir: str | None = None    # journalbot: path to markdown notes directory
    task_file: str | None = None    # taskbot: path to task list file or directory
    habit_file: str | None = None   # habitbot: path to habit log file (CSV or markdown)

    @property
    def is_personal(self) -> bool:
        return self.scope == ProjectScope.PERSONAL

    def has_gitlab(self) -> bool:
        """Check if this project has GitLab integration configured."""
        return self.gitlab_project_id is not None

    def has_github(self) -> bool:
        """Check if this project has GitHub integration configured."""
        return self.github_repo is not None

    def get_gitlab_token(self) -> str | None:
        """Get GitLab token (per-project or fall back to global env)."""
        if self.gitlab_token:
            return self.gitlab_token
        from shared.config import Config
        try:
            return Config.gitlab_token()
        except EnvironmentError:
            return None

    def get_gitlab_url(self) -> str:
        """Get GitLab URL (per-project or fall back to global env)."""
        if self.gitlab_url:
            return self.gitlab_url
        from shared.config import Config
        return Config.gitlab_url()

    def get_github_token(self) -> str | None:
        """Get GitHub token (per-project or fall back to global env)."""
        if self.github_token:
            return self.github_token
        from shared.config import Config
        try:
            return Config.github_token()
        except EnvironmentError:
            return None

    def get_github_base_url(self) -> str:
        """Get GitHub API base URL (per-project or fall back to global env)."""
        from shared.config import Config
        return Config.github_base_url()

    def get_data_dir(self) -> Path:
        """Get the data directory for this project (scope-aware)."""
        from shared.data_manager import get_project_data_dir
        return get_project_data_dir(self.name, self.scope)

    def get_reports_dir(self, bot: str | None = None) -> Path:
        """Get the reports directory for this project (scope-aware)."""
        from shared.data_manager import get_reports_dir
        return get_reports_dir(self.name, bot, self.scope)  # type: ignore

    def get_report_path(self, bot: str, variant: str = "latest") -> Path:
        """Get the path to a bot report (scope-aware)."""
        from shared.data_manager import get_report_path
        return get_report_path(self.name, bot, variant, self.scope)  # type: ignore

    def get_cache_dir(self) -> Path:
        """Get the cache directory for this project (scope-aware)."""
        from shared.data_manager import get_cache_dir
        return get_cache_dir(self.name, self.scope)

    def ensure_data_structure(self) -> None:
        """Ensure the complete data directory structure exists for this project."""
        from shared.data_manager import ensure_project_structure
        ensure_project_structure(self.name, self.scope)

    def to_dict(self) -> dict:
        base = {
            "name": self.name,
            "path": str(self.path),
            "description": self.description,
            "language": self.language,
            "scope": self.scope.value,
        }
        optional = {
            "gitlab_project_id": self.gitlab_project_id,
            "gitlab_url": self.gitlab_url,
            "gitlab_token": self.gitlab_token,
            "github_repo": self.github_repo,
            "github_token": self.github_token,
            "notes_dir": self.notes_dir,
            "task_file": self.task_file,
            "habit_file": self.habit_file,
        }
        return {**base, **{k: v for k, v in optional.items() if v is not None}}

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        scope_raw = data.get("scope", "team")
        try:
            scope = ProjectScope(scope_raw)
        except ValueError:
            scope = ProjectScope.TEAM

        return cls(
            name=data["name"],
            path=Path(data["path"]),
            description=data.get("description", ""),
            language=data.get("language", "python"),
            scope=scope,
            gitlab_project_id=data.get("gitlab_project_id"),
            gitlab_url=data.get("gitlab_url"),
            gitlab_token=data.get("gitlab_token"),
            github_repo=data.get("github_repo"),
            github_token=data.get("github_token"),
            notes_dir=data.get("notes_dir"),
            task_file=data.get("task_file"),
            habit_file=data.get("habit_file"),
        )


class ProjectRegistry:
    """Manages known projects across team and personal registries."""

    def __init__(self, registry_file: Path | None = None):
        # If a specific file is given, use only that one (backward compat + testing)
        self._explicit_file = registry_file
        self.projects: dict[str, Project] = {}
        self._load()

    def _load_file(self, path: Path) -> dict[str, Project]:
        """Load projects from a single registry file."""
        if not path.exists():
            return {}
        try:
            with open(path) as f:
                data = json.load(f)
            return {name: Project.from_dict(proj) for name, proj in data.items()}
        except Exception:
            return {}

    def _load(self) -> None:
        """Load projects from registry file(s)."""
        if self._explicit_file is not None:
            self.projects = self._load_file(self._explicit_file)
            return

        from shared.data_manager import get_registry_path, get_personal_registry_path
        # Load team registry first, then personal (personal keys win on collision)
        self.projects = {
            **self._load_file(get_registry_path()),
            **self._load_file(get_personal_registry_path()),
        }

    def _registry_file_for(self, scope: ProjectScope) -> Path:
        """Return the correct registry file path for a given scope."""
        from shared.data_manager import get_registry_path, get_personal_registry_path
        if self._explicit_file is not None:
            return self._explicit_file
        return get_personal_registry_path() if scope == ProjectScope.PERSONAL else get_registry_path()

    def _save_scope(self, scope: ProjectScope) -> None:
        """Save all projects of a given scope to the appropriate registry file."""
        registry_file = self._registry_file_for(scope)
        registry_file.parent.mkdir(parents=True, exist_ok=True)
        scoped = {
            name: proj.to_dict()
            for name, proj in self.projects.items()
            if proj.scope == scope
        }
        with open(registry_file, "w") as f:
            json.dump(scoped, f, indent=2)

    def _save(self) -> None:
        """Save all projects to their respective registry files."""
        if self._explicit_file is not None:
            self._explicit_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._explicit_file, "w") as f:
                json.dump({n: p.to_dict() for n, p in self.projects.items()}, f, indent=2)
            return
        self._save_scope(ProjectScope.TEAM)
        self._save_scope(ProjectScope.PERSONAL)

    def add_project(
        self,
        name: str,
        path: Path | str,
        description: str = "",
        language: str = "python",
        scope: ProjectScope = ProjectScope.TEAM,
        gitlab_project_id: str | None = None,
        gitlab_url: str | None = None,
        gitlab_token: str | None = None,
        github_repo: str | None = None,
        github_token: str | None = None,
        notes_dir: str | None = None,
        task_file: str | None = None,
        habit_file: str | None = None,
    ) -> "Project":
        """Add or update a project in the registry."""
        path = Path(path).resolve()
        if not path.exists():
            raise ValueError(f"Project path does not exist: {path}")

        project = Project(
            name=name,
            path=path,
            description=description,
            language=language,
            scope=scope,
            gitlab_project_id=gitlab_project_id,
            gitlab_url=gitlab_url,
            gitlab_token=gitlab_token,
            github_repo=github_repo,
            github_token=github_token,
            notes_dir=notes_dir,
            task_file=task_file,
            habit_file=habit_file,
        )
        self.projects[name] = project
        self._save()
        return project

    def remove_project(self, name: str) -> None:
        """Remove a project from the registry."""
        if name in self.projects:
            del self.projects[name]
            self._save()

    def get_project(self, name: str) -> Optional[Project]:
        """Get a project by name (exact → case-insensitive → partial match)."""
        if name in self.projects:
            return self.projects[name]
        name_lower = name.lower()
        for proj_name, proj in self.projects.items():
            if proj_name.lower() == name_lower:
                return proj
        for proj_name, proj in self.projects.items():
            if name_lower in proj_name.lower():
                return proj
        return None

    def list_projects(self) -> list[Project]:
        """List all registered projects."""
        return list(self.projects.values())

    def list_by_scope(self, scope: ProjectScope) -> list[Project]:
        """List projects filtered by scope."""
        return [p for p in self.projects.values() if p.scope == scope]

    def search_projects(self, query: str) -> list[Project]:
        """Search projects by name, path, or description."""
        query_lower = query.lower()
        return [
            proj for proj in self.projects.values()
            if (query_lower in proj.name.lower()
                or query_lower in str(proj.path).lower()
                or query_lower in proj.description.lower())
        ]
