from __future__ import annotations

from datetime import datetime

from typer.testing import CliRunner

from project_manager import cli
from shared.models import Issue, IssueDraft, IssueState, IssueTrackerPlatform


runner = CliRunner()


class FakeTrackerClient:
    def __init__(self):
        self.created_draft: IssueDraft | None = None

    def supports(self, capability):
        return True

    def capabilities(self):
        return frozenset()

    def create_issue(self, target_id: str, draft: IssueDraft) -> Issue:
        self.created_draft = draft
        now = datetime(2026, 3, 21, 8, 0, 0)
        return Issue(
            iid=123,
            title=draft.title,
            state=IssueState.OPEN,
            author="bot",
            created_at=now,
            updated_at=now,
            labels=draft.labels,
            assignees=draft.assignees,
            description=draft.description,
            web_url=f"https://github.com/{target_id}/issues/123",
        )


def test_create_command_uses_capability_aware_tracker(monkeypatch):
    fake_client = FakeTrackerClient()

    monkeypatch.setattr(
        cli,
        "_resolve_issue_tracker_target",
        lambda project, github_repo, allow_gitlab_picker=False: cli.IssueTrackerTarget(
            client=fake_client,
            target_id="acme/repo",
            source_name="acme/repo",
            platform=IssueTrackerPlatform.GITHUB,
        ),
    )

    result = runner.invoke(
        cli.app,
        [
            "create",
            "--github-repo", "acme/repo",
            "--title", "Create issue from bot",
            "--description", "Body text",
            "--label", "enhancement,bot",
            "--assignee", "alice",
        ],
    )

    assert result.exit_code == 0
    assert fake_client.created_draft is not None
    assert fake_client.created_draft.title == "Create issue from bot"
    assert fake_client.created_draft.description == "Body text"
    assert fake_client.created_draft.labels == ["enhancement", "bot"]
    assert fake_client.created_draft.assignees == ["alice"]


def test_resolve_issue_tracker_target_uses_registered_github_project(monkeypatch):
    monkeypatch.setattr(
        cli,
        "_load_issue_tracker_projects",
        lambda: [
            {
                "name": "BotsTeam",
                "github_repo": "danieluxury88/BotsTeam",
                "gitlab_project_id": None,
                "description": "BotsTeam Project",
            }
        ],
    )

    target = cli._resolve_issue_tracker_target("BotsTeam", "")

    assert target.platform == IssueTrackerPlatform.GITHUB
    assert target.target_id == "danieluxury88/BotsTeam"
    assert target.source_name == "BotsTeam"
