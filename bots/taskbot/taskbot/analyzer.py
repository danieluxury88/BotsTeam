"""TaskBot analyzer — reads personal task lists and generates AI productivity insights."""

from datetime import datetime
from pathlib import Path

from shared.data_manager import save_report
from shared.file_reader import format_files_for_llm, read_task_file
from shared.llm import chat
from shared.models import BotResult, BotStatus, ProjectScope

SYSTEM_PROMPT = """\
You are TaskBot, an AI assistant that analyzes personal task lists and to-do files.

Your role is to help the user understand their productivity patterns and prioritize their work.

When analyzing task lists, focus on:
- **Completion rate**: Ratio of done vs pending tasks
- **Stale items**: Tasks that appear overdue or have been sitting too long
- **Priority and urgency**: Which open tasks seem most important
- **Patterns**: Any recurring task types or areas that consistently pile up
- **Recommended next 3 actions**: The most impactful things to do next
- **Items to drop or defer**: Tasks that may no longer be relevant

Format your response as a clear markdown report. Be direct and actionable.
Markdown checkbox syntax: - [x] done, - [ ] pending.
"""


def get_bot_result(
    task_source: Path | str,
    model: str | None = None,
    project_name: str | None = None,
    scope: ProjectScope = ProjectScope.PERSONAL,
) -> BotResult:
    """
    Analyze a personal task list file or directory.

    Args:
        task_source: Path to a task file (.md, .txt) or directory of task files
        model: Optional Claude model override
        project_name: If provided, auto-saves report
        scope: Project scope (default: PERSONAL)

    Returns:
        BotResult with productivity insights report
    """
    task_source = Path(task_source)

    read_result = read_task_file(task_source)

    if read_result.is_empty:
        msg = f"No task content found at {task_source}"
        if read_result.errors:
            msg += f": {read_result.errors[0]}"
        return BotResult.failure("taskbot", msg)

    formatted = format_files_for_llm(read_result.entries)

    user_prompt = f"""\
Analyze these task lists and provide productivity insights.
Files read: {len(read_result.entries)}

{formatted}

Generate a task analysis and productivity report."""

    try:
        report_md = chat(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=1500,
            bot_env_key="TASKBOT_MODEL",
        )
    except Exception as e:
        return BotResult.failure("taskbot", f"LLM call failed: {e}")

    summary_line = f"Analyzed {len(read_result.entries)} task file(s), {read_result.total_words} words"

    result = BotResult(
        bot_name="taskbot",
        status=BotStatus.SUCCESS,
        summary=summary_line,
        markdown_report=report_md,
        data={
            "files_read": len(read_result.entries),
            "total_words": read_result.total_words,
        },
        timestamp=datetime.utcnow(),
    )

    if project_name:
        save_report(project_name, "taskbot", report_md, scope=scope)

    return result
