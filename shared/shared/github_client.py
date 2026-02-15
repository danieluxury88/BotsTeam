"""
GitHub client — shared utility for all bots.

Wraps PyGithub and returns normalised shared model types.
Raw PyGithub objects never leave this module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from github import Auth, Github, GithubException

from shared.config import Config
from shared.models import Issue, IssueSet, IssueState

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


# ── Client ───────────────────────────────────────────────────────────────────


class GitHubClient:
    """
    Authenticated GitHub client.
    Instantiate once and reuse across commands.
    """

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
        self._gh.get_user().login

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
