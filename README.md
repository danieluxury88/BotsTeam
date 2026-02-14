# 🤖 DevBots

**AI-powered development automation tools** — A monorepo of intelligent bots that help you understand and improve your code.

## 🎯 What's Inside

This workspace contains multiple specialized bots that share common infrastructure:

- **[GitBot](bots/gitbot/README.md)** — Analyzes git history and generates AI-powered summaries
- **[QABot](bots/qabot/README.md)** — Suggests tests based on code changes and runs test suites
- **[Project Manager](bots/project_manager/README.md)** — GitLab issue analyzer and AI-powered sprint planner
- **[Orchestrator](bots/orchestrator/README.md)** — Conversational interface that knows your projects and calls other bots

All bots use **Claude (Anthropic)** for AI analysis and share utilities for git reading, LLM access, and configuration.

## ⚡ Quick Start

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Clone and setup
git clone <your-repo-url>
cd BotsTeam
uv sync

# 3. Configure API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY

# 4. Use any bot!
uv run gitbot /path/to/project
uv run qabot suggest /path/to/project
uv run pmbot analyze --project-id 12345
uv run orchestrator chat
```

## 🚀 Usage Examples

### GitBot - Analyze Repository History
```bash
# Get AI summary of recent changes
uv run gitbot . --max-commits 50

# Save report to file
uv run gitbot /path/to/project --output report.md
```

### QABot - Test Suggestions & Execution
```bash
# Get test suggestions based on recent changes
uv run qabot suggest /path/to/project

# Run tests in a repository
uv run qabot run /path/to/project

# Full workflow: suggest then run tests
uv run qabot full /path/to/project
```

### Project Manager - GitLab Issue Analysis
```bash
# Analyze GitLab issues (patterns, team workload, recommendations)
uv run pmbot analyze --project-id 12345

# Generate sprint plan with priorities and effort estimates
uv run pmbot plan --project-id 12345 --output sprint-plan.md

# List issues in a Rich table
uv run pmbot list --project-id 12345 --state opened --labels bug
```

### Orchestrator - Conversational Interface
```bash
# Register your projects
uv run orchestrator add uni.li /home/user/projects/uni.li

# Start chat session
uv run orchestrator chat

# Then ask:
# > get qabot report for uni.li
# > show me gitbot analysis of myproject
# > analyze issues for project X
# > what projects do you know?
```

## 📦 Architecture

This is a **uv workspace monorepo** with:

```
BotsTeam/
├── shared/              # Shared utilities (git_reader, llm, models, config)
├── bots/
│   ├── gitbot/         # Git history analyzer
│   ├── qabot/          # Test suggestion & execution
│   ├── project_manager/ # GitLab issue analyzer & sprint planner
│   └── orchestrator/   # Conversational bot interface
└── docs/               # Documentation
```

Each bot:
- Imports from `shared` for common functionality
- Returns structured `BotResult` for composition
- Can be called via CLI or programmatically
- Uses the same Claude client and configuration

See [docs/architecture.md](docs/architecture.md) for detailed design.

## ⚙️ Configuration

Set up your `.env` file in the workspace root:

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | *required* | Your Anthropic API key |
| `GITBOT_MODEL` | `claude-haiku-4-5-20251001` | Claude model to use (all bots) |
| `GITLAB_PRIVATE_TOKEN` | — | Your GitLab personal access token (for pmbot) |
| `GITLAB_URL` | `https://gitlab.com` | GitLab instance URL |
| `GITLAB_PROJECT_ID` | — | Default GitLab project ID |

## 🔧 Development

```bash
# Sync all dependencies
uv sync

# Run individual bots
uv run gitbot --help
uv run qabot --help
uv run pmbot --help
uv run orchestrator --help

# Run tests (when available)
uv run pytest
```

## 📚 Bot Documentation

Each bot has its own README with detailed usage:

- [GitBot README](bots/gitbot/README.md) - Git history analysis
- [QABot README](bots/qabot/README.md) - Test suggestions and execution
- [Project Manager README](bots/project_manager/README.md) - GitLab issue analysis and sprint planning
- [Orchestrator README](bots/orchestrator/README.md) - Conversational interface

## 🗺️ Roadmap

### GitBot
- [x] Export report to Markdown file
- [x] Programmatic API for other bots
- [ ] Compare two branches
- [ ] GitHub Actions integration

### QABot
- [x] Test framework detection (pytest, unittest)
- [x] AI-powered test suggestions
- [x] Test execution
- [ ] Coverage analysis
- [ ] Test generation

### Project Manager
- [x] GitLab issue fetching and display
- [x] AI-powered issue analysis
- [x] Sprint planning with effort estimates
- [x] Programmatic API
- [ ] Multi-project comparison
- [ ] Velocity tracking

### Orchestrator
- [x] Project registry
- [x] Conversational interface with Claude
- [x] Bot invocation (gitbot, qabot, pmbot)
- [ ] Multi-bot workflows (gitbot → qabot pipeline)
- [ ] Slack/Discord integration

## 📄 License

MIT
