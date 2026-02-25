# Personal Context Extension — Design Specification

This document describes the technical design for extending DevBots to support a **personal context** alongside the existing team context. It covers data layout, model changes, registry changes, orchestrator routing, new bots, and dashboard updates.

---

## Goals

1. Store personal project data separately from team data (`data/personal/`)
2. Personal data never appears in team dashboards or reports, and vice versa
3. The orchestrator detects context from user intent — no explicit switching command needed
4. New personal bots read local files (notes, tasks, habit logs) rather than git repos or issue trackers
5. Backward compatibility — existing team projects and reports are unchanged

---

## Data Layout

```text
data/
├── projects.json           ← team registry (existing, unchanged)
├── personal/
│   ├── projects.json       ← personal registry (new)
│   ├── journal/
│   │   └── reports/
│   │       └── journalbot/
│   │           ├── latest.md
│   │           └── 2026-02-25-120000.md
│   ├── tasks/
│   │   └── reports/taskbot/
│   └── habits/
│       └── reports/habitbot/
├── BotsTeam/               ← team project (existing)
│   └── reports/gitbot/
└── UniLi/                  ← team project (existing)
    └── reports/pmbot/
```

### Key decisions

- Team projects remain at `data/{project}/` — no migration required
- Personal projects live under `data/personal/{project}/`
- Two separate registry files: `data/projects.json` (team) and `data/personal/projects.json` (personal)
- The `data/personal/` directory is also git-ignored (already covered by `data/` gitignore rule)

---

## `shared/models.py` — ProjectScope Enum

Add a scope enum used throughout the system:

```python
from enum import Enum

class ProjectScope(str, Enum):
    TEAM = "team"
    PERSONAL = "personal"
```

No changes to `BotResult` or other models — scope lives at the project registration level, not in individual reports.

---

## `shared/data_manager.py` — Scope-Aware Paths

Update path functions to accept an optional `scope` parameter. Default is `TEAM` for backward compatibility.

### New / changed functions

```python
from shared.models import ProjectScope

def get_personal_root() -> Path:
    """Returns data/personal/"""
    return get_data_root() / "personal"

def get_personal_registry_path() -> Path:
    """Returns data/personal/projects.json"""
    return get_personal_root() / "projects.json"

def get_project_data_dir(project_name: str, scope: ProjectScope = ProjectScope.TEAM) -> Path:
    """
    TEAM:     data/{project_name}/
    PERSONAL: data/personal/{project_name}/
    """
    if scope == ProjectScope.PERSONAL:
        return get_personal_root() / project_name
    return get_data_root() / project_name

def get_reports_dir(
    project_name: str,
    bot: str | None = None,
    scope: ProjectScope = ProjectScope.TEAM,
) -> Path:
    base = get_project_data_dir(project_name, scope) / "reports"
    return base / bot if bot else base

def save_report(
    project_name: str,
    bot: str,
    content: str,
    scope: ProjectScope = ProjectScope.TEAM,
    save_latest: bool = True,
    save_timestamped: bool = True,
) -> None:
    """Saves to the correct scope directory."""
    ...

def ensure_project_structure(
    project_name: str,
    scope: ProjectScope = ProjectScope.TEAM,
) -> None:
    """Creates data/{scope}/{project}/ directory tree."""
    ...
```

All existing callers continue to work unchanged (default scope = TEAM).

---

## `orchestrator/registry.py` — Project with Scope

### Updated `Project` dataclass

```python
@dataclass
class Project:
    name: str
    path: Path                          # For git-based bots; may be None for file-based personal bots
    description: str = ""
    language: str = "python"
    scope: ProjectScope = ProjectScope.TEAM   # NEW

    # Team integrations
    gitlab_project_id: str | None = None
    gitlab_url: str | None = None
    gitlab_token: str | None = None
    github_repo: str | None = None
    github_token: str | None = None

    # Personal bot data sources (new — optional)
    notes_dir: str | None = None        # For journalbot: path to markdown notes directory
    task_file: str | None = None        # For taskbot: path to task list file or directory
    habit_file: str | None = None       # For habitbot: path to habit log file

    @property
    def is_personal(self) -> bool:
        return self.scope == ProjectScope.PERSONAL

    def get_data_dir(self) -> Path:
        return get_project_data_dir(self.name, self.scope)
```

### Updated `ProjectRegistry`

```python
class ProjectRegistry:
    def __init__(
        self,
        registry_file: Path | None = None,
        scope: ProjectScope | None = None,  # None = load both
    ): ...

    def load_projects(self) -> dict[str, Project]:
        """Loads team registry and/or personal registry depending on scope."""
        projects = {}
        if self.scope in (None, ProjectScope.TEAM):
            projects.update(self._load_file(get_registry_path()))
        if self.scope in (None, ProjectScope.PERSONAL):
            projects.update(self._load_file(get_personal_registry_path()))
        return projects

    def add_project(self, name, path, scope=ProjectScope.TEAM, **kwargs) -> Project:
        """Writes to the correct registry file based on scope."""
        registry_file = (
            get_personal_registry_path()
            if scope == ProjectScope.PERSONAL
            else get_registry_path()
        )
        ...

    def list_by_scope(self, scope: ProjectScope) -> list[Project]:
        return [p for p in self.list_projects() if p.scope == scope]
```

### CLI additions

```bash
# Register a personal project
uv run orchestrator add myjournal ~/Notes/journal \
  --scope personal \
  --notes-dir ~/Notes/journal \
  --desc "Daily journal"

# Register personal git side-project
uv run orchestrator add side-project ~/Projects/side \
  --scope personal \
  --desc "My side project"

# List only personal projects
uv run orchestrator projects --scope personal

# List only team projects
uv run orchestrator projects --scope team
```

---

## `orchestrator/bot_invoker.py` — Scope-Aware Routing

Update `invoke_bot()` to pass scope through to `data_manager`:

```python
def invoke_bot(
    bot_name: str,
    project: Project | None = None,
    ...
) -> BotResult:
    scope = project.scope if project else ProjectScope.TEAM

    # Route personal-only bots
    if bot_name == "journalbot":
        return _invoke_journalbot(project)
    if bot_name == "taskbot":
        return _invoke_taskbot(project)
    if bot_name == "habitbot":
        return _invoke_habitbot(project)

    # Existing bots: pass scope to data_manager for correct save path
    result = _invoke_existing_bot(bot_name, project, ...)
    if project and project.name:
        save_report(project.name, bot_name, result.markdown_report, scope=scope)
    return result
```

### Orchestrator chat system prompt — context detection

Add context instructions to the orchestrator's Claude system prompt:

```text
CONTEXT DETECTION:
- Projects are either "team" (code repos, GitLab/GitHub issues) or "personal" (journals, tasks, habits).
- Detect context from the user's phrasing:
  - Personal signals: "my week", "my journal", "how am I doing", "my tasks", "my habits",
    "my side project" → use personal projects
  - Team signals: project names, "issues", "sprint", "commits", "tests" → use team projects
- If ambiguous, list matching projects from both scopes and ask the user to clarify.
- Include "scope" in the JSON action response: {"scope": "personal" | "team", ...}
```

---

## `shared/file_reader.py` — New: Local File Data Source

A new shared module for personal bots that read local files instead of git repos:

```python
"""
file_reader.py — reads local markdown/text/CSV files for personal bots.
Analogous to git_reader.py but for file-based data sources.
"""

@dataclass
class FileEntry:
    path: Path
    modified: datetime
    content: str
    word_count: int

@dataclass
class FileReadResult:
    entries: list[FileEntry]
    total_files: int
    date_range: tuple[datetime, datetime] | None
    errors: list[str]

def read_markdown_files(
    directory: Path,
    since: date | None = None,
    until: date | None = None,
    max_files: int = 50,
) -> FileReadResult:
    """
    Reads .md files from a directory, sorted by modification time.
    Respects since/until date filters.
    """
    ...

def read_task_file(path: Path) -> FileReadResult:
    """
    Reads a task list file. Supports:
    - Markdown checkboxes: - [ ] task / - [x] done
    - todo.txt format
    - Plain text (one task per line)
    """
    ...

def read_csv_file(path: Path) -> FileReadResult:
    """
    Reads a structured CSV file (e.g. habit log).
    Returns entries with date and field columns.
    """
    ...

def format_files_for_llm(entries: list[FileEntry], max_chars: int = 8000) -> str:
    """Formats file contents for Claude, respecting token limits."""
    ...
```

---

## New Personal Bots

All three follow the same `get_bot_result() → BotResult` contract as team bots.

### `bots/journalbot/`

```python
# journalbot/analyzer.py

def get_bot_result(
    notes_dir: str | Path,
    since: date | None = None,
    until: date | None = None,
    model: str | None = None,
    project_name: str | None = None,
    scope: ProjectScope = ProjectScope.PERSONAL,
) -> BotResult:
    """
    Reads markdown notes from notes_dir.
    Asks Claude to surface themes, mood patterns, recurring topics,
    and actionable insights.
    """
    entries = read_markdown_files(notes_dir, since=since, until=until)
    formatted = format_files_for_llm(entries.entries)
    report = chat(SYSTEM_PROMPT, formatted, bot_env_key="JOURNALBOT_MODEL")
    save_report(project_name, "journalbot", report, scope=scope)
    return BotResult(bot_name="journalbot", status=BotStatus.SUCCESS, ...)
```

**CLI:**

```bash
uv run journalbot ~/Notes/journal
uv run journalbot ~/Notes/journal --since 2026-02-01 --until 2026-02-28
```

**System prompt focus:** themes, mood patterns, key decisions made, topics to revisit, energy levels, recurring concerns.

---

### `bots/taskbot/`

```python
# taskbot/analyzer.py

def get_bot_result(
    task_source: str | Path,   # file or directory
    model: str | None = None,
    project_name: str | None = None,
    scope: ProjectScope = ProjectScope.PERSONAL,
) -> BotResult:
    """
    Reads task lists. Asks Claude to summarize completion rate,
    identify overdue or stale items, and suggest priorities.
    """
    ...
```

**CLI:**

```bash
uv run taskbot ~/Notes/tasks.md
uv run taskbot ~/Notes/tasks/    # reads all .md files in directory
```

**System prompt focus:** completed vs pending ratio, items older than 14 days, recurring uncompleted tasks, suggested priority order for open items.

---

### `bots/habitbot/`

```python
# habitbot/analyzer.py

def get_bot_result(
    habit_source: str | Path,   # CSV, markdown table, or text log
    since: date | None = None,
    until: date | None = None,
    model: str | None = None,
    project_name: str | None = None,
    scope: ProjectScope = ProjectScope.PERSONAL,
) -> BotResult:
    """
    Reads a habit tracking file. Asks Claude to surface streaks,
    consistency rates, and which habits need attention.
    """
    ...
```

**CLI:**

```bash
uv run habitbot ~/Notes/habits.csv
uv run habitbot ~/Notes/habits.md --since 2026-02-01
```

**System prompt focus:** streak lengths, consistency percentage per habit, habits improving vs declining, motivational summary.

---

## Dashboard Updates

### `generate_data.py`

Update to scan both registries and both data roots:

```python
def load_projects(self):
    # Existing: load data/projects.json
    team_projects = self._load_registry(get_registry_path(), scope="team")
    # New: load data/personal/projects.json
    personal_projects = self._load_registry(get_personal_registry_path(), scope="personal")
    return team_projects + personal_projects

def scan_reports(self, project: dict):
    # Use correct root based on project["scope"]
    scope = project.get("scope", "team")
    if scope == "personal":
        reports_root = get_personal_root() / project["name"] / "reports"
    else:
        reports_root = get_data_root() / project["name"] / "reports"
    ...
```

Add `scope` field to the projects JSON output so the frontend can filter.

### Frontend (`projects.html`, `reports.html`)

Add a context filter tab/toggle:

```text
[ All ]  [ Team ]  [ Personal ]
```

- Filters project cards and report list by `scope` field in JSON
- Personal projects shown with a distinct visual indicator
- Personal reports not mixed into team activity feed by default

---

## Implementation Order

| Step | Component | Effort |
| --- | --- | --- |
| 1 | Add `ProjectScope` to `shared/models.py` | XS |
| 2 | Update `shared/data_manager.py` with scope-aware paths | S |
| 3 | Update `orchestrator/registry.py` — `Project` scope field + dual registry loading | S |
| 4 | Update `orchestrator/cli.py` — `--scope` flag on `add` and `projects` commands | S |
| 5 | Create `shared/file_reader.py` | M |
| 6 | Create `bots/journalbot/` | M |
| 7 | Create `bots/taskbot/` | M |
| 8 | Create `bots/habitbot/` | M |
| 9 | Update `orchestrator/bot_invoker.py` — scope-aware routing + new bots | S |
| 10 | Update orchestrator chat system prompt — personal context detection | S |
| 11 | Update `dashboard/generate_data.py` — scan personal root | S |
| 12 | Add context filter to dashboard frontend | M |

Steps 1–4 form the foundation and can be done without any new bots. Steps 5–8 are independent of each other and can be parallelized.

---

## Non-Goals (out of scope for this design)

- Multi-user access control (this is a single-user local tool)
- Encrypting personal data at rest
- Syncing personal data to a remote server
- Role-based permissions (not needed for personal vs team separation)
