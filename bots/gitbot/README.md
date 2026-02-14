# 🤖 GitBot

AI-powered git history analyzer. Reads your commit history, groups it intelligently, and asks Claude to produce a high-level summary of what's been happening in your codebase.

## 💾 Auto-Saved Reports

When invoked through the **Orchestrator**, all reports are automatically saved to:

```
data/{project-name}/reports/gitbot/
├── latest.md              ← Always up-to-date
└── YYYY-MM-DD-HHMMSS.md   ← Timestamped archive
```

**Usage:** `uv run orchestrator chat` → Ask for reports by project name

## Features

- ✅ Reads any local git repository
- 🎯 Intelligent commit grouping (by day, author, or automatic)
- 🤖 AI-powered analysis with Claude
- 📊 Structured reports: overview, key changes, active areas, observations
- 💅 Beautiful terminal output via Rich
- ⚡ Fast and cost-effective (uses Claude Haiku by default)
- 📄 Export to Markdown
- 🔌 Programmatic API for bot composition

## Installation

From the workspace root:

```bash
uv sync
```

## Usage

### CLI

```bash
# Analyze current directory
uv run gitbot .

# Analyze external project
uv run gitbot /path/to/project

# Specific branch, limited commits
uv run gitbot /path/to/project --branch main --max-commits 50

# Group by day instead of auto
uv run gitbot /path/to/project --group-by day

# Skip AI analysis, show raw grouped commits
uv run gitbot /path/to/project --raw

# Use a different Claude model
uv run gitbot . --model claude-sonnet-4-5-20250929

# Save report to markdown file
uv run gitbot /path/to/project --output report.md
```

### Programmatic API

Other bots can call gitbot directly:

```python
from gitbot.analyzer import get_bot_result, get_changeset

# Get structured BotResult
result = get_bot_result("/path/to/repo", max_commits=100)
print(result.summary)
print(result.markdown_report)

# Get ChangeSet (for passing to other bots like qabot)
changeset = get_changeset("/path/to/repo", max_commits=100)
print(f"Files touched: {len(changeset.files_touched)}")
print(f"Date range: {changeset.date_range}")
```

## Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--max-commits` | `-n` | 100 | Maximum commits to read |
| `--group-by` | `-g` | auto | Grouping: `auto`, `day`, or `author` |
| `--branch` | `-b` | HEAD | Branch to analyze |
| `--model` | `-m` | — | Claude model override |
| `--output` | `-o` | — | Save report to markdown file |
| `--raw` | — | — | Skip AI, show raw groups only |

## Grouping Strategy

- **auto** — History > 7 days → group by day. Shorter → group by author
- **day** — One group per calendar day, most recent first
- **author** — One group per contributor, sorted by commit count

Groups are capped at 10 to keep LLM context manageable.

## Example Output

```
╭──────────────────────────────────────────────────────────────────╮
│ GitBot analyzing myproject                                       │
│ Path: /home/user/projects/myproject  •  Branch: main            │
╰──────────────────────────────────────────────────────────────────╯

✓ Read 50 commits
✓ Grouped into 5 sections

────────────────────────── Commit Groups ──────────────────────────
┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Group               ┃ Commits ┃ Authors   ┃ Date Range ┃
┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Friday, Feb 13 2026 │      12 │ alice     │ 2026-02-13 │
│ ...                 │     ... │ ...       │ ...        │
└─────────────────────┴─────────┴───────────┴────────────┘

────────────────────────── AI Analysis ────────────────────────────
[Structured markdown report from Claude...]
```

## Configuration

Uses shared workspace configuration from root `.env`:

```bash
ANTHROPIC_API_KEY=sk-...
GITBOT_MODEL=claude-haiku-4-5-20251001  # optional
```

## Integration with Other Bots

GitBot provides a `ChangeSet` that other bots can consume:

```python
# In qabot or orchestrator:
from gitbot.analyzer import get_changeset

changeset = get_changeset(repo_path)
# changeset contains: summary, files_touched, date_range, commit_count
```

This enables bot composition and orchestration workflows.

## Roadmap

- [x] Markdown export
- [x] Programmatic API
- [ ] Compare two branches
- [ ] GitHub Actions integration
- [ ] REST API wrapper
