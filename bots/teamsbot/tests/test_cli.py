from __future__ import annotations

from pathlib import Path

import pytest
import typer

from teamsbot import cli


def test_load_latest_report_reads_project_report(tmp_path: Path) -> None:
    report_path = tmp_path / "data" / "BotsTeam" / "reports" / "gitbot" / "latest.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("# Report\n\nHello", encoding="utf-8")

    project = type(
        "Project",
        (),
        {
            "name": "BotsTeam",
            "teams_channels": None,
            "get_report_path": lambda self, bot_name, variant: report_path,
        },
    )()
    registry = type("Registry", (), {"get_project": lambda self, name: project})()

    original_registry = cli.ProjectRegistry
    cli.ProjectRegistry = lambda: registry
    try:
        resolved_project, path, content = cli._load_latest_report("BotsTeam", "gitbot")
    finally:
        cli.ProjectRegistry = original_registry

    assert resolved_project is project
    assert path == report_path
    assert content == "# Report\n\nHello"


def test_load_latest_report_exits_when_project_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = type("Registry", (), {"get_project": lambda self, name: None})()
    monkeypatch.setattr(cli, "ProjectRegistry", lambda: registry)

    with pytest.raises(typer.Exit):
        cli._load_latest_report("Missing", "gitbot")


def test_resolve_project_channel_webhook_uses_named_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEAMS_REPORTS_URL", "https://example.test/reports")

    project = type(
        "Project",
        (),
        {
            "name": "BotsTeam",
            "teams_channels": [{"name": "Reports", "webhook_env_var": "TEAMS_REPORTS_URL"}],
            "get_teams_channel": lambda self, name=None: self.teams_channels[0],
            "get_teams_webhook_url": lambda self, name=None: "https://example.test/reports",
        },
    )()

    assert cli._resolve_project_channel_webhook(project, "Reports") == "https://example.test/reports"


def test_resolve_project_channel_webhook_uses_single_channel_by_default() -> None:
    project = type(
        "Project",
        (),
        {
            "name": "BotsTeam",
            "teams_channels": [{"name": "Reports", "webhook_env_var": "TEAMS_REPORTS_URL"}],
            "get_teams_channel": lambda self, name=None: self.teams_channels[0],
            "get_teams_webhook_url": lambda self, name=None: "https://example.test/reports",
        },
    )()

    assert cli._resolve_project_channel_webhook(project, None) == "https://example.test/reports"
