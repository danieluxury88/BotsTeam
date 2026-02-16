# DevBots Architecture

## Overview

DevBots is a monorepo containing AI-powered development automation tools ("bots") that share common infrastructure.

> **📊 Visual Diagrams:** For a visual understanding of the architecture, see the [PlantUML diagrams](DIAGRAMS.md):
> - [System Overview](system-overview.puml) - High-level component view
> - [Bot Architecture](bot-architecture.puml) - Detailed component structure
> - [Data Flow](data-flow.puml) - How data moves through the system
> - [Bot Interactions](bot-interactions.puml) - API contracts and invocation patterns

## Structure

```
BotsTeam/
├── shared/              # Shared utilities and contracts
├── bots/                # Individual bot implementations
│   ├── gitbot/          # Git history analyzer
│   ├── qabot/           # Test suggestion and execution
│   ├── project_manager/ # GitLab/GitHub issue analyzer and sprint planner
│   └── orchestrator/    # Conversational bot orchestrator
├── docs/                # Documentation
│   ├── *.puml           # PlantUML architecture diagrams
│   └── DIAGRAMS.md      # Diagram documentation
└── data/                # Auto-generated reports (git-ignored)
```

## Shared Library

The `shared` package provides:

- **config.py**: Environment configuration and .env loading
- **llm.py**: Claude/Anthropic client factory
- **models.py**: Bot collaboration contracts (BotResult, ChangeSet, Issue, IssueSet, WorkloadPlan)
- **git_reader.py**: Git repository reading utilities
- **data_manager.py**: Report and data storage management
- **gitlab_client.py**: GitLab API client (normalizes to Issue model)
- **github_client.py**: GitHub API client (normalizes to Issue model)

## Bot Contract

All bots return a `BotResult` with:
- `bot_name`: Identifier
- `status`: "success" | "error" | "warning"
- `summary`: Human-readable summary
- `data`: Bot-specific payload
- `markdown_report`: Full formatted report

This enables bot composition and orchestration.

## Current Bots

### GitBot
Analyzes git history and generates AI-powered summaries using Claude.

**Usage:**
```bash
uv run --directory bots/gitbot gitbot /path/to/repo
```

**Programmatic API:**
```python
from gitbot.analyzer import get_bot_result, get_changeset
result = get_bot_result("/path/to/repo", max_commits=100)
changeset = get_changeset("/path/to/repo")
```

### QABot
Suggests tests based on recent changes and runs test suites.

**Usage:**
```bash
uv run qabot suggest /path/to/repo
uv run qabot run /path/to/repo
uv run qabot full /path/to/repo
```

**Programmatic API:**
```python
from qabot.analyzer import get_bot_result
result = get_bot_result("/path/to/repo", max_commits=50)
```

### Orchestrator (DevBot)
Conversational interface that knows about projects and calls other bots.

**Usage:**
```bash
# Register a project
uv run orchestrator add uni.li /path/to/uni.li

# List projects
uv run orchestrator projects

# Start chat session
uv run orchestrator chat
```

In chat mode, ask things like:
- "get qabot report for uni.li"
- "show me gitbot analysis of myproject"
- "what projects do you know?"

The orchestrator uses Claude to understand your requests and routes them to the appropriate bot.

### Project Manager (PMBot)
Analyzes GitLab and GitHub issues, identifies patterns, and generates AI-powered sprint plans.

**Usage:**
```bash
# Analyze GitLab issues
uv run pmbot analyze --project-id 12345

# Analyze GitHub issues
uv run pmbot analyze --github-repo owner/repo

# Generate sprint plan
uv run pmbot plan --project-id 12345
```

**Programmatic API:**
```python
from project_manager.analyzer import get_bot_result
result = get_bot_result(project_id="12345", model="claude-sonnet-4-5-20250514")
```

## Bot Interactions

All bots follow a uniform contract:
1. Each bot exports a `get_bot_result()` function
2. Returns a `BotResult` dataclass with standardized fields
3. Can be invoked standalone (CLI) or through the orchestrator
4. Bots can compose by sharing data models (e.g., GitBot's `ChangeSet` → QABot)

See the [Bot Interactions diagram](bot-interactions.puml) for detailed API contracts.

## Development

This is a uv workspace. Install dependencies:
```bash
uv sync
```

Run individual bots:
```bash
uv run gitbot --help
uv run qabot --help
uv run orchestrator --help
```

Or use the orchestrator for conversational interface:
```bash
uv run orchestrator chat
```
