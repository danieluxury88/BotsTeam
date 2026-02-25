# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DevBots is a Python monorepo of AI-powered development bots that analyze code, suggest tests, manage issues (GitLab & GitHub), and orchestrate workflows using Claude (Anthropic). It uses **uv** as the package manager with a workspace layout and **hatchling** as the build backend.

## Common Commands

```bash
uv sync                          # Install all dependencies (workspace-wide)
uv run pytest                    # Run tests
uv run ruff check .              # Lint
uv run ruff check --fix .        # Lint with auto-fix

# Run individual bots
uv run gitbot /path/to/repo      # Analyze git history
uv run qabot suggest /path/to/repo  # Suggest tests
uv run qabot run /path/to/repo   # Execute tests
uv run pmbot analyze --project-id ID  # Analyze GitLab issues
uv run pmbot analyze --github-repo owner/repo  # Analyze GitHub issues
uv run orchestrator chat         # Interactive multi-bot chat
uv run dashboard                 # Launch web dashboard (standalone CLI)
uv run dashboard --port 3000     # Custom port
uv run dashboard generate        # Regenerate data only (no server)
uv run orchestrator dashboard    # Launch web dashboard (via orchestrator)
```

## Architecture

**Workspace packages** (each has its own `pyproject.toml`):

- `shared/` — Core library: config, Anthropic client factory, data models (`BotResult`, `ChangeSet`, `IssueSet`, `Issue`, `ProjectScope`), git reader, file reader, GitLab/GitHub clients, data manager, **bot registry**
- `bots/gitbot/` — Git history analyzer (groups commits, sends to Claude for summary)
- `bots/qabot/` — Test suggestion and execution (detects pytest/unittest, suggests tests from recent changes)
- `bots/project_manager/` — Issue analyzer and sprint planner, supports GitLab and GitHub (pmbot)
- `bots/journalbot/` — Personal journal/notes analyzer (reads local markdown dirs)
- `bots/taskbot/` — Personal task list analyzer (reads markdown todo files)
- `bots/habitbot/` — Personal habit tracking analyzer (reads CSV/markdown habit logs)
- `bots/orchestrator/` — Conversational interface that routes natural language to the appropriate bot

**Key pattern**: Every bot exposes a `get_bot_result()` function returning a `BotResult` dataclass (defined in `shared/models.py`). This uniform contract enables bot composition — e.g., gitbot's `ChangeSet` feeds into qabot's analysis.

**CLI framework**: All CLIs use **typer** with **rich** for terminal output.

**Issue models**: The `Issue` dataclass (`shared/models.py`) is platform-agnostic — both `gitlab_client.py` and `github_client.py` normalize their API responses into `Issue`/`IssueSet`. The legacy `GitLabIssue` alias still exists for backward compatibility.

**Bot registry** (`shared/bot_registry.py`): Single source of truth for all bot metadata (id, name, icon, description, scope, requires_field). The dashboard, API, and data generator all derive their bot lists from here automatically. Adding a new bot requires only one entry in this file plus bot code and routing in `bot_invoker.py`.

**Bot routing** (orchestrator): Claude parses user intent and dispatches to the correct bot via `bot_invoker.py`. Projects are registered in `data/projects.json` (team) and `data/personal/projects.json` (personal) with paths, GitLab/GitHub IDs, and optional per-project tokens.

**Data storage**: Reports auto-save to `data/{project}/reports/{botname}/` (team) or `data/personal/{project}/reports/{botname}/` (personal) with both `latest.md` and timestamped copies. The `data/` directory is git-ignored.

**Personal context** (`ProjectScope`): Projects have a `scope` field (`TEAM` or `PERSONAL`). Personal projects use file-based data sources (`notes_dir`, `task_file`, `habit_file`) instead of git repos or issue trackers. The orchestrator detects context from user phrasing.

**Dashboard** (`dashboard/`): A static HTML/CSS/JS web interface served via a simple Python HTTP server. `generate_data.py` reads both team and personal registries, scans all report directories, and writes four JSON files (`dashboard/data/{bots,projects,index,dashboard}.json`) that the frontend loads via fetch. Bot list is loaded dynamically from `bots.json` — no frontend changes needed when adding bots. No framework dependencies.

## Configuration

Environment variables loaded from `.env` (see `.env.example`):
- `ANTHROPIC_API_KEY` (required)
- `DEVBOTS_MODEL` — default Claude model (defaults to claude-haiku-4-5-20251001)
- Per-bot overrides: `GITBOT_MODEL`, `QABOT_MODEL`, `ISSUEBOT_MODEL`, `JOURNALBOT_MODEL`, `TASKBOT_MODEL`, `HABITBOT_MODEL`
- `GITLAB_TOKEN`, `GITLAB_URL` for GitLab integration
- `GITHUB_TOKEN`, `GITHUB_API_URL` for GitHub integration (supports GitHub Enterprise)

## Adding a New Bot

1. Create `bots/newbot/` with its own `pyproject.toml` depending on `shared`
2. Implement `analyzer.py` with a `get_bot_result()` returning `BotResult`
3. Implement `cli.py` using typer
4. Add ONE entry to `shared/shared/bot_registry.py` — this automatically updates the dashboard, API validation, and data generator
5. Add routing logic to `orchestrator/bot_invoker.py`
6. The root `pyproject.toml` uses `members = ["shared", "bots/*"]` glob — no workspace file change needed
