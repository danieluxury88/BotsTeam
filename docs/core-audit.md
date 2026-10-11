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

## Resolved (phase 0 stabilisation, 2026-10-10)

Done ahead of merging the work-focused bots into core (see core's `docs/worklog/2026-10-10-botsteam-core-merge-proposal.md`, section 9). `make lint test audit` is green: 103 tests pass, ruff clean, pip-audit reports no known vulnerabilities.

- **Dashboard exposure** — the server now binds `127.0.0.1` only, sends no CORS headers, and answers `403` to any request whose `Host` is not loopback or whose `Origin` differs from the page origin (blocks cross-site writes and DNS rebinding). Covered by `dashboard/tests/test_server.py`.
- **`.env` writer** — `/api/settings` can only change `DEVBOTS_PROVIDER`, `DEVBOTS_MODEL` and the per-bot `*_MODEL` keys. API keys and `OPENAI_BASE_URL` (which decides where the OpenAI key is sent) are read-only in the dashboard and are edited in `.env`. Values are validated so a newline cannot inject extra `.env` lines, and `_update_env_file` refuses any key outside the allowlist.
- **`make lint`** — 16 `F541` fixed.
- **`make test`** — `test_analyze_report_appends_open_tasks_by_assignee` hard-coded `0d old` against a fixed 2026-04-02 date; the fixture is now relative to the current time.
- **`make check-security`** — the ten flagged packages plus `idna`, `pillow` and `weasyprint` (reported by a newer advisory database) were upgraded in `uv.lock`.
- **`uv.lock`** — no longer git-ignored, so audits and installs are reproducible.
- **`datetime.utcnow()`** — replaced by `shared.models.utc_now()` (same naive-UTC value, no change to serialized timestamps).
- **Default model** — the dashboard presets and hint derive from `shared.config.DEFAULT_MODELS` instead of repeating the model name. The model itself is unchanged; reviewing it is deferred to the move.

## Open items

- **Unauthenticated mutating endpoints** — project CRUD, run-bot and note endpoints still have no authentication. They are reachable only from the local machine and same-origin pages now; they fall away if the API is not migrated into core.
- **Core criteria** — add `TASKS.md` and `BotsTeam.code-workspace` (both exist locally but are git-ignored as local-only files; re-run core's audit to confirm the criteria); decide whether to commit `.vscode/settings.json` and `.vscode/extensions.json` (requires un-ignoring them).
- **Registry paths** — `data/projects.json` stores absolute paths and `data/` holds client report history. Both are git-ignored; keep it that way and do not move `data/` contents into core.
