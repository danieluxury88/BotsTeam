"""Analyzer — sends grouped git history to Claude and returns a summary."""

import os
from pathlib import Path

from shared.config import get_anthropic_api_key, get_default_model, load_env
from shared.git_reader import read_commits, filter_commits, group_commits_auto, format_groups_for_llm
from shared.llm import create_client
from shared.models import ChangeSet, BotResult

load_env()

SYSTEM_PROMPT = """\
You are GitBot, an expert software engineer assistant specializing in code review and project analysis.

Your job is to analyze a grouped git commit history and produce a clear, high-level summary that helps
developers and project managers quickly understand:
- What has been worked on recently
- Which areas of the codebase are most active
- Any patterns worth highlighting (e.g. bug-fix bursts, feature development phases, refactoring periods)
- A brief assessment of development velocity and team activity

Guidelines:
- Be concise and direct. Avoid filler phrases.
- Group your observations naturally — don't just restate the commit list.
- Use developer-friendly language.
- If you spot anything noteworthy (e.g. many fixes in one area, or a quiet period followed by heavy activity), call it out.
- Format your response in clean Markdown with sections.
"""


def analyze_history(
    formatted_history: str,
    repo_name: str = "repository",
    model: str | None = None,
    truncated: bool = False,
) -> str:
    """Send commit history to Claude and return a markdown summary."""

    effective_model = model or get_default_model()
    truncation_note = (
        "\n**Note:** This is a partial history — the repository has more commits than were analyzed.\n"
        if truncated else ""
    )
    client = create_client()

    user_message = f"""\
Please analyze the following git history for the **{repo_name}** repository and provide a high-level summary.
{truncation_note}
{formatted_history}

Produce a structured report with:
1. **Overview** — one paragraph summarizing the overall activity
2. **Key Changes** — the most significant work done, grouped logically
3. **Active Areas** — which parts of the codebase saw the most activity
4. **Observations** — any patterns, concerns, or highlights worth noting
"""

    message = client.messages.create(
        model=effective_model,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return message.content[0].text


def get_changeset(
    repo_path: Path | str,
    branch: str = "HEAD",
    max_commits: int = 300,
    model: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> ChangeSet:
    """
    Programmatic API for gitbot — returns structured ChangeSet.

    This allows other bots (like qabot or orchestrator) to
    consume gitbot's analysis without going through the CLI.
    """
    repo_path = Path(repo_path).resolve()

    # Read and group commits
    read_result = read_commits(repo_path, branch=branch, max_commits=max_commits, since=since, until=until)
    commits = read_result.commits

    # Filter irrelevant commits
    filter_result = filter_commits(commits)
    commits = filter_result.commits

    if not commits:
        return ChangeSet(
            summary="No commits found",
            files_touched=[],
            date_range=None,
            raw_data={"commit_count": 0}
        )

    groups = group_commits_auto(commits)
    formatted = format_groups_for_llm(groups)

    # Get AI summary
    summary = analyze_history(
        formatted, repo_name=repo_path.name, model=model, truncated=read_result.truncated
    )

    # Collect all touched files
    files_touched = []
    seen = set()
    for group in groups:
        for f in group.all_files:
            if f not in seen:
                seen.add(f)
                files_touched.append(f)

    # Date range
    dates = [c.date for group in groups for c in group.commits]
    date_range = (min(dates), max(dates)) if dates else None

    return ChangeSet(
        summary=summary,
        files_touched=files_touched,
        date_range=date_range,
        raw_data={
            "commit_count": len(commits),
            "filtered_count": filter_result.removed_count,
            "truncated": read_result.truncated,
            "groups": len(groups),
            "branch": branch,
        }
    )


def get_bot_result(
    repo_path: Path | str,
    branch: str = "HEAD",
    max_commits: int = 300,
    model: str | None = None,
    project_name: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> BotResult:
    """
    Return gitbot analysis as a BotResult for orchestrator integration.

    Args:
        repo_path: Path to the git repository
        branch: Git branch to analyze
        max_commits: Maximum number of commits to analyze
        model: Optional Claude model override
        project_name: Optional project name for auto-saving reports
        since: Only commits after this date
        until: Only commits before this date

    Returns:
        BotResult with analysis and markdown report
    """
    try:
        changeset = get_changeset(repo_path, branch, max_commits, model, since=since, until=until)

        result = BotResult(
            bot_name="gitbot",
            status="success",
            summary=changeset.summary[:200] + "..." if len(changeset.summary) > 200 else changeset.summary,
            data={
                "changeset": changeset,
                "files_touched": changeset.files_touched,
                "commit_count": changeset.raw_data.get("commit_count", 0),
            },
            markdown_report=changeset.summary,
        )

        # Auto-save report if project_name is provided
        if project_name:
            from shared.data_manager import save_report
            latest, timestamped = save_report(
                project_name,
                "gitbot",
                changeset.summary,
                save_latest=True,
                save_timestamped=True,
            )
            result.data["report_saved"] = {
                "latest": str(latest),
                "timestamped": str(timestamped) if timestamped else None,
            }

        return result
    except Exception as e:
        return BotResult(
            bot_name="gitbot",
            status="error",
            summary=f"Failed to analyze repository: {str(e)}",
            data={"error": str(e)},
            markdown_report="",
        )
