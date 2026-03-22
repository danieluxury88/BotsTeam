# 🧪 QABot

AI-powered test suggestion and execution bot. Analyzes recent code changes and suggests what to test, then optionally runs your test suite.

## 💾 Auto-Saved Reports

When invoked through the **Orchestrator**, all reports are automatically saved to:

```
data/{project-name}/reports/qabot/
├── latest.md              ← Always up-to-date
└── YYYY-MM-DD-HHMMSS.md   ← Timestamped archive
```

**Usage:** `uv run orchestrator chat` → Ask for reports by project name

## Features

- 🤖 **AI Test Suggestions** — Claude analyzes changes and recommends specific tests
- 🔍 **Smart Framework Detection** — Automatically finds pytest or unittest
- ▶️ **Test Execution** — Runs your test suite and reports results
- 📋 **Priority Ranking** — Identifies high/medium/low priority tests
- 🎯 **Risk Analysis** — Highlights areas at highest risk from changes
- 💅 **Rich Terminal UI** — Beautiful formatted output
- 📄 **Markdown Reports** — Export test plans to files
- 🔌 **Programmatic API** — Callable by orchestrator and scripts

## Installation

From the workspace root:

```bash
uv sync
```

## Usage

QABot has three commands: `suggest`, `run`, and `full`.

### 1. Suggest Tests

Analyzes recent changes and suggests what to test:

```bash
# Analyze current directory
uv run qabot suggest .

# Analyze external project
uv run qabot suggest /path/to/project

# Limit commits analyzed
uv run qabot suggest /path/to/project --max-commits 20

# Save test plan to file
uv run qabot suggest /path/to/project --output test-plan.md

# Use different Claude model
uv run qabot suggest . --model claude-sonnet-4-5-20250929
```

### 2. Run Tests

Detects test framework and executes tests:

```bash
# Run tests in current directory
uv run qabot run .

# Run tests in external project
uv run qabot run /path/to/project

# Run tests with coverage reporting
uv run qabot run /path/to/project --coverage
```

Supports:
- ✅ pytest (with pytest.ini, pyproject.toml, or test_*.py files)
- ✅ unittest (Python's built-in test framework)

### 3. Full Workflow

Suggest tests, then run them:

```bash
# Complete QA workflow
uv run qabot full /path/to/project

# Skip test execution (suggestions only)
uv run qabot full /path/to/project --skip-tests

# Include coverage reporting in the full workflow
uv run qabot full /path/to/project --coverage

# Customize analysis depth
uv run qabot full . --max-commits 30
```

### Programmatic API

Other bots can call qabot directly:

```python
from qabot.analyzer import get_bot_result, analyze_changes_for_testing

# Get structured BotResult
result = get_bot_result("/path/to/repo", max_commits=50)
print(result.summary)
print(result.markdown_report)

# Get detailed analysis
analysis = analyze_changes_for_testing(Path("/path/to/repo"))
print(analysis.suggestions)
print(analysis.risk_areas)
```

## Options

### `suggest` command

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--max-commits` | `-n` | 50 | Maximum commits to analyze |
| `--model` | `-m` | — | Claude model override |
| `--output` | `-o` | — | Save report to markdown file |

### `run` command

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--coverage` | — | false | Run tests under coverage.py and summarize low-coverage files |
| `--min-coverage` | — | 80.0 | Flag files below this coverage percentage |

### `full` command

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--max-commits` | `-n` | 50 | Maximum commits to analyze |
| `--model` | `-m` | — | Claude model override |
| `--skip-tests` | — | false | Only suggest, don't run tests |
| `--coverage` | — | false | Run tests under coverage.py and summarize low-coverage files |
| `--min-coverage` | — | 80.0 | Flag files below this coverage percentage |

## Example Output

### Test Suggestions

```
╭──────────────────────────────────────────────────────────────────╮
│ QABot analyzing myproject                                        │
│ Path: /home/user/projects/myproject  •  Commits: 50             │
╰──────────────────────────────────────────────────────────────────╯

✓ Detected pytest with 23 test files

───────────────────────── Analyzing Changes ────────────────────────

Testing Summary

Recent changes focus on authentication module refactoring and new API
endpoints. Priority testing should validate auth flows, token handling,
and API contract compatibility...

Priority Test Areas

1. Authentication Module (High Priority - Unit/Integration)
   • Test password reset flow with new token expiry logic
   • Validate 2FA fallback scenarios
   • Why: Auth changes affect all users; security-critical

2. API Endpoints (Medium Priority - Integration)
   • Test /api/v2/users CRUD operations
   • Validate request/response schemas
   • Why: Breaking changes impact API consumers
...
```

### Test Execution

```
╭──────────────────────────────────────────────────────────────────╮
│ QABot running tests in myproject                                 │
╰──────────────────────────────────────────────────────────────────╯

✓ Detected pytest with 23 test files

─────────────────────────── Running Tests ──────────────────────────
Command: pytest -v

======================== test session starts ========================
collected 187 items

tests/test_auth.py::test_login PASSED                         [  1%]
tests/test_auth.py::test_logout PASSED                        [  2%]
tests/test_api.py::test_create_user PASSED                    [  3%]
...

==================== 187 passed in 12.34s ====================

────────────────────────────────────────────────────────────────────
✓ Tests passed: 187 passed in 12.34s
```

## Test Framework Detection

QABot automatically detects:

1. **pytest** if it finds:
   - `pytest.ini`, `pyproject.toml`, or `setup.cfg` with pytest config
   - Any `test_*.py` or `*_test.py` files

2. **unittest** if it finds:
   - Python test files with unittest imports
   - Standard test discovery structure

## Configuration

Uses shared workspace configuration from root `.env`:

```bash
ANTHROPIC_API_KEY=sk-...
GITBOT_MODEL=claude-haiku-4-5-20251001  # used by qabot too
```

## Integration with GitBot

QABot can consume gitbot's `ChangeSet`:

```python
from gitbot.analyzer import get_changeset
from qabot.analyzer import analyze_changeset_for_testing

# Get changes from gitbot
changeset = get_changeset(repo_path)

# Analyze for testing
qa_result = analyze_changeset_for_testing(changeset)
```

This enables gitbot → qabot pipeline orchestration.

## Roadmap

- [x] AI-powered test suggestions
- [x] Test framework detection
- [x] Test execution (pytest, unittest)
- [x] Programmatic API
- [x] Test coverage analysis
- [ ] Automatic test generation
- [ ] Test result parsing and diff analysis
- [ ] Integration with CI/CD
