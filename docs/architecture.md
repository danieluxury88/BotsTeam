# DevBots Architecture

## Overview

DevBots is a monorepo containing AI-powered development automation tools ("bots") that share common infrastructure.

## Structure

```
BotsTeam/
├── shared/          # Shared utilities and contracts
├── bots/            # Individual bot implementations
│   ├── gitbot/      # Git history analyzer
│   ├── qabot/       # Test suggestion and execution
│   └── orchestrator/ # Conversational bot orchestrator
└── docs/            # Documentation
```

## Shared Library

The `shared` package provides:

- **config.py**: Environment configuration and .env loading
- **llm.py**: Claude/Anthropic client factory
- **models.py**: Bot collaboration contracts (BotResult, RepoContext, ChangeSet)
- **git_reader.py**: Git repository reading utilities

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

## Future Bots

### QABot (planned)
Suggests tests based on recent changes and runs test suites.

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
