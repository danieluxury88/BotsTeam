# GitHub Copilot Instructions for DevBots

This file provides repository-specific guidance for GitHub Copilot when working on the DevBots project.

## Project Overview

DevBots is a Python monorepo containing AI-powered development automation tools. It includes multiple specialized bots that analyze code, suggest tests, manage issues (GitLab & GitHub), and orchestrate workflows using Claude (Anthropic).

**Key Technologies:**
- Language: Python 3.x
- Package Manager: **uv** (workspace-based monorepo)
- Build Backend: **hatchling**
- AI Provider: Anthropic Claude
- CLI Framework: **typer** with **rich** for terminal output
- Testing: **pytest**
- Linting: **ruff**

## Repository Structure

```
BotsTeam/
├── .github/                 # GitHub configuration and workflows
├── shared/                  # Shared utilities and core library
│   ├── config.py           # Configuration management
│   ├── llm.py              # Anthropic client factory
│   ├── models.py           # Data models (BotResult, ChangeSet, Issue, etc.)
│   ├── git_reader.py       # Git repository utilities
│   ├── gitlab_client.py    # GitLab API client
│   ├── github_client.py    # GitHub API client
│   └── data_manager.py     # Report and data storage
├── bots/
│   ├── gitbot/             # Git history analyzer
│   ├── qabot/              # Test suggestion and execution bot
│   ├── project_manager/    # Issue analyzer and sprint planner (GitLab/GitHub)
│   └── orchestrator/       # Conversational interface that routes to other bots
├── data/                    # Auto-generated reports and cache (git-ignored)
├── docs/                    # Documentation
├── .env.example            # Environment variable template
└── pyproject.toml          # Workspace root configuration
```

Each bot subdirectory has its own `pyproject.toml` and depends on the `shared` package.

## Common Commands

### Setup and Installation
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all workspace dependencies
uv sync
```

### Development
```bash
# Run linter
uv run ruff check .

# Auto-fix linting issues
uv run ruff check --fix .

# Run tests
uv run pytest

# Run tests with verbose output
uv run pytest -v
```

### Running Bots
```bash
# Git history analyzer
uv run gitbot /path/to/repo
uv run gitbot /path/to/repo --max-commits 50

# Test suggestion and execution
uv run qabot suggest /path/to/repo
uv run qabot run /path/to/repo

# Issue analysis (GitLab/GitHub)
uv run pmbot analyze --project-id 12345
uv run pmbot analyze --github-repo owner/repo

# Conversational orchestrator
uv run orchestrator chat
uv run orchestrator projects
```

## Architecture and Coding Patterns

### Uniform Bot Interface
All bots follow a consistent pattern:
1. Each bot exposes a `get_bot_result()` function
2. Returns a `BotResult` dataclass (defined in `shared/models.py`)
3. This enables bot composition (e.g., gitbot output feeds qabot analysis)

### Data Models
- **BotResult**: Unified result structure from all bots
- **ChangeSet**: Git commit analysis data
- **Issue**: Platform-agnostic issue representation (works with both GitLab and GitHub)
- **IssueSet**: Collection of issues with metadata

Both `gitlab_client.py` and `github_client.py` normalize their API responses into the common `Issue` model.

### Configuration
All configuration is managed through:
- `.env` file for environment variables (never commit secrets!)
- `~/.devbot/projects.json` for project registry (orchestrator)
- Per-bot model overrides via environment variables

### Report Storage
- Reports auto-save to `data/{project}/reports/{botname}/`
- Both `latest.md` and timestamped copies are maintained
- The `data/` directory is git-ignored

## Development Guidelines

### Code Style
- Follow existing patterns in each bot
- Use **typer** for CLI commands
- Use **rich** for terminal output (tables, console formatting)
- Maintain the uniform `BotResult` contract for all bots

### Adding a New Bot
1. Create `bots/newbot/` directory with its own `pyproject.toml`
2. Add dependency on `shared` package
3. Implement `analyzer.py` with `get_bot_result()` returning `BotResult`
4. Implement `cli.py` using typer
5. Register the bot in `orchestrator/bot_invoker.py`
6. Add package to workspace members in root `pyproject.toml`

### Testing
- Write tests using **pytest**
- Place tests in the appropriate bot directory
- Run tests before committing: `uv run pytest`
- Ensure tests are compatible with the monorepo workspace structure

### Environment Configuration
Required environment variables (see `.env.example`):
- `ANTHROPIC_API_KEY` — Required for all bots
- `DEVBOTS_MODEL` — Default Claude model (defaults to claude-haiku-4-5-20251001)
- Per-bot overrides: `GITBOT_MODEL`, `QABOT_MODEL`, `ISSUEBOT_MODEL`
- `GITLAB_TOKEN`, `GITLAB_URL`, `GITLAB_PROJECT_ID` — For GitLab integration
- `GITHUB_TOKEN`, `GITHUB_API_URL` — For GitHub integration

### Git Workflow
- Keep commits focused and descriptive
- Don't commit `.env` files or secrets
- Don't commit generated reports in `data/`
- Follow conventional commit messages where possible

## Important Restrictions

### Security
- **Never commit secrets or API keys** to the repository
- **Always use `.env` files** for sensitive configuration
- Validate that `.env` is in `.gitignore`
- Use environment variables for all tokens and credentials

### Code Quality
- **All code must pass `ruff check`** before committing
- Run tests with `uv run pytest` to ensure nothing breaks
- Maintain backwards compatibility with existing bot interfaces
- Don't change the `BotResult` contract without updating all bots

### Dependencies
- Use **uv** for all dependency management (not pip or poetry)
- Keep workspace structure intact in `pyproject.toml`
- Test that changes work in the workspace context (`uv sync`)

## Contributing

When working on issues:
1. Understand the bot architecture and shared library first
2. Make minimal, focused changes
3. Run linter: `uv run ruff check --fix .`
4. Run tests: `uv run pytest`
5. Test the bot CLI commands manually
6. Document any new features in the bot's README
7. Update CLAUDE.md if making architectural changes

## Additional Resources

- [Architecture Documentation](../docs/architecture.md)
- [GitBot README](../bots/gitbot/README.md)
- [QABot README](../bots/qabot/README.md)
- [Project Manager README](../bots/project_manager/README.md)
- [Orchestrator README](../bots/orchestrator/README.md)
