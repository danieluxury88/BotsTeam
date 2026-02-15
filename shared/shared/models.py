"""Bot collaboration contracts — shared data models for all devbots."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal


# ── Status Enums ─────────────────────────────────────────────────────────────

class BotStatus(str, Enum):
    """Bot execution status - richer than simple success/error/warning."""
    SUCCESS = "success"
    PARTIAL = "partial"       # Completed with warnings
    FAILED = "failed"
    SKIPPED = "skipped"       # Nothing to do (e.g. no commits, no tests)
    ERROR = "error"           # Alias for backward compatibility
    WARNING = "warning"       # Alias for backward compatibility


# ── Core Bot Models ──────────────────────────────────────────────────────────

@dataclass
class RepoContext:
    """Repository metadata for bot initialization."""
    path: Path
    branch: str = "HEAD"
    language: str | None = None
    test_framework: str | None = None  # "pytest", "unittest", etc.
    max_commits: int = 100

    @property
    def name(self) -> str:
        return self.path.resolve().name

    def validate(self) -> None:
        if not self.path.exists():
            raise ValueError(f"Repository path does not exist: {self.path}")
        git_dir = self.path / ".git"
        if not git_dir.exists():
            raise ValueError(f"No .git directory found at: {self.path}")


@dataclass
class ChangeSet:
    """Gitbot's output that other bots (like qabot) can consume."""
    summary: str
    files_touched: list[str] = field(default_factory=list)
    date_range: tuple[datetime, datetime] | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)  # Flexible payload


@dataclass
class BotResult:
    """Universal return type for all bots — enables composition."""
    bot_name: str
    status: BotStatus | Literal["success", "error", "warning"]  # Support both old and new
    summary: str
    data: dict[str, Any] = field(default_factory=dict)  # Bot-specific payload (legacy)
    markdown_report: str = ""  # Full markdown report
    # Extended fields for new bots
    report_md: str = ""  # Alias for markdown_report
    payload: dict[str, Any] = field(default_factory=dict)  # Alias for data
    errors: list[str] = field(default_factory=list)
    timestamp: datetime | None = None

    def __post_init__(self):
        """Sync legacy and new fields."""
        # Sync markdown_report and report_md
        if self.report_md and not self.markdown_report:
            self.markdown_report = self.report_md
        elif self.markdown_report and not self.report_md:
            self.report_md = self.markdown_report

        # Sync data and payload
        if self.payload and not self.data:
            self.data = self.payload
        elif self.data and not self.payload:
            self.payload = self.data

    def to_json(self) -> str:
        d = asdict(self)
        if isinstance(self.status, BotStatus):
            d["status"] = self.status.value
        if self.timestamp:
            d["timestamp"] = self.timestamp.isoformat()
        return json.dumps(d, indent=2, default=str)

    @classmethod
    def failure(cls, bot_name: str, error: str) -> "BotResult":
        return cls(
            bot_name=bot_name,
            status=BotStatus.FAILED,
            summary=f"Failed: {error}",
            markdown_report=f"## ❌ {bot_name} failed\n\n{error}",
            errors=[error],
            timestamp=datetime.utcnow(),
        )


# ── Git Models ───────────────────────────────────────────────────────────────

@dataclass
class CommitInfo:
    """A single commit — shared representation used by all bots."""
    sha: str
    message: str
    author: str
    date: datetime
    files_changed: list[str] = field(default_factory=list)


@dataclass
class CommitGroup:
    """A logical group of commits (by day, author, topic, etc.)."""
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
        seen: set[str] = set()
        files: list[str] = []
        for c in self.commits:
            for f in c.files_changed:
                if f not in seen:
                    seen.add(f)
                    files.append(f)
        return files


# ── Test Models ──────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    """A single test outcome — used by qabot."""
    name: str
    status: str          # "passed", "failed", "error", "skipped"
    duration_ms: float = 0.0
    message: str = ""    # failure message or error traceback


@dataclass
class TestSuiteResult:
    """Full test run output — qabot's internal payload."""
    framework: str
    total: int
    passed: int
    failed: int
    errored: int
    skipped: int
    duration_s: float
    tests: list[TestResult] = field(default_factory=list)
    raw_output: str = ""

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return round(self.passed / self.total * 100, 1)


# ── GitLab Models ────────────────────────────────────────────────────────────

class IssueState(str, Enum):
    OPEN   = "opened"
    CLOSED = "closed"
    ALL    = "all"


class IssuePriority(str, Enum):
    """Derived by project-manager's AI planner — not a GitLab native field."""
    CRITICAL = "critical"
    HIGH     = "high"
    NORMAL   = "normal"
    LOW      = "low"


class EffortSize(str, Enum):
    """AI-estimated effort size for planning."""
    XS = "XS"   # < 1 hour
    S  = "S"    # ~half day
    M  = "M"    # 1 day
    L  = "L"    # 2-3 days
    XL = "XL"   # 1 week+


@dataclass
class Issue:
    """
    A single issue — normalised from the GitLab or GitHub API response.
    All bots work with this type; raw API objects never leave their respective client modules.
    """
    iid: int                          # Project-scoped issue number (#42)
    title: str
    state: IssueState
    author: str
    created_at: datetime
    updated_at: datetime
    labels: list[str] = field(default_factory=list)
    assignees: list[str] = field(default_factory=list)
    milestone: str | None = None
    description: str = ""
    weight: int | None = None         # GitLab EE feature, None on CE/free
    due_date: datetime | None = None
    closed_at: datetime | None = None
    web_url: str = ""

    @property
    def age_days(self) -> int:
        """How many days since this issue was opened."""
        return (datetime.utcnow() - self.created_at.replace(tzinfo=None)).days

    @property
    def is_stale(self, threshold_days: int = 30) -> bool:
        updated = self.updated_at.replace(tzinfo=None)
        return (datetime.utcnow() - updated).days > threshold_days

    @property
    def short_desc(self) -> str:
        """First 200 chars of description, single line."""
        return self.description[:200].replace("\n", " ").strip()


@dataclass
class IssueSet:
    """
    Collection of issues for a project — project-manager's core payload.
    Consumed by AI analyzers and the planner. Works with both GitLab and GitHub issues.
    """
    project_id: str
    project_name: str
    fetched_at: datetime
    issues: list[Issue] = field(default_factory=list)

    @property
    def open_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.state == IssueState.OPEN]

    @property
    def closed_issues(self) -> list[Issue]:
        return [i for i in self.issues if i.state == IssueState.CLOSED]

    @property
    def all_labels(self) -> list[str]:
        seen: set[str] = set()
        labels: list[str] = []
        for issue in self.issues:
            for label in issue.labels:
                if label not in seen:
                    seen.add(label)
                    labels.append(label)
        return labels

    @property
    def all_assignees(self) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for issue in self.issues:
            for a in issue.assignees:
                if a not in seen:
                    seen.add(a)
                    result.append(a)
        return result

    def by_label(self, label: str) -> list[Issue]:
        return [i for i in self.issues if label in i.labels]

    def by_assignee(self, assignee: str) -> list[Issue]:
        return [i for i in self.issues if assignee in i.assignees]

    def stale(self, threshold_days: int = 30) -> list[Issue]:
        return [i for i in self.open_issues if i.is_stale(threshold_days)]


@dataclass
class PlannedIssue:
    """An issue enriched with AI planning metadata."""
    issue: Issue
    priority: IssuePriority
    effort: EffortSize
    rationale: str        # Why this priority/effort was assigned
    week: int | None = None  # Suggested sprint week (1-based)


@dataclass
class WorkloadPlan:
    """
    project-manager's planning output — AI-generated sprint plan.
    Can be consumed by the orchestrator or exported to markdown.
    """
    project_name: str
    total_open: int
    planned_issues: list[PlannedIssue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    summary: str = ""

    @property
    def by_week(self) -> dict[int, list[PlannedIssue]]:
        weeks: dict[int, list[PlannedIssue]] = {}
        for pi in self.planned_issues:
            w = pi.week or 99
            weeks.setdefault(w, []).append(pi)
        return dict(sorted(weeks.items()))


# Backward-compatibility alias
GitLabIssue = Issue
