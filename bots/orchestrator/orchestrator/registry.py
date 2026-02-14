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

    def to_dict(self):
        return {
            "name": self.name,
            "path": str(self.path),
            "description": self.description,
            "language": self.language,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            name=data["name"],
            path=Path(data["path"]),
            description=data.get("description", ""),
            language=data.get("language", "python"),
        )


class ProjectRegistry:
    """Manages known projects."""

    def __init__(self, registry_file: Path | None = None):
        if registry_file is None:
            # Default to .devbot/projects.json in home directory
            registry_file = Path.home() / ".devbot" / "projects.json"

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

    def add_project(self, name: str, path: Path | str, description: str = "", language: str = "python"):
        """Add a project to the registry."""
        path = Path(path).resolve()
        if not path.exists():
            raise ValueError(f"Project path does not exist: {path}")

        self.projects[name] = Project(
            name=name,
            path=path,
            description=description,
            language=language,
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
