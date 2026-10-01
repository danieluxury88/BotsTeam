# Core Audit Alignment

Tracks how BotsTeam measures up against the checks run by the `core` auditing tool, what has
been addressed, and what is still open. Update this file as items are resolved.

Baseline: core `project-report.json` generated 2026-10-01 (schema 2.1.0) — 8 findings, 4 warnings.

## Findings from core

| Section | Severity | Finding | Status |
| --- | --- | --- | --- |
| makefile | warning | No Makefile | Resolved — see [Makefile](#makefile) |
| criteria | warning | `TASKS.md` is missing (required file) | Open |
| criteria | warning | No `.code-workspace` file (e.g. `BotsTeam.code-workspace`) | Open |
| vscode | info | No `.vscode/settings.json` / `.vscode/extensions.json` | Open — note `.vscode/` is currently git-ignored |
| tech_stack | info | No `composer.json`, `package.json` or `.nvmrc` | Not applicable — Python/uv project; core's tech-stack analyzer does not read `pyproject.toml` |
| collection | warning | Missing collection patterns (PHP/JS/Drupal/DDEV files) | Not applicable, except `Makefile` and `TASKS.md` above |

Passing criteria: worktree clean, in sync with `origin/main`, `.env` present and git-ignored, no
`package-lock.json`. Drupal and Composer criteria are not applicable.

## Makefile

Target names follow core's `SEMANTIC_TARGET_GROUPS` (`scripts/makefile-alignment.py`) so the
alignment report maps them to the shared workflow groups. Run `make help` for the full list.

### Semantic groups covered

| Group | Target | Command |
| --- | --- | --- |
| `lint` | `lint` | `uv run ruff check .` |
| `fix` | `fix` | `uv run ruff check --fix .` |
| `test` | `test` | `uv run pytest` |
| `check-updates` | `check-updates` | `uv tree --outdated --depth 1` (informational, never fails) |
| `check-security` | `check-security` | `uv export` of the lockfile piped into `uvx pip-audit` |
| `audit` | `audit` | Alias of `check-security` (same pattern as WatchTower) |
| `doctor` | `doctor` | Checks uv, git, Python ≥ 3.10, `.env`, and the API key for `DEVBOTS_PROVIDER` |
| `clean` | `clean` | Removes `__pycache__`, `.pytest_cache`, `.ruff_cache`, coverage output; never touches `data/` |

Project-specific targets: `help` (default goal), `install`, `serve`, `generate`, `chat`.

### Semantic groups intentionally not covered

| Group(s) | Reason |
| --- | --- |
| `build` | Workspace packages are not published; there is no build artifact. Dashboard data generation is exposed as `generate`, not disguised as `build`. |
| `deploy` | No deployment target exists. |
| `lint-js`, `lint-md`, `lint-scss`, `fix-js`, `fix-md`, `fix-scss` | Would require Node tooling (Prettier, ESLint, Stylelint, markdownlint); the dashboard is deliberately dependency-free. Revisit if a `package.json` is introduced. |
| `lint-php`, `lint-twig`, `fix-php`, `fix-twig` | No PHP or Twig in this repo. |
| `test-ui`, `test-visual`, `test-install` | Playwright groups; no browser test setup. |
| `lint-staged` | No pre-commit / lint-staged setup. |

## Related fixes

- `uv run pytest` from the repo root failed at collection because test files share basenames
  across packages (`test_cli.py`, `test_analyzer.py`) without `__init__.py`. Fixed by setting
  `--import-mode=importlib` in `[tool.pytest.ini_options]` in the root `pyproject.toml`.

## Open items

Surfaced while adding the Makefile; each makes the corresponding target fail until fixed.

- **`make lint`** — 16 ruff `F541` errors (f-string without placeholders), all auto-fixable with `make fix`.
- **`make test`** — 1 failing test (90 pass):
  `bots/project_manager/tests/test_analyzer.py::test_analyze_report_appends_open_tasks_by_assignee`.
- **`make check-security`** — pip-audit reports known vulnerabilities in locked dependencies
  (minimum fixed version in parentheses): anyio (4.14.2), click (8.3.3), cryptography (50.0.0),
  gitpython (3.1.60), pygments (2.20.0), pyjwt (2.15.0), pytest (9.0.3), python-dotenv (1.2.2),
  requests (2.33.0), urllib3 (2.8.0).
- **`uv.lock` is git-ignored** — `check-security` audits the local lockfile, so results can differ
  between machines. Consider committing `uv.lock` for reproducible installs and audits.
- **Core criteria** — add `TASKS.md` and `BotsTeam.code-workspace`; decide whether to commit
  `.vscode/settings.json` and `.vscode/extensions.json` (requires un-ignoring them).
