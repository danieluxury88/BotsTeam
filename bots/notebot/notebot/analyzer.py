"""NoteBot analyzer — reads markdown notes and generates AI insights, plus improves individual notes."""

from datetime import date, datetime
from pathlib import Path

from shared.data_manager import save_report
from shared.file_reader import format_files_for_llm, read_markdown_files
from shared.llm import chat
from shared.models import BotResult, BotStatus, ProjectScope

# ── Analyse all notes ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are NoteBot, an expert knowledge manager and personal assistant.

Your role is to analyse a collection of markdown notes and surface actionable insights.

When analysing notes, cover these sections:
1. **Summary** — a concise overview of the notes collection (topic coverage, volume, recency)
2. **Key Themes** — the main subjects and recurring topics across the notes
3. **Action Items** — TODOs, decisions pending, follow-ups, or tasks mentioned in the notes (cite the note filename)
4. **Organisation Suggestions** — how to better structure, group, tag, or merge the notes; identify duplicates or closely related notes
5. **Knowledge Gaps** — topics referenced but not fully documented; areas where additional notes would add value

Format your response as clean markdown with these exact section headings.
Be specific — reference actual note filenames and content when relevant. Keep it concise and actionable.
"""

# ── Improve a single note ─────────────────────────────────────────────────────

_IMPROVE_SYSTEM = """\
You are an expert technical writer and knowledge manager.
Your job is to improve a single markdown note to make it clearer, better structured, and more useful.

Guidelines:
- Preserve all factual content and intent — do not add or remove information
- Improve headings, formatting, and structure
- Add an appropriate title if missing
- Use bullet lists, numbered lists, or tables where they improve clarity
- Add a brief summary at the top if the note is long
- Fix grammar and spelling
- Add section headings for long notes

Return ONLY the improved markdown text — no preamble, no explanation, no metadata.
"""


def improve_note(content: str, title: str = "") -> str:
    """
    Ask Claude to improve a single note's structure and clarity.

    Args:
        content: Raw markdown content of the note
        title: Optional filename or title hint

    Returns:
        Improved markdown text, or the original content on failure.
    """
    title_hint = f"Note title/filename: {title}\n\n" if title else ""
    user_message = (
        f"{title_hint}"
        f"Current content:\n\n{content or '(empty note)'}\n\n"
        "Return only the improved markdown."
    )
    try:
        return chat(
            system=_IMPROVE_SYSTEM,
            user=user_message,
            max_tokens=2000,
            bot_env_key="NOTEBOT_MODEL",
        ).strip()
    except Exception:
        return content


# ── Main entry point ──────────────────────────────────────────────────────────

def get_bot_result(
    notes_dir: Path | str,
    mode: str = "analyze",
    note_content: str | None = None,
    note_title: str | None = None,
    since: date | None = None,
    until: date | None = None,
    max_files: int = 50,
    model: str | None = None,
    project_name: str | None = None,
    scope: ProjectScope = ProjectScope.PERSONAL,
) -> BotResult:
    """
    NoteBot main entry point.

    Args:
        notes_dir: Path to the notes directory
        mode: "analyze" (full analysis) or "improve" (improve a single note)
        note_content: For mode="improve", the note content to improve
        note_title: For mode="improve", the note filename/title
        since: Only include files modified on or after this date (analyze mode)
        until: Only include files modified on or before this date (analyze mode)
        max_files: Maximum number of files to read (analyze mode)
        model: Optional Claude model override
        project_name: If provided, auto-saves analysis report
        scope: Project scope

    Returns:
        BotResult with analysis or improved note content
    """
    notes_dir = Path(notes_dir)

    if mode == "improve":
        if not note_content:
            return BotResult.failure("notebot", "No note content provided for improve mode.")
        improved = improve_note(note_content, title=note_title or "")
        return BotResult(
            bot_name="notebot",
            status=BotStatus.SUCCESS,
            summary=f"Improved note: {note_title or 'untitled'}",
            markdown_report=improved,
            data={"mode": "improve", "note": note_title},
            timestamp=datetime.utcnow(),
        )

    # mode == "analyze"
    read_result = read_markdown_files(notes_dir, since=since, until=until, max_files=max_files)

    if read_result.is_empty:
        msg = f"No markdown files found in {notes_dir}"
        if read_result.errors:
            msg += f": {read_result.errors[0]}"
        return BotResult.failure("notebot", msg)

    formatted = format_files_for_llm(read_result.entries)

    date_info = ""
    if since or until:
        date_info = f" (from {since or 'beginning'} to {until or 'now'})"

    user_prompt = f"""\
Analyse these notes{date_info}.
Files read: {len(read_result.entries)} of {read_result.total_files} available.
Total words: {read_result.total_words:,}

{formatted}

Generate a structured notes analysis report."""

    try:
        report_md = chat(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=2000,
            bot_env_key="NOTEBOT_MODEL",
        )
    except Exception as e:
        return BotResult.failure("notebot", f"LLM call failed: {e}")

    summary_line = f"Analysed {len(read_result.entries)} notes ({read_result.total_words:,} words)"
    if read_result.date_range:
        start, end = read_result.date_range
        summary_line += f" — {start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')}"

    result = BotResult(
        bot_name="notebot",
        status=BotStatus.SUCCESS,
        summary=summary_line,
        markdown_report=report_md,
        data={
            "files_read": len(read_result.entries),
            "total_files": read_result.total_files,
            "total_words": read_result.total_words,
            "mode": "analyze",
        },
        timestamp=datetime.utcnow(),
    )

    if project_name:
        save_report(project_name, "notebot", report_md, scope=scope)

    return result
