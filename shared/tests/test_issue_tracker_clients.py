from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from shared.github_client import GitHubClient
from shared.gitlab_client import GitLabClient
from shared.issue_tracker import UnsupportedIssueTrackerCapabilityError
from shared.models import IssueDraft, IssueState, IssueTrackerCapability


def _github_raw_issue(*, number: int, title: str, body: str = "Body"):
    now = datetime(2026, 3, 20, 12, 0, 0)
    return SimpleNamespace(
        number=number,
        title=title,
        state="open",
        user=SimpleNamespace(login="alice"),
        created_at=now,
        updated_at=now,
        labels=[SimpleNamespace(name="bug")],
        assignees=[SimpleNamespace(login="bob")],
        milestone=None,
        body=body,
        closed_at=None,
        html_url=f"https://github.com/acme/repo/issues/{number}",
        pull_request=None,
        edit=lambda **kwargs: None,
    )


def _gitlab_raw_issue(*, iid: int, title: str, description: str = "Body"):
    return SimpleNamespace(
        iid=iid,
        title=title,
        state="opened",
        author={"username": "alice"},
        created_at="2026-03-20T12:00:00.000Z",
        updated_at="2026-03-20T12:00:00.000Z",
        labels=["bug"],
        assignees=[{"username": "bob"}],
        milestone=None,
        description=description,
        weight=None,
        due_date=None,
        closed_at=None,
        web_url=f"https://gitlab.com/acme/repo/-/issues/{iid}",
    )


def test_github_client_exposes_capabilities_and_creates_issue(monkeypatch):
    created_calls = []

    class FakeRepo:
        def create_issue(self, **kwargs):
            created_calls.append(kwargs)
            return _github_raw_issue(number=42, title=kwargs["title"], body=kwargs.get("body") or "")

    client = object.__new__(GitHubClient)
    monkeypatch.setattr(client, "get_repo", lambda repo: FakeRepo())

    assert client.supports(IssueTrackerCapability.CREATE_ISSUE)
    assert client.supports(IssueTrackerCapability.UPDATE_ISSUE_DESCRIPTION)

    issue = client.create_issue(
        "acme/repo",
        IssueDraft(
            title="Ship issue creation",
            description="Create this from PMBot.",
            labels=["enhancement"],
            assignees=["alice"],
        ),
    )

    assert created_calls == [{
        "title": "Ship issue creation",
        "body": "Create this from PMBot.",
        "labels": ["enhancement"],
        "assignees": ["alice"],
    }]
    assert issue.iid == 42
    assert issue.title == "Ship issue creation"
    assert issue.state == IssueState.OPEN


def test_gitlab_client_updates_issue_description_and_reports_missing_creation_support(monkeypatch):
    updated_calls = []

    class FakeIssues:
        def update(self, issue_iid, payload):
            updated_calls.append((issue_iid, payload))

        def get(self, issue_iid):
            return _gitlab_raw_issue(iid=issue_iid, title="Existing issue", description="Updated body")

    class FakeProject:
        issues = FakeIssues()

    client = object.__new__(GitLabClient)
    monkeypatch.setattr(client, "get_project", lambda project_id: FakeProject())

    assert client.supports(IssueTrackerCapability.GET_ISSUE)
    assert not client.supports(IssueTrackerCapability.CREATE_ISSUE)

    issue = client.update_issue_description("group/repo", 7, "Updated body")

    assert updated_calls == [(7, {"description": "Updated body"})]
    assert issue.iid == 7
    assert issue.description == "Updated body"

    with pytest.raises(UnsupportedIssueTrackerCapabilityError):
        client.create_issue("group/repo", IssueDraft(title="Not yet"))
