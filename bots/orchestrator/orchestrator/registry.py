"""Project registry — maintains list of known projects."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Project:
    """A registered project."""
    name: str
    path: Path
    description: str = ""
    language: str = "python"

    # GitLab integration (optional)
    gitlab_project_id: str | None = None
    gitlab_url: str | None = None
    gitlab_token: str | None = None

    # GitHub integration (future)
    github_repo: str | None = None
    github_token: str | None = None

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
        """Get the data directory for this project."""
        from shared.data_manager import get_project_data_dir
        return get_project_data_dir(self.name)

    def get_reports_dir(self, bot: str | None = None) -> Path:
        """Get the reports directory for this project (optionally for a specific bot)."""
        from shared.data_manager import get_reports_dir
        return get_reports_dir(self.name, bot)  # type: ignore

    def get_report_path(self, bot: str, variant: str = "latest") -> Path:
        """Get the path to a bot report (latest or timestamped)."""
        from shared.data_manager import get_report_path
        return get_report_path(self.name, bot, variant)  # type: ignore

    def get_cache_dir(self) -> Path:
        """Get the cache directory for this project."""
        from shared.data_manager import get_cache_dir
        return get_cache_dir(self.name)

    def ensure_data_structure(self) -> None:
        """Ensure the complete data directory structure exists for this project."""
        from shared.data_manager import ensure_project_structure
        ensure_project_structure(self.name)

    def to_dict(self):
        base = {
            "name": self.name,
            "path": str(self.path),
            "description": self.description,
            "language": self.language,
        }
        # Only include integration fields if they have values
        optional = {
            "gitlab_project_id": self.gitlab_project_id,
            "gitlab_url": self.gitlab_url,
            "gitlab_token": self.gitlab_token,
            "github_repo": self.github_repo,
            "github_token": self.github_token,
        }
        return {**base, **{k: v for k, v in optional.items() if v is not None}}

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            name=data["name"],
            path=Path(data["path"]),
            description=data.get("description", ""),
            language=data.get("language", "python"),
            gitlab_project_id=data.get("gitlab_project_id"),
            gitlab_url=data.get("gitlab_url"),
            gitlab_token=data.get("gitlab_token"),
            github_repo=data.get("github_repo"),
            github_token=data.get("github_token"),
        )


class ProjectRegistry:
    """Manages known projects."""

    def __init__(self, registry_file: Path | None = None):
        if registry_file is None:
            from shared.data_manager import get_registry_path
            registry_file = get_registry_path()

        self.registry_file = registry_file
        self.projects: dict[str, Project] = {}
        self._load()

    def _load(self):
        """Load projects from registry file."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r") as f:
                    data = json.load(f)
                    self.projects = {
                        name: Project.from_dict(proj_data)
                        for name, proj_data in data.items()
                    }
            except Exception:
                # If file is corrupted, start fresh
                self.projects = {}

    def _save(self):
        """Save projects to registry file."""
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_file, "w") as f:
            data = {name: proj.to_dict() for name, proj in self.projects.items()}
            json.dump(data, f, indent=2)

    def add_project(
        self,
        name: str,
        path: Path | str,
        description: str = "",
        language: str = "python",
        gitlab_project_id: str | None = None,
        gitlab_url: str | None = None,
        gitlab_token: str | None = None,
        github_repo: str | None = None,
        github_token: str | None = None,
    ):
        """Add a project to the registry."""
        path = Path(path).resolve()
        if not path.exists():
            raise ValueError(f"Project path does not exist: {path}")

        self.projects[name] = Project(
            name=name,
            path=path,
            description=description,
            language=language,
            gitlab_project_id=gitlab_project_id,
            gitlab_url=gitlab_url,
            gitlab_token=gitlab_token,
            github_repo=github_repo,
            github_token=github_token,
        )
        self._save()

    def remove_project(self, name: str):
        """Remove a project from the registry."""
        if name in self.projects:
            del self.projects[name]
            self._save()

    def get_project(self, name: str) -> Optional[Project]:
        """Get a project by name (case-insensitive fuzzy match)."""
        # Exact match first
        if name in self.projects:
            return self.projects[name]

        # Case-insensitive match
        name_lower = name.lower()
        for proj_name, proj in self.projects.items():
            if proj_name.lower() == name_lower:
                return proj

        # Partial match
        for proj_name, proj in self.projects.items():
            if name_lower in proj_name.lower():
                return proj

        return None

    def list_projects(self) -> list[Project]:
        """List all registered projects."""
        return list(self.projects.values())

    def search_projects(self, query: str) -> list[Project]:
        """Search projects by name or path."""
        query_lower = query.lower()
        results = []
        for proj in self.projects.values():
            if (query_lower in proj.name.lower() or
                query_lower in str(proj.path).lower() or
                query_lower in proj.description.lower()):
                results.append(proj)
        return results
