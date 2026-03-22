from __future__ import annotations

from pathlib import Path

from orchestrator.registry import Project, ProjectRegistry
from shared.models import ProjectScope


def test_project_roundtrips_languages_and_frameworks(tmp_path: Path):
    registry_file = tmp_path / "projects.json"
    registry = ProjectRegistry(registry_file)
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    registry.add_project(
        "UniLi",
        repo_path,
        description="Drupal project",
        language="php",
        languages=["php", "javascript"],
        frameworks=["Drupal"],
        scope=ProjectScope.TEAM,
    )

    reloaded = ProjectRegistry(registry_file)
    project = reloaded.projects["UniLi"]

    assert project.language == "php"
    assert project.languages == ["php", "javascript"]
    assert project.frameworks == ["Drupal"]


def test_project_from_dict_backfills_languages_from_legacy_language():
    project = Project.from_dict({
        "name": "Legacy",
        "path": "/tmp/legacy",
        "language": "php",
    })

    assert project.language == "php"
    assert project.languages == ["php"]
