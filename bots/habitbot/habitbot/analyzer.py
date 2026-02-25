"""HabitBot analyzer — reads habit tracking files and generates AI consistency insights."""

from datetime import date, datetime
from pathlib import Path

from shared.data_manager import save_report
from shared.file_reader import format_files_for_llm, read_habit_file
from shared.llm import chat
from shared.models import BotResult, BotStatus, ProjectScope

SYSTEM_PROMPT = """\
You are HabitBot, an AI assistant that analyzes personal habit tracking data.

Your role is to surface patterns, celebrate wins, and identify where attention is needed.

When analyzing habit data, focus on:
- **Overall consistency**: What percentage of days is each habit completed?
- **Streaks**: Current and longest streaks for each habit
- **Trends**: Which habits are improving, declining, or steady?
- **Struggling habits**: Habits with low consistency that need attention
- **Strong habits**: Habits that are well-established (celebrate these!)
- **Correlation patterns**: Any habits that tend to co-occur (do well together or fail together)
- **Recommended focus**: 1-2 habits to prioritize for the next week

Format your response as a clear markdown report. Be encouraging and specific.
Use data from the entries when referencing streaks or percentages.
"""


def get_bot_result(
    habit_source: Path | str,
    since: date | None = None,
    until: date | None = None,
    model: str | None = None,
    project_name: str | None = None,
    scope: ProjectScope = ProjectScope.PERSONAL,
) -> BotResult:
    """
    Analyze a habit tracking file (CSV or markdown).

    Args:
        habit_source: Path to habit log file (.csv or .md)
        since: Filter entries from this date (for markdown logs)
        until: Filter entries to this date (for markdown logs)
        model: Optional Claude model override
        project_name: If provided, auto-saves report
        scope: Project scope (default: PERSONAL)

    Returns:
        BotResult with habit insights report
    """
    habit_source = Path(habit_source)

    read_result = read_habit_file(habit_source)

    if read_result.is_empty:
        msg = f"No habit data found at {habit_source}"
        if read_result.errors:
            msg += f": {read_result.errors[0]}"
        return BotResult.failure("habitbot", msg)

    formatted = format_files_for_llm(read_result.entries)

    date_info = ""
    if since or until:
        date_info = f" (from {since or 'beginning'} to {until or 'now'})"

    user_prompt = f"""\
Analyze this habit tracking data{date_info} and provide insights on consistency and progress.

{formatted}

Generate a habit analysis report."""

    try:
        report_md = chat(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=1500,
            bot_env_key="HABITBOT_MODEL",
        )
    except Exception as e:
        return BotResult.failure("habitbot", f"LLM call failed: {e}")

    summary_line = f"Analyzed habit data from {habit_source.name}"

    result = BotResult(
        bot_name="habitbot",
        status=BotStatus.SUCCESS,
        summary=summary_line,
        markdown_report=report_md,
        data={
            "source_file": str(habit_source),
            "total_words": read_result.total_words,
        },
        timestamp=datetime.utcnow(),
    )

    if project_name:
        save_report(project_name, "habitbot", report_md, scope=scope)

    return result
