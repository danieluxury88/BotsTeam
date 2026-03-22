# 🤖 Orchestrator (DevBot)

Conversational bot that manages multiple projects and orchestrates gitbot, qabot, and pmbot. Chat naturally to analyze code, get test suggestions, and manage GitLab/GitHub issues across all your projects.

## ✨ Features

- 💬 **Natural Language Interface** — Ask questions in plain English
- 🗂️ **Multi-Project Registry** — Manage unlimited projects with metadata
- 🔗 **GitLab/GitHub Integration** — Per-project remote repository connections
- 🧠 **Smart Routing** — Uses Claude to understand requests and route to correct bot
- 🔌 **Bot Invocation** — Calls gitbot, qabot, and pmbot programmatically
- 🔄 **Pipeline Workflows** — Supports multi-bot flows like `gitbot -> qabot`
- 💾 **Auto-Save Reports** — All reports automatically saved to `data/{project}/reports/`
- 💅 **Rich Terminal UI** — Beautiful formatted output with tables
- 🔍 **Fuzzy Matching** — Finds projects even with partial names
- 📋 **Project Management** — Add/remove/list projects with integrations

## Installation

From the workspace root:

```bash
uv sync
```

The orchestrator is also available as `devbot`, and the default chat session is available directly as `uv run chat`.

## Quick Start

```bash
# 1. Add your first project
uv run orchestrator add uni.li /home/user/projects/uni.li \
  --gitlab-id 76261915 \
  --desc "University Liechtenstein Project"

# 2. List registered projects
uv run orchestrator projects

# 3. Start chatting!
uv run orchestrator chat
uv run chat
```

## Project Management

### Adding Projects

**Basic project** (local analysis only):
```bash
uv run orchestrator add myapp ~/projects/myapp \
  --desc "My application"
```

**With GitLab integration** (enables pmbot):
```bash
uv run orchestrator add myapp ~/projects/myapp \
  --gitlab-id 12345 \
  --desc "My application"
```

**With self-hosted GitLab**:
```bash
uv run orchestrator add myapp ~/projects/myapp \
  --gitlab-id mygroup/myproject \
  --gitlab-url https://gitlab.company.com
```

**With per-project credentials**:
```bash
uv run orchestrator add myapp ~/projects/myapp \
  --gitlab-id 12345 \
  --gitlab-token glpat-xxxxx  # Overrides .env
```

**With GitHub**:
```bash
uv run orchestrator add myapp ~/projects/myapp \
  --github-repo owner/repo
```

### Listing Projects

```bash
uv run orchestrator projects
```

**Output:**
```
                    Registered Projects
┏━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ Name   ┃ Path              ┃ Description    ┃ Integration ┃
┡━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ uni.li │ /home/user/pro... │ University...  │ GitLab      │
│ myapp  │ /home/user/myapp  │ My application │ —           │
└────────┴───────────────────┴────────────────┴─────────────┘
```

### Removing Projects

```bash
uv run orchestrator remove myapp
```

## Chat Interface

Start an interactive session:

```bash
uv run orchestrator chat
uv run chat
```

### Example Conversations

**Get git history analysis:**
```
You: get gitbot report for uni.li

→ Running gitbot on uni.li...

─────────────── GITBOT Report ───────────────────
# uni.li Repository Summary
**Period:** 2026-02-13 | **Commits:** 50

## Overview
Active development on migration MVP...

✓ Report saved to: data/uni.li/reports/gitbot/latest.md
```

**Get test suggestions:**
```
You: suggest tests for myapp

→ Running qabot on myapp...

[Full QA analysis with priority test areas]

✓ Report saved to: data/myapp/reports/qabot/latest.md
```

**Analyze recent changes and what to test in one step:**
```
You: analyze recent changes and tell me what to test for uni.li

→ Running gitbot_qabot on uni.li...

[Combined GitBot summary followed by QABot test recommendations]

✓ Report saved to: data/uni.li/reports/orchestrator/latest.md
```

**Analyze remote issues** (requires GitLab or GitHub integration):
```
You: analyze issues for uni.li

→ Running pmbot on uni.li...

[Issue analysis with patterns, hotspots, recommendations]

✓ Report saved to: data/uni.li/reports/pmbot/latest.md
```

**Create sprint plan:**
```
You: create sprint plan for uni.li

→ Running pmbot on uni.li in plan mode...

[Sprint plan with prioritized issues and effort estimates]

✓ Report saved to: data/uni.li/reports/pmbot/latest.md
```

**Create a GitHub issue:**
```
You: create an issue for BotsTeam titled "Dashboard: investigate Header Navigation problem" with description "Investigate the Dashboard header navigation issue, define expected behavior, and propose or implement a fix if straightforward."

→ Running pmbot on BotsTeam...

[Issue creation summary with new issue URL]
```

**Review issue descriptions:**
```
You: review issues for BotsTeam

→ Running pmbot on BotsTeam...

[Issue description review report]
```

**List projects:**
```
You: what projects do you know?

[Projects table appears]
```

### Special Commands

In chat mode:

- `/projects` — List all registered projects
- `/add` — Add a project interactively
- `/remove` — Remove a project
- `/exit` or `/quit` — Exit chat

## How Bots Are Selected

The orchestrator uses Claude to understand your request and automatically route to the right bot:

| Request Type | Bot Used | Requirement |
|---|---|---|
| "git history", "changes", "commits" | **gitbot** | Local git repo |
| "tests", "qa", "testing" | **qabot** | Local git repo |
| "recent changes and what to test" | **gitbot_qabot** | Local git repo |
| "issues", "sprint", "backlog" | **pmbot** | GitLab or GitHub integration |

## Auto-Saved Reports

All bot reports are automatically saved to:

```
data/
└── {project-name}/
    └── reports/
        ├── gitbot/
        │   ├── latest.md              ← Always up-to-date
        │   └── 2026-02-14-101155.md   ← Timestamped archive
        ├── qabot/
        │   ├── latest.md
        │   └── ...
        └── pmbot/
            ├── latest.md
            └── ...
```

**Benefits:**
- ✅ No manual saving needed
- ✅ History preserved with timestamps
- ✅ Easy to find (always check `latest.md`)
- ✅ Git-ignored (won't clutter commits)

## Configuration

Projects are stored in the repo-local registries:

- Team projects: `data/projects.json`
- Personal projects: `data/personal/projects.json`

```json
{
  "uni.li": {
    "name": "uni.li",
    "path": "/home/user/projects/uni.li",
    "description": "University Liechtenstein Project",
    "language": "php",
    "languages": ["php", "javascript"],
    "frameworks": ["Drupal"],
    "gitlab_project_id": "76261915"
  }
}
```

**Global credentials** (in `.env`):
```bash
GITLAB_TOKEN=glpat-xxxxx
GITLAB_URL=https://gitlab.com
GITHUB_TOKEN=ghp-xxxxx
```

**Per-project credentials** override global settings when specified during `add`.

Projects can store one primary language in `language` plus richer stack metadata in `languages` and `frameworks`.
Example:

```bash
uv run orchestrator add uni.li /home/user/projects/uni.li \
  --lang php \
  --language php \
  --language javascript \
  --framework Drupal \
  --gitlab-id 76261915
```

## Integration Requirements

| Feature | Requirements |
|---|---|
| **GitBot** | Local git repository |
| **QABot** | Local git repository |
| **PMBot** | GitLab or GitHub integration plus the corresponding token |

If pmbot is requested for a project without GitLab or GitHub integration, you'll see:

```
⚠ pmbot requires GitLab or GitHub integration
Project 'myapp' doesn't have remote issue tracker metadata.

To enable pmbot:
  orchestrator add myapp /path/to/project --gitlab-id YOUR_PROJECT_ID
  orchestrator add myapp /path/to/project --github-repo owner/repo
```

## Programmatic Usage

Use the orchestrator from Python:

```python
from orchestrator.registry import ProjectRegistry
from orchestrator.bot_invoker import invoke_bot

# Load registry
registry = ProjectRegistry()
project = registry.get_project("uni.li")

# Invoke gitbot
result = invoke_bot("gitbot", project=project, max_commits=50)
print(result.markdown_report)

# Invoke pmbot
result = invoke_bot("pmbot", project=project, bot_params={"mode": "analyze"})
print(result.report_md)
```

## Tips

1. **Start with local projects** - Add projects without GitLab integration first to use gitbot/qabot
2. **Add remote issue tracking later** - Re-run `orchestrator add` with `--gitlab-id` or `--github-repo` to enable pmbot
3. **Use descriptive names** - Short project names make chat easier
4. **Check saved reports** - All analysis is saved to `data/{project}/reports/`
5. **Per-project tokens** - Useful for working with multiple GitLab instances

## Troubleshooting

**Project not found:**
- Check registered projects: `orchestrator projects`
- Try exact name match (case-insensitive)

**pmbot not working:**
- Verify project has GitLab or GitHub integration: `orchestrator projects`
- Check `GITLAB_TOKEN` or `GITHUB_TOKEN` in `.env`
- Ensure the remote project/repository identifier is correct
- For GitHub issue creation and editing, ensure the token can write issues on the target repo

**Reports not saving:**
- Check file permissions on `data/` directory
- Verify project is registered in `data/projects.json` or `data/personal/projects.json`

## Examples

See the [main README](../../README.md) for more examples and architecture details.
