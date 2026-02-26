"""
GitLab client — shared utility for all bots.

Wraps python-gitlab and returns normalised shared model types.
Raw python-gitlab objects never leave this module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import gitlab

from shared.config import Config
from shared.models import Issue, IssueSet, IssueState

# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_dt(value: str | None) -> datetime | None:
    """Parse a GitLab ISO datetime string to a timezone-aware datetime."""
    if not value:
        return None
    try:
        # GitLab returns e.g. "2024-01-15T10:30:00.000Z"
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt
    except ValueError:
        return None


def _require_dt(value: str | None, fallback: datetime | None = None) -> datetime:
    parsed = _parse_dt(value)
    if parsed:
        return parsed
    if fallback:
        return fallback
    return datetime.now(tz=timezone.utc)


def _normalise_issue(raw) -> Issue:
    """Convert a python-gitlab issue object to an Issue datamodel."""
    assignees = [a.get("username", a.get("name", "")) for a in (raw.assignees or [])]

    author = ""
    if hasattr(raw, "author") and raw.author:
        author = raw.author.get("username", raw.author.get("name", ""))

    milestone = None
    if hasattr(raw, "milestone") and raw.milestone:
        milestone = raw.milestone.get("title")

    due_date = None
    if hasattr(raw, "due_date") and raw.due_date:
        # due_date is "YYYY-MM-DD", not a full ISO datetime
        try:
            due_date = datetime.strptime(raw.due_date, "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            pass

    return Issue(
        iid=raw.iid,
        title=raw.title,
        state=IssueState.OPEN if raw.state == "opened" else IssueState.CLOSED,
        author=author,
        created_at=_require_dt(raw.created_at),
        updated_at=_require_dt(raw.updated_at),
        labels=list(raw.labels or []),
        assignees=assignees,
        milestone=milestone,
        description=raw.description or "",
        weight=getattr(raw, "weight", None),
        due_date=due_date,
        closed_at=_parse_dt(getattr(raw, "closed_at", None)),
        web_url=getattr(raw, "web_url", ""),
    )


# ── Client ───────────────────────────────────────────────────────────────────

class GitLabClient:
    """
    Authenticated GitLab client.
    Instantiate once and reuse across commands.
    """

    def __init__(
        self,
        token: str | None = None,
        url: str | None = None,
    ) -> None:
        self._token = token or Config.gitlab_token()
        self._url   = url or Config.gitlab_url()
        self._gl    = gitlab.Gitlab(self._url, private_token=self._token)
        self._gl.auth()  # Validates token immediately — fails fast on bad creds

    def get_project(self, project_id: str):
        """
        Resolve a project by ID or namespace/path.
        Accepts: numeric ID ("12345") or path ("mygroup/myproject").
        """
        try:
            return self._gl.projects.get(project_id)
        except gitlab.exceptions.GitlabGetError as e:
            raise ValueError(
                f"Project '{project_id}' not found or no access.\n"
                f"GitLab error: {e}"
            )

    def fetch_issues(
        self,
        project_id: str,
        state: IssueState = IssueState.ALL,
        max_issues: int = 500,
    ) -> IssueSet:
        """
        Fetch issues for a project and return a normalised IssueSet.

        Args:
            project_id: Numeric ID or "namespace/project" path.
            state:       IssueState.OPEN, CLOSED, or ALL.
            max_issues:  Safety cap to avoid fetching thousands of issues.
        """
        project = self.get_project(project_id)

        raw_issues = project.issues.list(
            state=state.value,
            order_by="updated_at",
            sort="desc",
            get_all=False,
            per_page=min(max_issues, 100),
        )

        # Handle pagination if needed
        all_raw: list = list(raw_issues)
        if len(all_raw) == 100 and max_issues > 100:
            page = 2
            while len(all_raw) < max_issues:
                batch = project.issues.list(
                    state=state.value,
                    order_by="updated_at",
                    sort="desc",
                    page=page,
                    per_page=100,
                )
                if not batch:
                    break
                all_raw.extend(batch)
                page += 1

        issues = [_normalise_issue(r) for r in all_raw[:max_issues]]

        return IssueSet(
            project_id=str(project_id),
            project_name=project.name,
            fetched_at=datetime.now(tz=timezone.utc),
            issues=issues,
        )

    def iter_issues(
        self,
        project_id: str,
        state: IssueState = IssueState.ALL,
    ) -> Iterator[Issue]:
        """Stream issues one by one — useful for very large projects."""
        project = self.get_project(project_id)
        for raw in project.issues.list(
            state=state.value,
            order_by="updated_at",
            sort="desc",
            iterator=True,
        ):
            yield _normalise_issue(raw)

    def get_issue(self, project_id: str, issue_iid: int) -> Issue:
        """Fetch a single issue by its project-scoped IID."""
        project = self.get_project(project_id)
        try:
            raw = project.issues.get(issue_iid)
        except gitlab.exceptions.GitlabGetError as e:
            raise ValueError(f"Issue #{issue_iid} not found in project '{project_id}'.\nGitLab error: {e}")
        return _normalise_issue(raw)

    def update_issue_description(
        self,
        project_id: str,
        issue_iid: int,
        description: str,
    ) -> None:
        """Update a single issue's description in GitLab (atomic PUT, no re-fetch)."""
        project = self.get_project(project_id)
        project.issues.update(issue_iid, {"description": description})


# ── Convenience function ─────────────────────────────────────────────────────

def fetch_issues(
    project_id: str,
    state: IssueState = IssueState.ALL,
    max_issues: int = 500,
    token: str | None = None,
    url: str | None = None,
) -> IssueSet:
    """
    Module-level convenience — creates a client and fetches issues in one call.
    All bots can use this without managing a client instance.
    """
    client = GitLabClient(token=token, url=url)
    return client.fetch_issues(project_id, state=state, max_issues=max_issues)


def get_issue(
    project_id: str,
    issue_iid: int,
    token: str | None = None,
    url: str | None = None,
) -> Issue:
    """Module-level convenience — fetch a single issue by IID."""
    client = GitLabClient(token=token, url=url)
    return client.get_issue(project_id, issue_iid)


def update_issue_description(
    project_id: str,
    issue_iid: int,
    description: str,
    token: str | None = None,
    url: str | None = None,
) -> None:
    """
    Module-level convenience — creates a client and updates an issue description.
    """
    client = GitLabClient(token=token, url=url)
    client.update_issue_description(project_id, issue_iid, description)
