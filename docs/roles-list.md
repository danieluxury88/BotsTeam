# DevBots Roles & Contexts

This document describes the contexts (team vs. personal) and the bot roles planned for each.

---

## Contexts

DevBots supports two contexts that determine which projects and bots are available:

| Context | Scope | Data Location | Description |
| --- | --- | --- | --- |
| **Team** | Shared, code-oriented | `data/{project}/` | Work projects, repos, GitLab/GitHub integrations |
| **Personal** | Private, individual | `data/personal/{project}/` | Personal journals, tasks, habits, side projects |

Context is detected automatically by the orchestrator from user intent — no explicit switching required.

---

## Team Context Roles

These bots analyze code repositories and project management data.

### Requirements Analyst

**Bot:** pmbot (Project Manager)

Connects to GitLab or GitHub to fetch open issues, identify patterns, surface blockers, and summarize team workload. Answers: *"What is the team working on? What is stuck? What's the priority?"*

### Solution Architect

**Bot:** gitbot + qabot (combined)

Analyzes recent git history to understand what changed and why, then suggests tests to validate those changes. Answers: *"What was built recently? Is it tested?"*

### Sprint Planner

**Bot:** pmbot (plan mode)

Takes the current issue backlog and generates a prioritized sprint plan with effort estimates (`XS` → `XL`) for each issue. Answers: *"What should the team work on next sprint?"*

---

## Personal Context Roles

These bots work with personal, non-code data sources (local files, markdown notes, habit logs).

### Journal Analyst

**Bot:** journalbot *(planned)*

Reads a directory of personal markdown notes or journal entries. Sends content to Claude to surface patterns, recurring themes, mood trends, and insights over time.

Data source: a local directory of `.md` files (e.g. `~/Notes/journal/`)

Example prompt: *"How have I been feeling this week? What topics keep coming up?"*

### Task & Productivity Tracker

**Bot:** taskbot *(planned)*

Reads personal task lists in markdown (checkboxes), plain text, or todo.txt format. Analyzes completion rates, overdue items, and recurring blockers.

Data source: a task file or directory (e.g. `~/Notes/tasks.md`)

Example prompt: *"What did I accomplish this week? What's been sitting on my list too long?"*

### Habit & Goal Tracker

**Bot:** habitbot *(planned)*

Reads a structured habit log (CSV, markdown table, or simple daily log). Tracks streaks, identifies consistency patterns, and surfaces which goals need attention.

Data source: a habit log file (e.g. `~/Notes/habits.csv`)

Example prompt: *"How consistent have I been with my habits? Which ones am I falling behind on?"*

### Personal Dev Analyst

**Bot:** gitbot + qabot (personal scope)

Same as the team gitbot/qabot but registered under the personal context. Keeps personal side-project analyses separate from team dashboards and reports.

Data source: a local git repository

Example prompt: *"What did I build on my side project this month?"*

---

## Adding a New Bot Role

To add a new bot to either context:

1. Create `bots/{botname}/` with its own `pyproject.toml`
2. Implement `analyzer.py` with `get_bot_result() → BotResult`
3. Implement `cli.py` with a typer CLI
4. Register in `orchestrator/bot_invoker.py`
5. Add to workspace members in root `pyproject.toml`
6. Set the appropriate default scope (`TEAM` or `PERSONAL`) in the bot's metadata

For personal bots that read local files instead of git repos, use `shared/file_reader.py` *(planned)* as the data source layer instead of `shared/git_reader.py`.

---

## Context Design Reference

See [context-design.md](context-design.md) for the full technical specification of the personal context extension, including data layout, `ProjectScope` enum, registry changes, and orchestrator routing updates.
