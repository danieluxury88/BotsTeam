# DevBots Dashboard

The DevBots Dashboard is a web-based interface for browsing projects, viewing bot reports, and triggering new analyses. It is implemented as static HTML/CSS/JS served by a lightweight Python HTTP server — no frameworks, no build tools.

## Quick Start

```bash
# Generate data + start server + open browser
uv run dashboard

# Custom port
uv run dashboard --port 3000

# Regenerate JSON data only (no server)
uv run dashboard generate

# Via orchestrator
uv run orchestrator dashboard
```

Open <http://localhost:8080>

---

## Architecture

```text
Bot reports (data/{project}/reports/{bot}/*.md)          ← team bots
Bot reports (data/personal/{project}/reports/{bot}/*.md) ← personal bots
    ↓  dashboard/generate_data.py  (reads shared/bot_registry.py)
dashboard/data/bots.json        — bot registry (id, name, icon, scope, …)
dashboard/data/projects.json    — project list + activity summary (scope field)
dashboard/data/index.json       — full report catalog
dashboard/data/dashboard.json   — statistics + recent activity
    ↓  Fetch API (vanilla JS)
Browser  (CONFIG.BOTS populated at runtime from bots.json via API.getBots())
    projects.html   — project management (scope badges, dynamic bot modal)
    reports.html    — report browser + inline viewer
    bots.html       — bot status
    activity.html   — chronological feed
    index.html      — summary dashboard
```

### File Layout

```text
dashboard/
├── server.py           # HTTP server + REST API routing
├── api.py              # REST API handlers (CRUD, report generation)
├── generate_data.py    # Scans data/ → writes JSON to dashboard/data/
├── data/               # Generated JSON (git-ignored)
│   ├── bots.json       # Bot registry (generated from shared/bot_registry.py)
│   ├── projects.json
│   ├── index.json
│   └── dashboard.json
├── css/                # Modular CSS (variables, components, responsive)
├── js/                 # JavaScript modules (api, components, dashboard)
└── *.html              # Pages
```

---

## REST API

The Python server (`dashboard/server.py`) exposes both static file serving and a REST API:

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/projects` | List all registered projects |
| `POST` | `/api/projects` | Create a new project |
| `PUT` | `/api/projects/{name}` | Update project fields |
| `DELETE` | `/api/projects/{name}` | Remove a project |
| `POST` | `/api/projects/{name}/reports` | Run selected bots and save reports |
| `GET` | `/api/bots` | List all registered bots (from bot_registry) |
| `GET` | `/reports/{project}/{bot}/{file}` | Serve a team project markdown report |
| `GET` | `/reports/personal/{project}/{bot}/{file}` | Serve a personal project markdown report |

### Report Generation Request

```json
POST /api/projects/uni.li/reports
{
  "bots": ["gitbot", "pmbot"],
  "since": "2026-01-01",
  "until": "2026-02-01",
  "pmbot_mode": "analyze"
}
```

Response:

```json
{
  "results": {
    "gitbot": { "status": "success", "summary": "..." },
    "pmbot":  { "status": "success", "summary": "..." }
  },
  "completed": 2,
  "failed": 0
}
```

---

## Generated JSON Schemas

### `dashboard/data/bots.json`

```json
[
  { "id": "gitbot",     "name": "GitBot",     "icon": "🔍", "description": "Git history analyzer",               "scope": "team",     "requires_field": null },
  { "id": "qabot",      "name": "QABot",      "icon": "🧪", "description": "Test suggestion and execution",      "scope": "team",     "requires_field": null },
  { "id": "pmbot",      "name": "PMBot",      "icon": "📊", "description": "Issue analyzer and sprint planner",  "scope": "team",     "requires_field": null },
  { "id": "journalbot", "name": "JournalBot", "icon": "📓", "description": "Personal journal and notes analyzer","scope": "personal", "requires_field": "notes_dir" },
  { "id": "taskbot",    "name": "TaskBot",    "icon": "✅", "description": "Personal task list analyzer",        "scope": "personal", "requires_field": "task_file" },
  { "id": "habitbot",   "name": "HabitBot",   "icon": "🔄", "description": "Habit and goal tracking analyzer",   "scope": "personal", "requires_field": "habit_file" }
]
```

Generated from `shared/bot_registry.py`. Loaded by the browser at startup via `API.getBots()`, which populates `CONFIG.BOTS`. Adding a bot to `bot_registry.py` automatically makes it appear across the entire dashboard with no frontend changes.

### `dashboard/data/projects.json`

```json
{
  "projects": [
    {
      "id": "uni.li",
      "name": "UniLi",
      "path": "/path/to/project",
      "scope": "team",
      "gitlab_id": "76261915",
      "github_repo": null,
      "last_activity": "2026-02-25T07:55:40",
      "reports_count": 4,
      "bots_run": ["gitbot", "pmbot"]
    },
    {
      "id": "journal",
      "name": "My Journal",
      "path": null,
      "scope": "personal",
      "notes_dir": "/Users/me/notes",
      "task_file": null,
      "habit_file": null,
      "last_activity": "2026-02-24T20:00:00",
      "reports_count": 2,
      "bots_run": ["journalbot"]
    }
  ],
  "last_updated": "2026-02-25T12:00:00Z"
}
```

### `dashboard/data/index.json`

```json
{
  "reports": [
    {
      "id": "pmbot-uni.li-2026-02-25T075540",
      "bot": "pmbot",
      "project_id": "uni.li",
      "timestamp": "2026-02-25T07:55:40",
      "status": "success",
      "summary": "...",
      "path": "reports/uni.li/pmbot/2026-02-25-075540.md",
      "size_bytes": 2048
    }
  ],
  "last_updated": "...",
  "total_reports": 4
}
```

### `dashboard/data/dashboard.json`

```json
{
  "version": "1.0.0",
  "statistics": {
    "total_projects": 3,
    "active_projects": 2,
    "total_reports": 6,
    "total_bots": 6,
    "team_projects": 2,
    "personal_projects": 1
  },
  "recent_activity": [...]
}
```

---

## Features

### Projects Page

- Lists all registered projects — both team and personal — with scope badges (👥 Team / 👤 Personal)
- Search/filter by name
- Add, edit, and delete projects via modal form (writes to `data/projects.json` or `data/personal/projects.json`)
- Per-project report generation: bot checkboxes are rendered dynamically from `CONFIG.BOTS`, filtered by project scope; personal bots are enabled only when the required path field (`notes_dir`, `task_file`, `habit_file`) is configured

### Reports Page

- Filterable list of all reports (by project, by bot)
- Click any report to view it rendered as styled markdown in-page (no page navigation)
- Shows report metadata: bot, project, timestamp, status

### Bots Page

- Status panel for every bot loaded from `data/bots.json` (team + personal)
- Report count and last run timestamp per bot

### Activity Page

- Chronological feed of all bot reports across all projects
- Shows relative timestamps, status indicators, and summaries

### Dashboard (Home)

- Summary statistics (projects, reports, bots run)
- Recent activity snapshot

---

## Design Principles

- **No frameworks** — Pure HTML5, CSS3 (Grid/Flexbox, Variables), vanilla JS
- **No build step** — Serve files directly; edit and refresh
- **Local-first** — All data stays on disk; no external calls from the browser
- **Touch-friendly** — 48px minimum touch targets throughout
- **Dark mode** — System-aware via `prefers-color-scheme`

---

## Development Notes

### Adding a New Bot

Add one entry to `shared/shared/bot_registry.py` — that's it. The bot will automatically appear:

- In `dashboard/data/bots.json` (generated at next `uv run dashboard generate`)
- In the Bots page status panel
- In the report generation modal (filtered by `scope`)
- In the Reports page bot filter dropdown

No changes needed to `api.py`, `config.js`, `generate_data.py`, or any HTML.

```python
# shared/shared/bot_registry.py
BOTS = {
    ...
    "newbot": BotMeta("newbot", "NewBot", "🆕", "Does something useful", "team"),
}
```

### Adding New Project Fields

1. `api.py` — accept the field in POST/PUT handlers
2. `generate_data.py` — include the field in `projects.json` output
3. The project modal form in `projects.html`
