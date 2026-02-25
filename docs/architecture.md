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
│   ├── project_manager/        # GitLab/GitHub issue analyzer & sprint planner
│   ├── orchestrator/           # Conversational bot router + project registry
│   └── dashboard/              # Standalone dashboard CLI (uv run dashboard)
├── dashboard/                  # Web dashboard (static HTML/CSS/JS + Python server)
├── data/                       # Auto-saved reports and project registry (git-ignored)
│   ├── projects.json           # Project registry
│   └── {project_name}/
│       ├── reports/{bot}/      # latest.md + timestamped archives
│       └── cache/
└── docs/                       # Architecture docs, PlantUML diagrams
```

---

## Shared Library (`shared/`)

The `shared` package is the foundation for all bots. It provides:

### `models.py` — Data Contracts

All inter-bot data is typed with dataclasses:

| Model | Description |
| --- | --- |
| `BotResult` | Universal bot output: `bot_name`, `status`, `summary`, `markdown_report`, `data` |
| `BotStatus` | Enum: `SUCCESS`, `PARTIAL`, `FAILED`, `SKIPPED`, `ERROR`, `WARNING` |
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

### `data_manager.py` — Report Storage

```python
get_data_root() → Path                          # BotsTeam/data/
get_registry_path() → Path                      # BotsTeam/data/projects.json
get_project_data_dir(project_name) → Path       # data/{project}/
get_reports_dir(project_name, bot=None) → Path  # data/{project}/reports/{bot}/
save_report(project_name, bot, content, save_latest=True, save_timestamped=True)
list_reports(project_name, bot=None) → list[Path]
```

Report naming:

- `data/{project}/reports/{bot}/latest.md` — always current
- `data/{project}/reports/{bot}/2026-02-25-075540.md` — timestamped archive

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

### Orchestrator — Conversational Bot Router

**Role:** Conversational interface that understands natural language, routes requests to the right bot, and manages the project registry.

**Key components:**

- `registry.py` — `ProjectRegistry` and `Project` dataclasses; loads/saves `data/projects.json`
- `bot_invoker.py` — `invoke_bot(bot_name, project, **params) → BotResult`; routes to gitbot/qabot/pmbot
- `cli.py` — Interactive chat loop, project CRUD, dashboard launcher

**CLI:**

```bash
uv run orchestrator chat                    # Interactive conversational loop
uv run orchestrator add myproject /path [--gitlab-id N] [--github-repo owner/repo]
uv run orchestrator projects                # List all registered projects
uv run orchestrator dashboard [--port N]    # Launch web dashboard
```

**Chat examples:**

```text
> get gitbot report for uni.li
> analyze issues for myproject
> create sprint plan for uni.li
> what projects do you know?
```

**Bot invocation flow:**

1. User message → Claude parses intent → JSON `{action, bot, project, params}`
2. `invoke_bot()` resolves project from registry
3. Bot runs, result auto-saved if `project.name` is set
4. Report displayed via Rich Markdown

#### Project Registry Schema (`data/projects.json`)

```json
{
  "myproject": {
    "name": "myproject",
    "path": "/absolute/path/to/project",
    "description": "Optional description",
    "language": "python",
    "gitlab_project_id": "12345",
    "gitlab_url": "https://gitlab.com",
    "gitlab_token": null,
    "github_repo": "owner/repo",
    "github_token": null
  }
}
```

`Project` class conveniences:

- `project.has_gitlab()` / `project.has_github()`
- `project.get_gitlab_token()` — per-project token, falls back to global `Config`
- `project.get_data_dir()` → `data/{project_name}/`

---

### Dashboard — Web-Based Visualization

**Role:** Static HTML/CSS/JS web interface for browsing projects and bot reports. Served by a Python HTTP server with a small REST API.

**Data pipeline:**

```text
Bot reports in data/{project}/reports/{bot}/
    ↓  generate_data.py
dashboard/data/projects.json   — project metadata + activity summary
dashboard/data/index.json      — complete report catalog
dashboard/data/dashboard.json  — statistics + recent activity
    ↓  Fetch API
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
GET    /api/projects                        — List all projects
POST   /api/projects                        — Create project
PUT    /api/projects/{name}                 — Update project
DELETE /api/projects/{name}                 — Remove project
POST   /api/projects/{name}/reports         — Generate bot reports for a project
GET    /reports/{project}/{bot}/{filename}  — Serve raw markdown report
```

**Features implemented:**

- Project list with search and CRUD (add/edit/delete via modal)
- Per-project report generation (select bots, runs inline)
- In-page markdown report viewer with styled rendering
- Activity feed (chronological report history)
- Bot status panel
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

## Planned: Personal Context Extension

The current architecture is **team-oriented** — all bots are code/issue focused, the registry is flat, and there is no notion of scope or privacy.

The planned extension adds a **personal context** layer to support personal bots (journal, tasks, habits) alongside team bots, with clear data separation.

See [context-design.md](context-design.md) for the full design specification.

### Summary of planned changes

| Layer | Change |
| --- | --- |
| `shared/models.py` | Add `ProjectScope` enum (`PERSONAL`, `TEAM`) |
| `shared/data_manager.py` | Scope-aware paths: personal → `data/personal/{project}/` |
| `shared/file_reader.py` | New: reads local markdown/text/CSV for non-git bots |
| `orchestrator/registry.py` | `Project` gets `scope` field; `ProjectRegistry` loads both registries |
| `orchestrator/bot_invoker.py` | Route by scope; context detected from user intent |
| New bots | `journalbot`, `taskbot`, `habitbot` |
| Dashboard | Context filter (All / Personal / Team) |
