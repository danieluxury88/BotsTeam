# Repository Guidelines

## Project Structure & Module Organization
- `shared/shared/`: core utilities and contracts (`models.py`, config, git/file readers, API clients, data manager).
- `bots/<bot>/<bot>/`: bot packages (for example `bots/gitbot/gitbot/`, `bots/qabot/qabot/`) with CLI and analyzer logic.
- `bots/dashboard/dashboard_cli/`: CLI launcher for the web dashboard.
- `dashboard/`: static web app and local server/data scripts (`server.py`, `generate_data.py`, `css/`, `js/`).
- `data/`: runtime output (project registries, generated reports, cache). Avoid manual edits unless debugging.
- `docs/`: architecture, usage, and design documentation.
- `bots/slackbot/`: Slack integration package.

## Build, Test, and Development Commands
- `uv sync`: install workspace dependencies for all packages.
- `uv run ruff check .`: run lint checks.
- `uv run ruff check --fix .`: auto-fix lint issues where possible.
- `uv run pytest`: run test suite (workspace-level).
- `uv run orchestrator chat`: start the conversational orchestrator.
- `uv run chat`: start the default orchestrator chat session directly.
- `uv run dashboard`: generate dashboard data and start the web UI.
- `uv run dashboard generate`: regenerate JSON data only.
- `uv run <bot> --help` (for example `uv run gitbot --help`): inspect CLI options per bot.

## Coding Style & Naming Conventions
- Target Python 3.10+ with 4-space indentation and explicit type hints.
- Follow existing bot pattern: expose `get_bot_result()` and return `BotResult` from `shared/models.py`.
- Use `snake_case` for Python modules/functions/variables, `PascalCase` for classes/dataclasses.
- Keep CLI code in `cli.py` and core analysis logic in `analyzer.py`.
- For dashboard JavaScript, follow current style: `camelCase` functions and small focused modules under `dashboard/js/`.

## Testing Guidelines
- Use `pytest`; add tests alongside the package they cover (for example `bots/qabot/tests/test_runner.py`, `shared/tests/test_data_manager.py`).
- Name files `test_*.py`; keep tests deterministic and filesystem-safe.
- For CLI changes, test both command success and failure paths.
- No enforced coverage threshold yet; new features should include targeted tests.

## Commit & Pull Request Guidelines
- Follow the repository’s observed commit style: `feat: ...`, `fix: ...`, `docs: ...`, optionally scoped (for example `feat(orchestrator): ...`).
- Keep commits small and single-purpose.
- PRs should include: concise summary, impacted paths, lint/test results, and linked issue/task.
- Include screenshots or short recordings for dashboard/UI changes.

## Security & Configuration Tips
- Copy `.env.example` to `.env`; never commit secrets (`ANTHROPIC_API_KEY`, GitLab/GitHub tokens).
- Treat `data/` outputs as generated artifacts; avoid committing local report dumps.
