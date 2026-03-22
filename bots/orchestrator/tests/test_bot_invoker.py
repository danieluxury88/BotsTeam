from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from orchestrator.bot_invoker import invoke_bot, invoke_pipeline
from shared.models import BotResult, ChangeSet, ProjectScope


def test_invoke_bot_passes_generic_params_to_pmbot(monkeypatch):
    captured = {}

    def fake_runner(
        *,
        project_name=None,
        github_repo=None,
        mode=None,
        title=None,
        description=None,
        dry_run=None,
    ):
        captured.update({
            "project_name": project_name,
            "github_repo": github_repo,
            "mode": mode,
            "title": title,
            "description": description,
            "dry_run": dry_run,
        })
        return BotResult(
            bot_name="issuebot",
            status="success",
            summary="ok",
            markdown_report="ok",
        )

    project = SimpleNamespace(
        name="BotsTeam",
        scope=ProjectScope.TEAM,
        gitlab_project_id=None,
        github_repo="danieluxury88/BotsTeam",
        has_gitlab=lambda: False,
        has_github=lambda: True,
        get_gitlab_url=lambda: "https://gitlab.com",
        get_gitlab_token=lambda: None,
        get_github_token=lambda: "token",
        get_github_base_url=lambda: "https://api.github.com",
    )

    monkeypatch.setattr("orchestrator.bot_invoker.pmbot_get_result", fake_runner)

    result = invoke_bot(
        "pmbot",
        project=project,
        bot_params={
            "mode": "create",
            "title": "Header Navigation bug",
            "description": "Investigate dashboard header nav.",
            "dry_run": True,
        },
    )

    assert result.status == "success"
    assert captured["project_name"] == "BotsTeam"
    assert captured["github_repo"] == "danieluxury88/BotsTeam"
    assert captured["mode"] == "create"
    assert captured["title"] == "Header Navigation bug"
    assert captured["description"] == "Investigate dashboard header nav."
    assert captured["dry_run"] is True


def test_invoke_bot_filters_unknown_params_for_gitbot(monkeypatch, tmp_path: Path):
    captured = {}
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    def fake_runner(path, branch=None, project_name=None, max_commits=None, model=None, since=None, until=None):
        captured["path"] = path
        captured["branch"] = branch
        captured["project_name"] = project_name
        return BotResult(
            bot_name="gitbot",
            status="success",
            summary="ok",
            markdown_report="ok",
        )

    monkeypatch.setattr("orchestrator.bot_invoker.gitbot_get_result", fake_runner)

    result = invoke_bot(
        "gitbot",
        repo_path=repo_path,
        bot_params={"branch": "main", "unknown_flag": "ignored"},
    )

    assert result.status == "success"
    assert captured["path"] == repo_path.resolve()
    assert captured["branch"] == "main"
    assert "unknown_flag" not in captured


def test_invoke_pipeline_composes_gitbot_and_qabot(monkeypatch, tmp_path: Path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    project = SimpleNamespace(
        name="uni.li",
        path=repo_path,
        scope=ProjectScope.TEAM,
    )

    monkeypatch.setattr(
        "orchestrator.bot_invoker.gitbot_get_changeset",
        lambda path, branch="HEAD", max_commits=300, model=None, since=None, until=None: ChangeSet(
            summary="## Overview\n\nRecent changes touched navigation and layout.",
            files_touched=["web/modules/custom/site/header.php"],
            raw_data={"commit_count": 3},
        ),
    )
    monkeypatch.setattr(
        "orchestrator.bot_invoker.analyze_changeset_for_testing",
        lambda changeset, model=None: SimpleNamespace(
            summary="Analysis complete",
            suggestions=[],
            risk_areas=["dashboard"],
            markdown_report="## Priority Test Areas\n\n- Validate header navigation on dashboard.",
        ),
    )
    monkeypatch.setattr(
        "orchestrator.bot_invoker.save_report",
        lambda project_name, bot_name, report, save_latest=True, save_timestamped=True: (
            Path("/tmp/latest.md"),
            Path("/tmp/archive.md"),
        ),
    )

    result = invoke_pipeline("gitbot_qabot", project=project, bot_params={"max_commits": 20})

    assert result.status == "success"
    assert result.bot_name == "gitbot_qabot"
    assert "GitBot Summary" in result.markdown_report
    assert "QABot Test Recommendations" in result.markdown_report
    assert result.data["pipeline"] == "gitbot_qabot"
    assert result.data["report_saved"]["latest"] == "/tmp/latest.md"
