# DevBots Architecture

## Overview

DevBots is a Python monorepo of AI-powered development bots. Each bot is an independent package that shares common infrastructure from the `shared` library. All bots use **Claude (Anthropic)** for AI analysis and expose a uniform `BotResult` contract so they can be composed and orchestrated.

> For visual representations see the [PlantUML diagrams](DIAGRAMS.md).

---

## Repository Structure

```text
BotsTeam/
├── shared/                     # Core library used by all bots
├── bots/
│   ├── gitbot/                 # Git history analyzer
│   ├── qabot/                  # Test suggestion & execution
│   ├── project_manager/        # GitLab/GitHub issue analyzer & sprint planner (pmbot)
│   ├── journalbot/             # Personal journal/notes analyzer
│   ├── taskbot/                # Personal task list analyzer
│   ├── habitbot/               # Personal habit tracking analyzer
│   ├── orchestrator/           # Conversational bot router + project registry
│   └── dashboard/              # Standalone dashboard CLI (uv run dashboard)
├── dashboard/                  # Web dashboard (static HTML/CSS/JS + Python server)
├── data/                       # Auto-saved reports and project registry (git-ignored)
│   ├── projects.json           # Team project registry
│   ├── {project_name}/
│   │   ├── reports/{bot}/      # latest.md + timestamped archives
│   │   └── cache/
│   └── personal/               # Personal project data
│       ├── projects.json       # Personal project registry
│       └── {project_name}/
│           └── reports/{bot}/  # Personal bot reports
└── docs/                       # Architecture docs, PlantUML diagrams
```

---

## Shared Library (`shared/`)

The `shared` package is the foundation for all bots. It provides:

### `bot_registry.py` — Bot Metadata Registry

Single source of truth for all bot metadata. When adding a new bot, add one entry here — the dashboard, API validator, and data generator all pick it up automatically.

```python
@dataclass(frozen=True)
class BotMeta:
    id: str           # e.g. "gitbot"
    name: str         # e.g. "GitBot"
    icon: str         # emoji
    description: str
    scope: BotScope   # "team" | "personal" | "both"
    requires_field: str | None  # personal bots: "notes_dir", "task_file", "habit_file"
```

Helper functions: `team_bots()`, `personal_bots()`, `all_bots()`, `to_json()`.

### `models.py` — Data Contracts

All inter-bot data is typed with dataclasses:

| Model | Description |
| --- | --- |
| `BotResult` | Universal bot output: `bot_name`, `status`, `summary`, `markdown_report`, `data` |
| `BotStatus` | Enum: `SUCCESS`, `PARTIAL`, `FAILED`, `SKIPPED`, `ERROR`, `WARNING` |
| `ProjectScope` | Enum: `TEAM`, `PERSONAL` — controls data directory and bot routing |
| `ChangeSet` | gitbot output; consumed by qabot and orchestrator |
| `CommitInfo`, `CommitGroup` | Git commit structures |
| `Issue`, `IssueSet` | Platform-agnostic issue representation (GitLab + GitHub normalize to these) |
| `PlannedIssue`, `WorkloadPlan` | pmbot sprint planning output |
| `TestResult`, `TestSuiteResult` | qabot test execution data |
| `RepoContext` | Repo metadata: path, branch, language, test framework |

Key patterns:

- `BotResult.failure(bot_name, message)` — convenience constructor for errors
- `BotResult.to_json()` — serialization
- `IssueSet` has computed properties: `open_issues`, `stale()`, `by_label()`

### `config.py` — Environment Configuration

Loads `.env` and exposes typed accessors:

```python
Config.gitlab_token()       # GITLAB_TOKEN or GITLAB_PRIVATE_TOKEN
Config.gitlab_url()         # GITLAB_URL (default: https://gitlab.com)
Config.github_token()       # GITHUB_TOKEN
Config.github_base_url()    # GITHUB_API_URL (default: https://api.github.com)
```

Environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | required | Claude API access |
| `DEVBOTS_MODEL` | `claude-haiku-4-5-20251001` | Default model for all bots |
| `GITBOT_MODEL` / `QABOT_MODEL` / `ISSUEBOT_MODEL` | — | Per-bot model overrides |
| `DEVBOTS_MAX_COMMITS` | 100 | Git commit limit |
| `GITLAB_TOKEN` | — | Global GitLab token (fallback) |
| `GITLAB_URL` | `https://gitlab.com` | GitLab instance URL |
| `GITHUB_TOKEN` | — | Global GitHub token (fallback) |
| `GITHUB_API_URL` | `https://api.github.com` | GitHub API URL (GitHub Enterprise) |

### `llm.py` — Claude Client

```python
create_client() → anthropic.Anthropic
chat(system, user, max_tokens=1024, bot_env_key=None) → str
```

`bot_env_key` (e.g. `"ISSUEBOT_MODEL"`) enables per-bot model selection.

### `git_reader.py` — Git Utilities

```python
read_commits(repo_path, branch="HEAD", max_commits=300, since=None, until=None) → ReadCommitsResult
filter_commits(commits) → FilterResult       # removes merges, bot commits, duplicates
group_commits_auto(commits) → CommitGroup[]  # detects best grouping strategy
group_commits_by_day(commits) → CommitGroup[]
group_commits_by_author(commits) → CommitGroup[]
format_groups_for_llm(groups) → str
```

### `file_reader.py` — Local File Reader

Reads local markdown directories, task files, and CSV/markdown habit logs for personal bots. Analogous to `git_reader.py` for git-based bots.

```python
read_markdown_files(directory, since, until, max_files) → FileReadResult
read_task_file(path) → FileReadResult
read_habit_file(path) → FileReadResult          # supports .csv and .md
format_files_for_llm(entries, max_chars) → str
```

### `data_manager.py` — Report Storage

Supports both team and personal scopes via `ProjectScope`:

```python
get_data_root() → Path                                    # BotsTeam/data/
get_personal_root() → Path                                # BotsTeam/data/personal/
get_registry_path() → Path                                # data/projects.json
get_personal_registry_path() → Path                       # data/personal/projects.json
get_project_data_dir(project_name, scope) → Path          # data/{project}/ or data/personal/{project}/
get_reports_dir(project_name, bot, scope) → Path
save_report(project_name, bot, content, scope=TEAM, ...)
list_reports(project_name, bot, scope) → list[Path]
```

Report naming:

- `data/{project}/reports/{bot}/latest.md` — always current
- `data/{project}/reports/{bot}/2026-02-25-075540.md` — timestamped archive
- Personal reports follow the same pattern under `data/personal/`

### `gitlab_client.py` / `github_client.py` — Issue Clients

Both normalize platform API responses into `Issue` / `IssueSet`:

```python
GitLabClient(token=None, url=None).fetch_issues(project_id, state, max_issues) → IssueSet
GitHubClient(token=None, base_url=None).fetch_issues(repo, state, max_issues) → IssueSet
```

Raw API objects never leave the client modules. All consumers work with `Issue`.

---

## Bots

### GitBot — Git History Analyzer

**Role:** Reads recent commits, groups them, and sends to Claude for an AI-powered summary.

**Entry point:**

```python
get_bot_result(repo_path, branch="HEAD", max_commits=300, model=None,
               project_name=None, since=None, until=None) → BotResult
```

**CLI:**

```bash
uv run gitbot /path/to/repo [--max-commits N] [--branch BRANCH] [--since DATE] [--until DATE]
```

**Data flow:** `repo_path` → `CommitInfo[]` → `CommitGroup[]` → Claude → `BotResult` (payload: `ChangeSet`)

Auto-saves report to `data/{project}/reports/gitbot/` when `project_name` is provided.

---

### QABot — Test Suggestion & Execution

**Role:** Analyzes what changed in recent commits and suggests tests; can run existing test suites.

**Entry point:**

```python
get_bot_result(repo_path, max_commits=100, model=None, project_name=None) → BotResult
```

**CLI:**

```bash
uv run qabot suggest /path/to/repo   # Suggest tests only
uv run qabot run /path/to/repo       # Run existing tests
uv run qabot full /path/to/repo      # Suggest + run
```

**Data flow:** `repo_path` → `CommitInfo[]` → Claude → `QAAnalysisResult` → `BotResult`

Can also consume a `ChangeSet` from gitbot directly (avoiding redundant git reads).

---

### Project Manager (pmbot) — Issue Analyzer & Sprint Planner

**Role:** Fetches open issues from GitLab or GitHub, analyzes patterns, and generates sprint plans.

**Entry points:**

```python
analyze(issue_set: IssueSet) → BotResult   # Project health, patterns, recommendations
plan(issue_set: IssueSet) → BotResult      # Prioritized sprint workload with effort estimates
```

**CLI:**

```bash
uv run pmbot analyze --project-id 12345           # GitLab
uv run pmbot analyze --github-repo owner/repo     # GitHub
uv run pmbot plan --project-id 12345
uv run pmbot list --project-id 12345 --state opened --labels bug
```

**Data flow:** `project_id` or `github_repo` → GitLab/GitHub API → `Issue[]` → `IssueSet` → Claude → `BotResult` (payload: `WorkloadPlan`)

---

### JournalBot — Personal Notes Analyzer

**Role:** Reads markdown journal/notes directories and generates AI insights on themes, patterns, and progress.

**Entry point:**

```python
get_bot_result(notes_dir, since, until, max_files, model, project_name, scope) → BotResult
```

**CLI:** `uv run journalbot ~/Notes/journal [--since DATE] [--until DATE] [--project NAME]`

---

### TaskBot — Personal Task Analyzer

**Role:** Reads markdown task/todo files and generates productivity insights on completion rates, blockers, and priorities.

**Entry point:**

```python
get_bot_result(task_source, model, project_name, scope) → BotResult
```

**CLI:** `uv run taskbot ~/Notes/tasks.md [--project NAME]`

---

### HabitBot — Habit Tracking Analyzer

**Role:** Reads habit tracking logs (CSV or markdown) and surfaces consistency patterns, streaks, and recommendations.

**Entry point:**

```python
get_bot_result(habit_source, since, until, model, project_name, scope) → BotResult
```

**CLI:** `uv run habitbot ~/Notes/habits.csv [--since DATE] [--until DATE] [--project NAME]`

---

### Orchestrator — Conversational Bot Router

**Role:** Conversational interface that understands natural language, routes requests to the right bot, manages the project registry, and detects team vs personal context automatically.

**Key components:**

- `registry.py` — `ProjectRegistry` and `Project` dataclasses; loads both `data/projects.json` (team) and `data/personal/projects.json` (personal). `Project` has `scope`, `notes_dir`, `task_file`, `habit_file` fields.
- `bot_invoker.py` — `invoke_bot(bot_name, project, **params) → BotResult`; routes to all bots including personal ones
- `cli.py` — Interactive chat loop, project CRUD (with scope), dashboard launcher

**CLI:**

```bash
uv run orchestrator chat                    # Interactive conversational loop
uv run orchestrator add myproject /path [--scope personal] [--notes-dir ~/Notes]
uv run orchestrator projects                # List all registered projects (team + personal)
uv run orchestrator dashboard [--port N]    # Launch web dashboard
```

**Chat examples:**

```text
> get gitbot report for uni.li
> analyze my journal for this month    # → journalbot (personal context detected)
> how am I doing on my habits?         # → habitbot
> analyze issues for uni.li
```

**Bot invocation flow:**

1. User message → Claude parses intent + detects scope → JSON `{action, bot, project, params}`
2. `invoke_bot()` resolves project from registry (team or personal)
3. Bot runs, result auto-saved to correct scoped directory
4. Report displayed via Rich Markdown

#### Project Registry Schemas

Team (`data/projects.json`):

```json
{
  "myproject": {
    "name": "myproject",
    "path": "/absolute/path",
    "scope": "team",
    "gitlab_project_id": "12345",
    "github_repo": "owner/repo"
  }
}
```

Personal (`data/personal/projects.json`):

```json
{
  "mylife": {
    "name": "mylife",
    "path": "/home/user/notes",
    "scope": "personal",
    "notes_dir": "/home/user/notes/journal",
    "task_file": "/home/user/notes/tasks.md",
    "habit_file": "/home/user/notes/habits.csv"
  }
}
```

`Project` class conveniences:

- `project.has_gitlab()` / `project.has_github()`
- `project.get_gitlab_token()` — per-project token, falls back to global `Config`
- `project.scope` — `ProjectScope.TEAM` or `ProjectScope.PERSONAL`

---

### Dashboard — Web-Based Visualization

**Role:** Static HTML/CSS/JS web interface for browsing all projects (team and personal) and bot reports. Served by a Python HTTP server with a small REST API.

**Data pipeline:**

```text
Team:     data/{project}/reports/{bot}/
Personal: data/personal/{project}/reports/{bot}/
    ↓  generate_data.py  (reads shared.bot_registry for bot list)
dashboard/data/bots.json       — bot metadata from registry
dashboard/data/projects.json   — all projects (team + personal) + activity summary
dashboard/data/index.json      — complete report catalog (scoped)
dashboard/data/dashboard.json  — statistics + recent activity
    ↓  Fetch API (CONFIG.BOTS loaded at runtime from bots.json)
Browser (projects.html, reports.html, activity.html, bots.html)
```

**Launching:**

```bash
uv run dashboard                # Generates data + starts server + opens browser
uv run dashboard --port 3000    # Custom port
uv run dashboard generate       # Regenerate JSON only (no server)
uv run orchestrator dashboard   # Same, via orchestrator CLI
```

**REST API** (served by `dashboard/server.py`):

```text
GET    /api/projects                              — List all projects
POST   /api/projects                              — Create project
PUT    /api/projects/{name}                       — Update project
DELETE /api/projects/{name}                       — Remove project
POST   /api/projects/{name}/reports               — Generate bot reports for a project
GET    /reports/{project}/{bot}/{filename}         — Serve team report markdown
GET    /reports/personal/{project}/{bot}/{filename} — Serve personal report markdown
```

**Features:**

- Project list with search, CRUD, and scope badges (👥 Team / 👤 Personal)
- Report generation modal adapts to project scope: team projects show team bots, personal projects show personal bots with their configured data sources
- In-page markdown report viewer with styled rendering
- Activity feed (chronological report history across all scopes)
- Bot status panel (all 7 bots)
- Dark mode (system-aware)
- Touch-friendly (48px+ targets)

---

## Bot Contract

Every bot follows this uniform interface:

```python
# Required
def get_bot_result(...) -> BotResult: ...

# BotResult fields
bot_name: str
status: BotStatus          # SUCCESS, ERROR, WARNING, etc.
summary: str               # One-line human-readable summary
markdown_report: str       # Full formatted report (alias: report_md)
data: dict | None          # Bot-specific payload (alias: payload)
```

This contract enables:

- **Composition**: gitbot's `ChangeSet` can feed directly into qabot
- **Orchestration**: orchestrator invokes any bot via `invoke_bot()`
- **Storage**: `data_manager.save_report()` works for any bot
- **Dashboard**: report viewer renders any bot's markdown output

---

## Data Flow Patterns

### Pattern 1 — Single Bot (CLI)

```text
User: uv run gitbot /repo
  → gitbot/cli.py reads args
  → gitbot/analyzer.get_bot_result()
  → save to data/{project}/reports/gitbot/ (if project_name given)
  → display via Rich
```

### Pattern 2 — Multi-Bot via Orchestrator (Chat)

```text
User: "get qabot report for uni.li"
  → orchestrator/cli.py parse_user_request() via Claude
  → JSON: {action: invoke_bot, bot: qabot, project: uni.li}
  → bot_invoker.invoke_bot("qabot", project=uni_li_project)
  → qabot/analyzer.get_bot_result()
  → auto-saved to data/uni.li/reports/qabot/
  → displayed in chat loop
```

### Pattern 3 — Dashboard API-Triggered Report

```text
Dashboard UI: POST /api/projects/uni.li/reports {bots: [gitbot, pmbot]}
  → api.py:generate_reports()
  → invoke_bot() for each bot
  → reports auto-saved
  → generate_data.py regenerates dashboard JSON
  → response: {results: {...}, completed: 2, failed: 0}
```

---

## Personal Context Extension

The architecture supports both **team** and **personal** contexts with clear data separation. Personal bots read local files rather than git repos or issue trackers.

See [context-design.md](context-design.md) for the original design specification.

### Implemented changes

| Layer | Change |
| --- | --- |
| `shared/bot_registry.py` | New: single source of truth for all bot metadata and scopes |
| `shared/models.py` | `ProjectScope` enum (`TEAM`, `PERSONAL`) |
| `shared/data_manager.py` | Scope-aware paths: personal → `data/personal/{project}/` |
| `shared/file_reader.py` | New: reads local markdown dirs, task files, CSV habit logs |
| `orchestrator/registry.py` | `Project` gets `scope`, `notes_dir`, `task_file`, `habit_file`; loads both registries |
| `orchestrator/bot_invoker.py` | Routes to journalbot, taskbot, habitbot; passes scope through |
| `orchestrator/cli.py` | `--scope` flag; intent detection for personal vs team context |
| New bots | `journalbot`, `taskbot`, `habitbot` |
| Dashboard | Scope badges; personal report paths; bot modal adapts to scope; bot list from registry |
