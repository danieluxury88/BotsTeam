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
Bot reports (data/{project}/reports/{bot}/*.md)
    ↓  dashboard/generate_data.py
dashboard/data/projects.json    — project list + activity summary
dashboard/data/index.json       — full report catalog
dashboard/data/dashboard.json   — statistics + recent activity
    ↓  Fetch API (vanilla JS)
Browser
    projects.html   — project management
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
| `GET` | `/reports/{project}/{bot}/{file}` | Serve a raw markdown report file |

### Report Generation Request

```json
POST /api/projects/uni.li/reports
{
  "bots": ["gitbot", "pmbot"]
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

### `dashboard/data/projects.json`

```json
{
  "projects": [
    {
      "id": "uni.li",
      "name": "UniLi",
      "path": "/path/to/project",
      "gitlab_id": "76261915",
      "github_repo": null,
      "last_activity": "2026-02-25T07:55:40",
      "reports_count": 4,
      "bots_run": ["gitbot", "pmbot"]
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
    "total_projects": 2,
    "active_projects": 1,
    "total_reports": 4,
    "total_bots": 4
  },
  "recent_activity": [...]
}
```

---

## Features

### Projects Page

- Lists all registered projects with description, integrations (GitLab/GitHub), and last activity
- Search/filter by name
- Add, edit, and delete projects via modal form (writes to `data/projects.json`)
- Per-project report generation: select which bots to run, results shown inline

### Reports Page

- Filterable list of all reports (by project, by bot)
- Click any report to view it rendered as styled markdown in-page (no page navigation)
- Shows report metadata: bot, project, timestamp, status

### Bots Page

- Status panel for each bot (gitbot, qabot, pmbot, orchestrator)
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

When adding a new bot, update `generate_data.py` to recognize the bot name so its reports appear in the dashboard. No frontend changes are needed — the report viewer is generic.

When adding new project fields, update:

1. `api.py` — to accept the field in POST/PUT handlers
2. `generate_data.py` — to include the field in `projects.json` output
3. The project modal form in `projects.html`
