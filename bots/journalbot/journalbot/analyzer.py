"""JournalBot analyzer — reads markdown notes and generates AI insights."""

from datetime import date, datetime
from pathlib import Path

from shared.data_manager import save_report
from shared.file_reader import format_files_for_llm, read_markdown_files
from shared.llm import chat
from shared.models import BotResult, BotStatus, ProjectScope

SYSTEM_PROMPT = """\
You are JournalBot, an AI assistant that analyzes personal journal entries and notes.

Your role is to surface patterns, insights, and actionable takeaways from personal writing.

When analyzing journal entries, focus on:
- **Recurring themes**: Topics, concerns, or ideas that appear across multiple entries
- **Mood and energy patterns**: Emotional tone, stress levels, enthusiasm
- **Key decisions or realizations**: Important moments worth revisiting
- **Progress on goals or projects**: Evidence of growth or stagnation
- **What needs attention**: Unresolved concerns or items to follow up on

Format your response as a clear markdown report with sections. Be empathetic, constructive,
and specific — reference actual content from the entries when relevant. Keep it concise.
"""


def get_bot_result(
    notes_dir: Path | str,
    since: date | None = None,
    until: date | None = None,
    max_files: int = 30,
    model: str | None = None,
    project_name: str | None = None,
    scope: ProjectScope = ProjectScope.PERSONAL,
) -> BotResult:
    """
    Analyze personal journal/notes markdown files.

    Args:
        notes_dir: Path to directory containing .md journal files
        since: Only include files modified on or after this date
        until: Only include files modified on or before this date
        max_files: Maximum number of files to read
        model: Optional Claude model override
        project_name: If provided, auto-saves report to data/personal/{project}/reports/journalbot/
        scope: Project scope (default: PERSONAL)

    Returns:
        BotResult with insights report
    """
    notes_dir = Path(notes_dir)

    read_result = read_markdown_files(notes_dir, since=since, until=until, max_files=max_files)

    if read_result.is_empty:
        msg = f"No markdown files found in {notes_dir}"
        if read_result.errors:
            msg += f": {read_result.errors[0]}"
        return BotResult.failure("journalbot", msg)

    formatted = format_files_for_llm(read_result.entries)

    date_info = ""
    if since or until:
        date_info = f" (from {since or 'beginning'} to {until or 'now'})"

    user_prompt = f"""\
Analyze these journal/notes entries{date_info}.
Files read: {len(read_result.entries)} of {read_result.total_files} available.

{formatted}

Generate a personal insights report."""

    try:
        report_md = chat(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=2000,
            bot_env_key="JOURNALBOT_MODEL",
        )
    except Exception as e:
        return BotResult.failure("journalbot", f"LLM call failed: {e}")

    summary_line = f"Analyzed {len(read_result.entries)} journal entries"
    if read_result.date_range:
        start, end = read_result.date_range
        summary_line += f" ({start.strftime('%Y-%m-%d')} – {end.strftime('%Y-%m-%d')})"

    result = BotResult(
        bot_name="journalbot",
        status=BotStatus.SUCCESS,
        summary=summary_line,
        markdown_report=report_md,
        data={
            "files_read": len(read_result.entries),
            "total_files": read_result.total_files,
            "total_words": read_result.total_words,
        },
        timestamp=datetime.utcnow(),
    )

    if project_name:
        save_report(project_name, "journalbot", report_md, scope=scope)

    return result
