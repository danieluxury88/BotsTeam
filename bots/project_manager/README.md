# 📋 Project Manager Bot (pmbot)

AI-powered GitLab issue analyzer and workload planner. Fetches issues from GitLab, analyzes patterns and team health, and generates prioritized sprint plans with effort estimates.

## 💾 Auto-Saved Reports

When invoked through the **Orchestrator**, all reports are automatically saved to:

```
data/{project-name}/reports/project_manager/
├── latest.md              ← Always up-to-date
└── YYYY-MM-DD-HHMMSS.md   ← Timestamped archive
```

**Usage:** `uv run orchestrator chat` → Ask for reports by project name

## Features

- ✅ Fetch issues from GitLab (open, closed, filtered by labels/milestones)
- 🤖 AI-powered issue analysis (patterns, recurring problems, team workload)
- 📅 Sprint planning with automatic priority and effort estimation
- 📊 Beautiful Rich table display in terminal
- 💅 Markdown reports with weekly schedules
- 🔌 Programmatic API for bot composition

## Installation

From the workspace root:

```bash
uv sync
```

## Configuration

Add to your `.env` file:

```bash
GITLAB_PRIVATE_TOKEN=your_token_here
GITLAB_URL=https://gitlab.com  # or your GitLab instance URL
GITLAB_PROJECT_ID=12345  # optional default project
```

## Usage

### CLI

```bash
# List issues in a Rich table
uv run pmbot list --project-id 12345

# Filter by state
uv run pmbot list --project-id 12345 --state opened

# Filter by labels
uv run pmbot list --project-id 12345 --labels bug,critical

# AI analysis: patterns, team workload, recommendations
uv run pmbot analyze --project-id 12345

# Generate sprint plan with priorities and effort estimates
uv run pmbot plan --project-id 12345

# Limit to specific issues
uv run pmbot analyze --project-id 12345 --max-issues 50
```

### Programmatic API

Other bots can call pmbot directly:

```python
from project_manager.analyzer import get_bot_result
from shared.gitlab_client import fetch_issues

# Fetch issues from GitLab
issue_set = fetch_issues(project_id="12345")

# Get AI analysis
result = get_bot_result(issue_set, mode="analyze")
print(result.summary)
print(result.markdown_report)

# Get sprint plan
result = get_bot_result(issue_set, mode="plan")
print(result.markdown_report)  # Shows prioritized weekly schedule
```

## Commands

### list

Fetch and display GitLab issues in a Rich table.

**Options:**
- `--project-id` (required) — GitLab project ID
- `--state` — Filter by state: `opened`, `closed`, `all` (default: `all`)
- `--labels` — Comma-separated labels to filter by
- `--milestone` — Filter by milestone name
- `--max-issues` — Limit number of issues (default: 100)

**Example:**
```bash
uv run pmbot list --project-id 12345 --state opened --labels bug
```

### analyze

AI-powered issue analysis: patterns, recurring problems, team workload.

**Options:**
- `--project-id` (required) — GitLab project ID
- `--state` — Filter by state (default: `all`)
- `--labels` — Filter by labels
- `--max-issues` — Limit number of issues (default: 100)
- `--output` — Save report to markdown file

**Example:**
```bash
uv run pmbot analyze --project-id 12345 --output report.md
```

**Report includes:**
1. Project Health — overall backlog assessment
2. Patterns & Recurring Problems — themes across issues
3. Hotspots — labels/areas with most issues
4. Team Workload — distribution across assignees
5. Stale Issues — open issues needing attention
6. Recommendations — actionable improvements

### plan

Generate an AI sprint plan: prioritize open issues, estimate effort, and schedule a weekly workload.

**Options:**
- `--project-id` (required) — GitLab project ID
- `--labels` — Filter by labels
- `--max-issues` — Limit number of issues (default: 100)
- `--output` — Save plan to markdown file

**Example:**
```bash
uv run pmbot plan --project-id 12345 --output sprint-plan.md
```

**Plan includes:**
- Priority Overview — sorted by critical → high → normal → low
- Effort Estimates — XS (< 2h), S (~4h), M (~8h), L (2-3d), XL (1w+)
- Weekly Schedule — issues grouped by target week with total hours
- Warnings — risks or concerns identified by AI

## Priority Levels

- **Critical** 🔴 — Blockers, security issues, data loss risks
- **High** 🟠 — Significant user impact, major bugs, overdue items
- **Normal** 🟡 — Standard features and improvements
- **Low** 🟢 — Nice-to-haves, minor tweaks, cosmetic issues

## Effort Estimates

- **XS** — < 2 hours
- **S** — Half day (~4h)
- **M** — 1 day (~8h)
- **L** — 2-3 days
- **XL** — 1 week or more

## Use Cases

1. **Sprint Planning** — Generate weekly workload plans with effort estimates
2. **Backlog Health** — Identify patterns, stale issues, and team imbalances
3. **Team Retrospectives** — Analyze recurring problems and improvement areas
4. **Stakeholder Reports** — Export markdown reports for management
5. **Bot Orchestration** — Call from orchestrator to get project insights

## Examples

### Quick health check
```bash
uv run pmbot analyze --project-id 12345
```

### Plan next sprint
```bash
uv run pmbot plan --project-id 12345 --labels sprint-ready
```

### Export full analysis
```bash
uv run pmbot analyze --project-id 12345 --output team-report.md
uv run pmbot plan --project-id 12345 --output sprint-plan.md
```

### Integration with orchestrator
```bash
uv run orchestrator chat
> analyze issues for project uni.li
> create sprint plan for project X
```

## Notes

- Uses Claude (Anthropic) for AI analysis
- Respects GitLab API rate limits
- Fetches up to 100 issues by default (configurable)
- Analysis works best with 20-100 issues
- Sprint plans assume single developer, ~5h effective work per day

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `GITLAB_PRIVATE_TOKEN` | (required) | Your GitLab personal access token |
| `GITLAB_URL` | `https://gitlab.com` | GitLab instance URL |
| `GITLAB_PROJECT_ID` | — | Default project ID if not specified |
| `ISSUEBOT_MODEL` | `claude-haiku-4-5-20251001` | Claude model for analysis |
