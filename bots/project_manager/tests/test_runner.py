from __future__ import annotations

from datetime import datetime

from project_manager import runner
from shared.models import (
    Issue,
    IssueState,
    IssueTrackerAccessReport,
    IssueTrackerCapability,
    IssueTrackerCapabilityStatus,
    IssueTrackerPlatform,
)


class FakeTrackerClient:
    def __init__(self):
        self.created = None

    def create_issue(self, target_id, draft):
        self.created = (target_id, draft)
        now = datetime(2026, 3, 21, 12, 0, 0)
        return Issue(
            iid=77,
            title=draft.title,
            state=IssueState.OPEN,
            author="bot",
            created_at=now,
            updated_at=now,
            labels=draft.labels,
            assignees=draft.assignees,
            description=draft.description,
            web_url=f"https://github.com/{target_id}/issues/77",
        )

    def probe_capabilities(self, target_id):
        return IssueTrackerAccessReport(
            platform=IssueTrackerPlatform.GITHUB,
            target_id=target_id,
            target_name=target_id,
            authenticated_as="alice",
            capability_statuses=[
                IssueTrackerCapabilityStatus(
                    capability=IssueTrackerCapability.FETCH_ISSUES,
                    supported=True,
                    authorized=True,
                    detail="Verified issue read access.",
                ),
                IssueTrackerCapabilityStatus(
                    capability=IssueTrackerCapability.CREATE_ISSUE,
                    supported=True,
                    authorized=False,
                    detail="Write access failed: missing scope.",
                ),
            ],
        )


def test_runner_create_mode_uses_tracker_target(monkeypatch):
    client = FakeTrackerClient()

    monkeypatch.setattr(
        runner,
        "_resolve_target",
        lambda **kwargs: runner.IssueTrackerTarget(
            client=client,
            target_id="danieluxury88/BotsTeam",
            source_name="BotsTeam",
            platform=IssueTrackerPlatform.GITHUB,
        ),
    )

    result = runner.get_bot_result(
        project_name="BotsTeam",
        github_repo="danieluxury88/BotsTeam",
        mode="create",
        title="Dashboard header navigation problem",
        description="Investigate broken active state in the dashboard header.",
        labels=["bug", "dashboard"],
    )

    assert result.status == "success"
    assert client.created is not None
    assert client.created[0] == "danieluxury88/BotsTeam"
    assert client.created[1].title == "Dashboard header navigation problem"
    assert client.created[1].labels == ["bug", "dashboard"]


def test_runner_check_mode_returns_access_report(monkeypatch):
    client = FakeTrackerClient()

    monkeypatch.setattr(
        runner,
        "_resolve_target",
        lambda **kwargs: runner.IssueTrackerTarget(
            client=client,
            target_id="danieluxury88/BotsTeam",
            source_name="BotsTeam",
            platform=IssueTrackerPlatform.GITHUB,
        ),
    )

    result = runner.get_bot_result(
        project_name="BotsTeam",
        github_repo="danieluxury88/BotsTeam",
        mode="check",
    )

    assert result.status == "partial"
    assert "issue-tracker access" in result.summary.lower()
    assert "authenticated as: alice" in result.report_md.lower()
