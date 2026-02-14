# 🤖 Orchestrator (DevBot)

Conversational bot that knows about your projects and calls other bots on your behalf. Chat with it naturally to get reports from gitbot or qabot without remembering command syntax.

## Features

- 💬 **Natural Language Interface** — Ask questions in plain English
- 🗂️ **Project Registry** — Maintains a list of your projects
- 🧠 **Smart Routing** — Uses Claude to understand requests and route to correct bot
- 🔌 **Bot Invocation** — Calls gitbot and qabot programmatically
- 💅 **Rich Terminal UI** — Beautiful formatted output
- 🔍 **Fuzzy Matching** — Finds projects even with partial names
- 📋 **Project Management** — Add/remove/list projects easily

## Installation

From the workspace root:

```bash
uv sync
```

The orchestrator is also available as `devbot` command.

## Usage

### Quick Start

```bash
# Add your projects to the registry
uv run orchestrator add uni.li /home/user/projects/uni.li

# Start chat session
uv run orchestrator chat
```

### Chat Interface

Once in chat mode, ask naturally:

```
You: get qabot report for uni.li

→ Running qabot on uni.li...
[Full QABot test analysis appears here]

You: show me gitbot analysis of myproject

→ Running gitbot on myproject...
[Full GitBot history summary appears here]

You: what projects do you know?

┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Name   ┃ Path                     ┃ Description     ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ uni.li │ /home/user/projects/...  │ University...   │
└────────┴──────────────────────────┴─────────────────┘
```

### Special Commands

In chat mode, use these commands:

- `/projects` — List all registered projects
- `/add` — Add a project interactively
- `/remove` — Remove a project
- `/exit` or `/quit` — Exit chat

### CLI Commands

Manage projects without starting chat:

```bash
# List projects
uv run orchestrator projects

# Add a project
uv run orchestrator add myproject /path/to/project

# Add with description
uv run orchestrator add myproject /path/to/project --desc "My awesome project"

# Remove a project
uv run orchestrator remove myproject
```

## Example Conversations

### Get QA Report

```
You: get qabot report for uni.li

→ Running qabot on uni.li...

╭──────────────────────── QABOT Report ────────────────────────╮
│                                                              │
│ Testing Summary                                              │
│ Recent changes focus on authentication...                    │
│                                                              │
│ Priority Test Areas                                          │
│ 1. Authentication Module (High)...                           │
│ ...                                                          │
╰──────────────────────────────────────────────────────────────╯
```

### Get Git Analysis

```
You: analyze recent changes in myproject

→ Running gitbot on myproject...

╭──────────────────────── GITBOT Report ────────────────────────╮
│                                                               │
│ Overview                                                      │
│ The repository has seen active development...                │
│                                                               │
│ Key Changes                                                   │
│ - Refactored authentication module                           │
│ - Added new API endpoints                                    │
│ ...                                                           │
╰───────────────────────────────────────────────────────────────╯
```

### List Projects

```
You: what projects do you know?

                    Registered Projects
┏━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
┃ Name        ┃ Path                     ┃ Description     ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
│ uni.li      │ /home/user/Clients/...   │ University...   │
│ myproject   │ /home/user/projects/...  │ Web app         │
│ api-server  │ /home/user/work/...      │ REST API        │
└─────────────┴──────────────────────────┴─────────────────┘
```

## How It Works

1. **You ask** in natural language (e.g., "get qabot report for uni.li")
2. **Claude parses** your request and identifies:
   - Which bot to use (gitbot or qabot)
   - Which project you're referring to
   - Any parameters (like max_commits)
3. **Orchestrator finds** the project in the registry (fuzzy matching)
4. **Bot is invoked** programmatically with the project path
5. **Results are displayed** with beautiful formatting

## Project Registry

Projects are stored in `~/.devbot/projects.json`:

```json
{
  "uni.li": {
    "name": "uni.li",
    "path": "/home/user/Clients/ProtonSystems/uni.li",
    "description": "University Liechtenstein Drupal Migration",
    "language": "python"
  }
}
```

The registry supports:
- ✅ Exact name matching
- ✅ Case-insensitive matching
- ✅ Partial name matching (fuzzy)
- ✅ Path and description search

## Configuration

Uses shared workspace configuration from root `.env`:

```bash
ANTHROPIC_API_KEY=sk-...
GITBOT_MODEL=claude-haiku-4-5-20251001  # used for parsing requests
```

## Programmatic Usage

You can use orchestrator components in your own scripts:

```python
from orchestrator.registry import ProjectRegistry
from orchestrator.bot_invoker import invoke_bot

# Manage projects
registry = ProjectRegistry()
registry.add_project("myproject", "/path/to/project")
project = registry.get_project("myproject")

# Invoke bots
result = invoke_bot("gitbot", project.path, max_commits=100)
print(result.markdown_report)

result = invoke_bot("qabot", project.path, max_commits=50)
print(result.summary)
```

## Natural Language Examples

The orchestrator understands various phrasings:

- "get qabot report for uni.li"
- "show me gitbot analysis of myproject"
- "analyze recent changes in api-server"
- "what should I test in uni.li?"
- "run gitbot on myproject"
- "give me a qa report for api-server"
- "what projects do you know?"
- "list all my projects"

## Roadmap

- [x] Project registry with JSON storage
- [x] Conversational interface with Claude
- [x] Bot invocation (gitbot, qabot)
- [x] Fuzzy project matching
- [ ] Multi-bot workflows (gitbot → qabot pipeline)
- [ ] Project templates
- [ ] Slack/Discord integration
- [ ] Web UI
- [ ] Scheduled reports
- [ ] Git webhook integration

## Aliases

The orchestrator is available under two names:
- `uv run orchestrator` — Full name
- `uv run devbot` — Short alias

Both work identically!
