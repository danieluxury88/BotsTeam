# 📋 Project Manager Bot (pmbot)

AI-powered GitLab/GitHub issue analyzer, planner, reviewer, and issue creator.

## 💾 Auto-Saved Reports

When invoked through the orchestrator, PMBot reports are automatically saved to:

```text
data/{project-name}/reports/pmbot/
├── latest.md
└── YYYY-MM-DD-HHMMSS.md
```

**Usage:** `uv run chat` or `uv run orchestrator chat`

## Features

- ✅ Fetch issues from GitLab or GitHub
- 🤖 AI-powered issue analysis
- 📅 Sprint planning with priority and effort estimates
- ✍️ Issue description review and improvement
- 🆕 GitHub and GitLab issue creation
- 🔌 Programmatic runner for orchestrator and other bots

## Installation

From the workspace root:

```bash
uv sync
```

## Configuration

Add credentials to `.env` as needed:

```bash
GITLAB_PRIVATE_TOKEN=glpat-xxxxx
GITLAB_URL=https://gitlab.com
GITLAB_PROJECT_ID=12345

GITHUB_TOKEN=github_pat_xxxxx
GITHUB_API_URL=https://api.github.com
```

For GitHub or GitLab issue creation and description updates, the token must have issue write access on the target repository or project.

- Fine-grained PAT: grant the target repository and set `Issues` to `Read and write`
- Classic PAT: use `repo` for private repositories or `public_repo` for public ones

## CLI

### Inspect capabilities

```bash
uv run pmbot capabilities --project BotsTeam
uv run pmbot capabilities --github-repo owner/repo

# Runtime auth and permission preflight
uv run pmbot check --project BotsTeam
uv run pmbot check --github-repo owner/repo
```

`capabilities` shows what PMBot implements. `check` verifies what the configured token can actually do on the target repository or project.

### List and analyze issues

```bash
uv run pmbot list --project 12345 --state open
uv run pmbot analyze --project 12345
uv run pmbot analyze --github-repo owner/repo
uv run pmbot plan --project 12345 --weeks 2
```

### Create issues

```bash
uv run pmbot create \
  --project BotsTeam \
  --title "Dashboard: investigate Header Navigation problem" \
  --description "Investigate the Dashboard header navigation issue, define expected behavior, and propose or implement a fix if straightforward."

uv run pmbot create \
  --github-repo owner/repo \
  --title "Broken navigation state" \
  --description-file ./issue.md \
  --label bug \
  --label dashboard \
  --assignee alice \
  --dry-run
```

### Review and improve descriptions

```bash
uv run pmbot review --project BotsTeam --dry-run
uv run pmbot review --project BotsTeam --issue 42
uv run pmbot review --github-repo owner/repo --state all --max 20
```

`--dry-run` shows the improvements without applying updates.

## Orchestrator Usage

Start chat:

```bash
uv run chat
```

Then ask:

```text
analyze issues for BotsTeam
create sprint plan for BotsTeam
review issues for BotsTeam
create an issue for BotsTeam titled "Dashboard: investigate Header Navigation problem" with description "Investigate the Dashboard header navigation issue, define expected behavior, and propose or implement a fix if straightforward."
```

## Programmatic Usage

Use the PMBot runner when you want PMBot to own tracker resolution and action dispatch:

```python
from project_manager.runner import get_bot_result

result = get_bot_result(
    project_name="BotsTeam",
    github_repo="danieluxury88/BotsTeam",
    mode="create",
    title="Dashboard: investigate Header Navigation problem",
    description="Investigate the Dashboard header navigation issue.",
)

print(result.summary)
print(result.markdown_report)
```

If you already have an `IssueSet`, you can still use the analyzer-level API:

```python
from project_manager.analyzer import get_bot_result
from shared.github_client import fetch_issues

issue_set = fetch_issues("owner/repo")
result = get_bot_result(issue_set, mode="analyze")
print(result.markdown_report)
```

## Notes

- GitHub and GitLab issue creation are supported
- Description review and updates are supported on both GitHub and GitLab
- Analysis and planning work with both GitLab and GitHub issue sources
