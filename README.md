# 🤖 GitBot

AI-powered git history reviewer. Reads your commit history, groups it intelligently, and asks Claude to produce a high-level summary of what's been happening in your codebase.

## Features

- Reads any local git repository (outside of its own repo)
- Groups commits by day, author, or automatically
- Produces a structured AI analysis: overview, key changes, active areas, observations
- Beautiful terminal output via Rich
- Fast and cheap — uses Claude Haiku by default

## Installation

```bash
# 1. Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or on macOS: brew install uv

# 2. Clone this repo
git clone <your-repo-url>
cd gitbot

# 3. Install with uv (automatically creates venv and installs dependencies)
uv sync

# 4. Configure your API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Alternative: Traditional pip installation

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install with pip
pip install -e .
```

## Usage

```bash
# After installation with uv sync, use uv run to execute commands:
# Analyze the current directory
uv run gitbot .

# Analyze an external project
uv run gitbot /path/to/your/project

# Analyze a specific branch, last 50 commits
uv run gitbot /path/to/project --branch main --max-commits 50

# Group by day instead of auto
uv run gitbot /path/to/project --group-by day

# Skip AI, just show the grouped commit table
uv run gitbot /path/to/project --raw

# Use a different Claude model
uv run gitbot . --model claude-sonnet-4-5-20250929

# Save report to markdown file
uv run gitbot /path/to/project --output report.md
uv run gitbot /path/to/project -o analysis-2026-02-13.md
```

### With traditional pip installation:
After activating your virtual environment, you can use `gitbot` directly:
```bash
gitbot .
gitbot /path/to/your/project
gitbot /path/to/project --output report.md
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | required | Your Anthropic API key |
| `GITBOT_MODEL` | `claude-haiku-4-5-20251001` | Claude model to use |

## Options

```
--max-commits  -n   Max commits to read (default: 100)
--group-by     -g   Grouping: auto | day | author (default: auto)
--branch       -b   Branch to analyze (default: HEAD)
--model        -m   Claude model override
--output       -o   Save report to markdown file
--raw              Skip AI, show raw groups only
```

## Grouping Strategy

- **auto** — Spans > 7 days → group by day. Shorter → group by author.
- **day** — One group per calendar day, most recent first.
- **author** — One group per contributor, sorted by commit count.

## Roadmap

- [x] Export report to Markdown file
- [ ] Compare two branches
- [ ] GitHub Actions integration
- [ ] REST API wrapper (FastAPI)
