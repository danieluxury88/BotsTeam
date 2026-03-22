"""
GitHub client — shared utility for all bots.

Wraps PyGithub and returns normalised shared model types.
Raw PyGithub objects never leave this module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from github import Auth, Github, GithubException
from github.GithubObject import NotSet

from shared.config import Config
from shared.issue_tracker import UnsupportedIssueTrackerCapabilityError
from shared.models import (
    Issue,
    IssueTrackerAccessReport,
    IssueTrackerCapabilityStatus,
    IssueDraft,
    IssueSet,
    IssueState,
    IssueTrackerCapability,
    IssueTrackerPlatform,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _normalise_issue(raw) -> Issue:
    """Convert a PyGithub issue object to an Issue datamodel."""
    # Skip pull requests (GitHub API returns them mixed with issues)
    if raw.pull_request is not None:
        raise ValueError("skip_pull_request")

    assignees = [a.login for a in (raw.assignees or [])]

    author = ""
    if raw.user:
        author = raw.user.login

    milestone = None
    if raw.milestone:
        milestone = raw.milestone.title

    due_date = None
    # GitHub milestones have due_on, individual issues don't have due dates
    if raw.milestone and raw.milestone.due_on:
        due_date = raw.milestone.due_on.replace(tzinfo=timezone.utc)

    closed_at = None
    if raw.closed_at:
        closed_at = raw.closed_at.replace(tzinfo=timezone.utc)

    created_at = raw.created_at.replace(tzinfo=timezone.utc)
    updated_at = raw.updated_at.replace(tzinfo=timezone.utc)

    return Issue(
        iid=raw.number,
        title=raw.title,
        state=IssueState.OPEN if raw.state == "open" else IssueState.CLOSED,
        author=author,
        created_at=created_at,
        updated_at=updated_at,
        labels=[label.name for label in raw.labels],
        assignees=assignees,
        milestone=milestone,
        description=raw.body or "",
        weight=None,  # GitHub doesn't have native weight
        due_date=due_date,
        closed_at=closed_at,
        web_url=raw.html_url,
    )


def _format_github_error(exc: GithubException) -> str:
    """Return a readable GitHub API error message."""
    raw = str(exc).strip()
    if raw and raw != "None":
        return raw

    data = getattr(exc, "data", None)
    if isinstance(data, dict):
        message = data.get("message")
        errors = data.get("errors")
        parts: list[str] = []
        if message:
            parts.append(str(message))
        if errors:
            parts.append(str(errors))
        if parts:
            return " | ".join(parts)

    status = getattr(exc, "status", None)
    if status is not None:
        return f"GitHub API error status {status}"
    return exc.__class__.__name__


# ── Client ───────────────────────────────────────────────────────────────────


class GitHubClient:
    """
    Authenticated GitHub client.
    Instantiate once and reuse across commands.
    """

    platform = IssueTrackerPlatform.GITHUB
    _CAPABILITIES = frozenset({
        IssueTrackerCapability.FETCH_ISSUES,
        IssueTrackerCapability.GET_ISSUE,
        IssueTrackerCapability.CREATE_ISSUE,
        IssueTrackerCapability.UPDATE_ISSUE_DESCRIPTION,
    })

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._token = token or Config.github_token()
        self._base_url = base_url or Config.github_base_url()

        auth = Auth.Token(self._token)

        if self._base_url != "https://api.github.com":
            # GitHub Enterprise
            self._gh = Github(base_url=self._base_url, auth=auth)
        else:
            self._gh = Github(auth=auth)

        # Validate token by fetching authenticated user
        self._authenticated_as = self._gh.get_user().login

    def capabilities(self) -> frozenset[IssueTrackerCapability]:
        """Return the operations supported by this client."""
        return self._CAPABILITIES

    def supports(self, capability: IssueTrackerCapability) -> bool:
        """Check whether the client supports a capability."""
        return capability in self._CAPABILITIES

    def _issues_enabled(self, gh_repo) -> bool:
        return getattr(gh_repo, "has_issues", True) is not False

    def _probe_issue_read_access(self, gh_repo) -> tuple[bool, str]:
        """Verify issue read access with a single lightweight API call."""
        if not self._issues_enabled(gh_repo):
            return False, "Issues are disabled for this repository."

        try:
            next(iter(gh_repo.get_issues(state="all", sort="updated", direction="desc")), None)
        except GithubException as e:
            if getattr(e, "status", None) == 410:
                return False, "Issues are disabled for this repository."
            return False, f"Read access failed: {_format_github_error(e)}"

        return True, "Verified issue read access."

    def _probe_issue_write_access(self, gh_repo) -> tuple[bool, str]:
        """Verify issue write access without creating an issue."""
        if not self._issues_enabled(gh_repo):
            return False, "Issues are disabled for this repository."

        try:
            gh_repo._requester.requestJsonAndCheck(
                "POST",
                f"{gh_repo.url}/issues",
                input={"title": ""},
            )
        except GithubException as e:
            status = getattr(e, "status", None)
            if status == 422:
                return True, "Verified issue write access with a validation-only create probe."
            if status == 410:
                return False, "Issues are disabled for this repository."
            return False, f"Write access failed: {_format_github_error(e)}"

        return False, "Unexpected success from write probe; permission status is uncertain."

    def probe_capabilities(self, repo: str) -> IssueTrackerAccessReport:
        """Verify runtime access for supported GitHub issue operations."""
        gh_repo = self.get_repo(repo)
        read_ok, read_detail = self._probe_issue_read_access(gh_repo)
        write_ok, write_detail = self._probe_issue_write_access(gh_repo)

        return IssueTrackerAccessReport(
            platform=self.platform,
            target_id=repo,
            target_name=getattr(gh_repo, "full_name", repo),
            authenticated_as=getattr(self, "_authenticated_as", ""),
            capability_statuses=[
                IssueTrackerCapabilityStatus(
                    capability=IssueTrackerCapability.FETCH_ISSUES,
                    supported=True,
                    authorized=read_ok,
                    detail=read_detail,
                ),
                IssueTrackerCapabilityStatus(
                    capability=IssueTrackerCapability.GET_ISSUE,
                    supported=True,
                    authorized=read_ok,
                    detail=f"Uses issue read access. {read_detail}",
                ),
                IssueTrackerCapabilityStatus(
                    capability=IssueTrackerCapability.CREATE_ISSUE,
                    supported=True,
                    authorized=write_ok,
                    detail=write_detail,
                ),
                IssueTrackerCapabilityStatus(
                    capability=IssueTrackerCapability.UPDATE_ISSUE_DESCRIPTION,
                    supported=True,
                    authorized=write_ok,
                    detail=f"Uses issue write access. {write_detail}",
                ),
            ],
        )

    def get_repo(self, repo: str):
        """
        Resolve a repository by full name (owner/repo).
        """
        try:
            return self._gh.get_repo(repo)
        except GithubException as e:
            raise ValueError(
                f"Repository '{repo}' not found or no access.\n"
                f"GitHub error: {e}"
            )

    def get_issue(self, repo: str, issue_number: int) -> Issue:
        """Fetch a single GitHub issue by its repository-scoped number."""
        gh_repo = self.get_repo(repo)
        try:
            raw = gh_repo.get_issue(number=issue_number)
        except GithubException as e:
            raise ValueError(
                f"Issue #{issue_number} not found in repository '{repo}'.\n"
                f"GitHub error: {e}"
            )

        try:
            return _normalise_issue(raw)
        except ValueError as e:
            raise ValueError(
                f"Item #{issue_number} in repository '{repo}' is not an issue."
            ) from e

    def fetch_issues(
        self,
        repo: str,
        state: IssueState = IssueState.ALL,
        max_issues: int = 500,
    ) -> IssueSet:
        """
        Fetch issues for a repository and return a normalised IssueSet.

        Args:
            repo:       Full repository name "owner/repo".
            state:      IssueState.OPEN, CLOSED, or ALL.
            max_issues: Safety cap to avoid fetching thousands of issues.
        """
        gh_repo = self.get_repo(repo)

        # Map our IssueState to GitHub API state parameter
        state_map = {
            IssueState.OPEN: "open",
            IssueState.CLOSED: "closed",
            IssueState.ALL: "all",
        }
        gh_state = state_map[state]

        raw_issues = gh_repo.get_issues(
            state=gh_state,
            sort="updated",
            direction="desc",
        )

        issues: list[Issue] = []
        count = 0
        for raw in raw_issues:
            if count >= max_issues:
                break
            try:
                issues.append(_normalise_issue(raw))
                count += 1
            except ValueError:
                # Skip pull requests
                continue

        return IssueSet(
            project_id=repo,
            project_name=gh_repo.name,
            fetched_at=datetime.now(tz=timezone.utc),
            issues=issues,
        )

    def iter_issues(
        self,
        repo: str,
        state: IssueState = IssueState.ALL,
    ) -> Iterator[Issue]:
        """Stream issues one by one — useful for very large repositories."""
        gh_repo = self.get_repo(repo)

        state_map = {
            IssueState.OPEN: "open",
            IssueState.CLOSED: "closed",
            IssueState.ALL: "all",
        }

        for raw in gh_repo.get_issues(
            state=state_map[state],
            sort="updated",
            direction="desc",
        ):
            try:
                yield _normalise_issue(raw)
            except ValueError:
                continue

    def create_issue(self, repo: str, draft: IssueDraft) -> Issue:
        """Create a GitHub issue and return the normalized issue."""
        if not self.supports(IssueTrackerCapability.CREATE_ISSUE):
            raise UnsupportedIssueTrackerCapabilityError(
                f"{self.platform.value} does not support issue creation."
            )

        gh_repo = self.get_repo(repo)
        try:
            raw = gh_repo.create_issue(
                title=draft.title,
                body=draft.description or NotSet,
                labels=draft.labels or NotSet,
                assignees=draft.assignees or NotSet,
            )
        except GithubException as e:
            raise ValueError(
                f"Failed to create issue in repository '{repo}'.\n"
                f"GitHub error: {_format_github_error(e)}"
            )
        return _normalise_issue(raw)

    def update_issue_description(
        self,
        repo: str,
        issue_number: int,
        description: str,
    ) -> Issue:
        """Update a GitHub issue description and return the normalized issue."""
        if not self.supports(IssueTrackerCapability.UPDATE_ISSUE_DESCRIPTION):
            raise UnsupportedIssueTrackerCapabilityError(
                f"{self.platform.value} does not support issue updates."
            )

        gh_repo = self.get_repo(repo)
        try:
            raw = gh_repo.get_issue(number=issue_number)
            raw.edit(body=description)
        except GithubException as e:
            raise ValueError(
                f"Failed to update issue #{issue_number} in repository '{repo}'.\n"
                f"GitHub error: {_format_github_error(e)}"
            )
        return _normalise_issue(raw)


# ── Convenience function ─────────────────────────────────────────────────────


def fetch_issues(
    repo: str,
    state: IssueState = IssueState.ALL,
    max_issues: int = 500,
    token: str | None = None,
    base_url: str | None = None,
) -> IssueSet:
    """
    Module-level convenience — creates a client and fetches issues in one call.
    All bots can use this without managing a client instance.
    """
    client = GitHubClient(token=token, base_url=base_url)
    return client.fetch_issues(repo, state=state, max_issues=max_issues)


def get_issue(
    repo: str,
    issue_number: int,
    token: str | None = None,
    base_url: str | None = None,
) -> Issue:
    """Module-level convenience — fetch a single issue by number."""
    client = GitHubClient(token=token, base_url=base_url)
    return client.get_issue(repo, issue_number)


def create_issue(
    repo: str,
    draft: IssueDraft,
    token: str | None = None,
    base_url: str | None = None,
) -> Issue:
    """Module-level convenience — create a single issue."""
    client = GitHubClient(token=token, base_url=base_url)
    return client.create_issue(repo, draft)


def update_issue_description(
    repo: str,
    issue_number: int,
    description: str,
    token: str | None = None,
    base_url: str | None = None,
) -> Issue:
    """Module-level convenience — update a single issue description."""
    client = GitHubClient(token=token, base_url=base_url)
    return client.update_issue_description(repo, issue_number, description)
