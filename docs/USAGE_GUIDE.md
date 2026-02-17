# DevBots Usage Guide

A quick-reference guide for using the DevBots orchestrator and dashboard.

## Setup

```bash
# Install everything
uv sync

# Add your API key
cp .env.example .env
# Edit .env → set ANTHROPIC_API_KEY=sk-ant-...
```

## 1. Register a Project

Before running any bot, register your project:

```bash
# Basic (enables gitbot + qabot)
uv run orchestrator add myproject ~/Projects/myproject --desc "My app"

# With GitLab (also enables pmbot for issues/sprints)
uv run orchestrator add myproject ~/Projects/myproject \
  --gitlab-id 12345 \
  --desc "My app"

# With GitHub
uv run orchestrator add myproject ~/Projects/myproject \
  --github-repo owner/repo \
  --desc "My app"
```

Verify it was added:

```bash
uv run orchestrator projects
```

## 2. Run Bots via Chat

Start the interactive chat:

```bash
uv run orchestrator chat
```

Then type natural language requests:

| What you type | What happens |
|---|---|
| `get gitbot report for myproject` | Analyzes recent git commits and generates a summary |
| `suggest tests for myproject` | Suggests tests based on recent code changes |
| `analyze issues for myproject` | Analyzes open issues and finds patterns (needs GitLab/GitHub) |
| `create sprint plan for myproject` | Generates a sprint plan with priorities (needs GitLab/GitHub) |
| `what projects do you know?` | Lists all registered projects |

### Chat Commands

| Command | Action |
|---|---|
| `/projects` | Show registered projects |
| `/add` | Add a project interactively (step-by-step prompts) |
| `/remove` | Remove a project |
| `/exit` | Quit the chat |

## 3. Run Bots Directly (without chat)

You can also run each bot directly from the command line:

```bash
# Git analysis
uv run gitbot ~/Projects/myproject

# Test suggestions
uv run qabot suggest ~/Projects/myproject

# Run tests
uv run qabot run ~/Projects/myproject

# Issue analysis (GitLab)
uv run pmbot analyze --project-id 12345

# Issue analysis (GitHub)
uv run pmbot analyze --github-repo owner/repo

# Sprint planning
uv run pmbot plan --project-id 12345
```

## 4. View Reports

All reports are automatically saved when run through the orchestrator:

```
data/
└── myproject/
    └── reports/
        ├── gitbot/
        │   ├── latest.md           ← always the most recent
        │   └── 2026-02-15-212708.md
        ├── qabot/
        │   └── ...
        └── pmbot/
            └── ...
```

### Using the Dashboard

The dashboard provides a web UI to browse projects and reports:

```bash
# Launch dashboard (generates data + starts server + opens browser)
uv run dashboard

# Custom port
uv run dashboard --port 3000

# Just regenerate data (no server)
uv run dashboard generate
```

Open http://localhost:8080 and navigate to:

- **Dashboard** — Overview with summary stats
- **Projects** — All registered projects with search
- **Bots** — Bot status and report counts
- **Activity** — Chronological feed of all reports
- **Reports** — Filterable report list (by project or bot)

Click any report to view it rendered with full markdown styling.

## 5. Typical Workflow

Here's a common workflow to get a full project status update:

```bash
# 1. Start the chat
uv run orchestrator chat

# 2. Get a git summary
> get gitbot report for myproject

# 3. Get test suggestions
> suggest tests for myproject

# 4. Analyze issues (if GitLab/GitHub configured)
> analyze issues for myproject

# 5. Exit chat
> /exit

# 6. View everything in the dashboard
uv run dashboard
```

## Configuration Reference

### Environment Variables (`.env`)

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `DEVBOTS_MODEL` | No | Default model (default: `claude-haiku-4-5-20251001`) |
| `GITLAB_TOKEN` | For pmbot | GitLab personal access token |
| `GITLAB_URL` | No | GitLab URL (default: `https://gitlab.com`) |
| `GITHUB_TOKEN` | For GitHub | GitHub personal access token |

### Project Registry

Projects are stored in `~/.devbot/projects.json`. You manage them with:

```bash
uv run orchestrator add <name> <path> [options]
uv run orchestrator remove <name>
uv run orchestrator projects
```

## Troubleshooting

**"Project not found"** — Check the project name matches exactly: `uv run orchestrator projects`

**pmbot says "requires GitLab integration"** — Re-add the project with `--gitlab-id`:
```bash
uv run orchestrator add myproject ~/Projects/myproject --gitlab-id 12345
```

**Dashboard shows no data** — Regenerate: `uv run dashboard generate`

**Reports not appearing in dashboard** — Reports are only auto-saved when run through the orchestrator chat, not when running bots directly.
