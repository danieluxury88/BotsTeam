"""Git repository reader — extracts and groups commit history."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import git


@dataclass
class CommitInfo:
    sha: str
    message: str
    author: str
    date: datetime
    files_changed: list[str] = field(default_factory=list)


@dataclass
class CommitGroup:
    """A logical group of commits (e.g. same day, same author burst, or topic)."""
    label: str
    commits: list[CommitInfo] = field(default_factory=list)

    @property
    def authors(self) -> list[str]:
        return list({c.author for c in self.commits})

    @property
    def date_range(self) -> tuple[datetime, datetime]:
        dates = [c.date for c in self.commits]
        return min(dates), max(dates)

    @property
    def all_files(self) -> list[str]:
        seen = set()
        files = []
        for c in self.commits:
            for f in c.files_changed:
                if f not in seen:
                    seen.add(f)
                    files.append(f)
        return files


def read_commits(
    repo_path: str | Path,
    branch: str = "HEAD",
    max_commits: int = 200,
) -> list[CommitInfo]:
    """Read commits from a git repository."""
    repo = git.Repo(str(repo_path), search_parent_directories=True)
    commits = []

    for commit in repo.iter_commits(branch, max_count=max_commits):
        try:
            files = list(commit.stats.files.keys())
        except Exception:
            files = []

        commits.append(
            CommitInfo(
                sha=commit.hexsha[:8],
                message=commit.message.strip(),
                author=commit.author.name,
                date=datetime.fromtimestamp(commit.committed_date, tz=timezone.utc),
                files_changed=files,
            )
        )

    return commits


def group_commits_by_day(commits: list[CommitInfo]) -> list[CommitGroup]:
    """Group commits by calendar day (most recent first)."""
    groups: dict[str, CommitGroup] = {}

    for commit in commits:
        day_key = commit.date.strftime("%Y-%m-%d")
        label = commit.date.strftime("%A, %B %d %Y")
        if day_key not in groups:
            groups[day_key] = CommitGroup(label=label)
        groups[day_key].commits.append(commit)

    # Return sorted most-recent first
    return [groups[k] for k in sorted(groups.keys(), reverse=True)]


def group_commits_by_author(commits: list[CommitInfo]) -> list[CommitGroup]:
    """Group commits by author."""
    groups: dict[str, CommitGroup] = {}

    for commit in commits:
        author = commit.author
        if author not in groups:
            groups[author] = CommitGroup(label=f"Author: {author}")
        groups[author].commits.append(commit)

    return sorted(groups.values(), key=lambda g: len(g.commits), reverse=True)


def group_commits_auto(commits: list[CommitInfo], max_groups: int = 10) -> list[CommitGroup]:
    """
    Auto-grouping strategy:
    - If history spans > 7 days → group by day
    - Otherwise → group by author
    Caps at max_groups to keep LLM context manageable.
    """
    if not commits:
        return []

    dates = [c.date for c in commits]
    span_days = (max(dates) - min(dates)).days

    if span_days > 7:
        groups = group_commits_by_day(commits)
    else:
        groups = group_commits_by_author(commits)

    # Merge overflow into an "older activity" bucket
    if len(groups) > max_groups:
        overflow = groups[max_groups:]
        main = groups[:max_groups]
        bucket = CommitGroup(label="Older activity")
        for g in overflow:
            bucket.commits.extend(g.commits)
        main.append(bucket)
        return main

    return groups


def format_groups_for_llm(groups: list[CommitGroup]) -> str:
    """Serialize grouped commits into a compact text block for the LLM prompt."""
    lines = []

    for group in groups:
        start, end = group.date_range
        date_str = (
            start.strftime("%Y-%m-%d")
            if start.date() == end.date()
            else f"{start.strftime('%Y-%m-%d')} → {end.strftime('%Y-%m-%d')}"
        )
        lines.append(f"\n## {group.label} ({date_str}) — {len(group.commits)} commit(s)")
        lines.append(f"Authors: {', '.join(group.authors)}")

        # List unique top-level paths changed
        top_paths = _summarize_paths(group.all_files)
        if top_paths:
            lines.append(f"Areas touched: {', '.join(top_paths)}")

        lines.append("Commits:")
        for c in group.commits:
            first_line = c.message.splitlines()[0][:120]
            lines.append(f"  [{c.sha}] {first_line}")

    return "\n".join(lines)


def _summarize_paths(files: list[str], max_paths: int = 6) -> list[str]:
    """Collapse file paths to their top-level directories for brevity."""
    dirs: dict[str, int] = {}
    for f in files:
        top = f.split("/")[0] if "/" in f else f
        dirs[top] = dirs.get(top, 0) + 1

    sorted_dirs = sorted(dirs.items(), key=lambda x: x[1], reverse=True)
    return [f"{d} ({n})" for d, n in sorted_dirs[:max_paths]]
