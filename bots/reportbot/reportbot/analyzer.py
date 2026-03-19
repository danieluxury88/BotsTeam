"""ReportBot analyzer — reviews and improves markdown reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from shared.llm import chat
from shared.models import BotResult, BotStatus

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load_instructions(
    mode: str,
    instructions_file: Path | str | None = None,
) -> str:
    """Load prompt instructions from an override file or bundled prompt."""
    prompt_path = (
        Path(instructions_file)
        if instructions_file
        else PROMPTS_DIR / f"{mode}.md"
    )
    return prompt_path.read_text(encoding="utf-8").strip()


def review_report(
    content: str,
    title: str = "",
    instructions_file: Path | str | None = None,
) -> str:
    """Review a markdown report and return feedback in markdown."""
    system_prompt = _load_instructions("review", instructions_file)
    title_hint = f"Report title/filename: {title}\n\n" if title else ""
    user_message = (
        f"{title_hint}"
        "Review the following markdown report.\n\n"
        f"{content or '(empty report)'}"
    )
    return chat(
        system=system_prompt,
        user=user_message,
        max_tokens=2000,
        bot_env_key="REPORTBOT_MODEL",
    ).strip()


def improve_report(
    content: str,
    title: str = "",
    instructions_file: Path | str | None = None,
) -> str:
    """Improve a markdown report and return the rewritten markdown."""
    system_prompt = _load_instructions("improve", instructions_file)
    title_hint = f"Report title/filename: {title}\n\n" if title else ""
    user_message = (
        f"{title_hint}"
        "Improve the following markdown report.\n\n"
        f"{content or '(empty report)'}"
    )
    return chat(
        system=system_prompt,
        user=user_message,
        max_tokens=2500,
        bot_env_key="REPORTBOT_MODEL",
    ).strip()


def get_bot_result(
    report_file: Path | str,
    mode: str = "review",
    instructions_file: Path | str | None = None,
) -> BotResult:
    """
    Review or improve a markdown report file.

    Args:
        report_file: Path to the markdown report
        mode: "review" or "improve"
        instructions_file: Optional custom markdown prompt file

    Returns:
        BotResult containing either review feedback or improved markdown
    """
    report_path = Path(report_file)

    if mode not in {"review", "improve"}:
        return BotResult.failure("reportbot", f"Unsupported mode: {mode}")

    if not report_path.exists():
        return BotResult.failure("reportbot", f"Report file not found: {report_path}")

    try:
        content = report_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return BotResult.failure("reportbot", f"Could not read report file: {exc}")

    try:
        if mode == "review":
            output = review_report(
                content,
                title=report_path.name,
                instructions_file=instructions_file,
            )
            summary = f"Reviewed report: {report_path.name}"
        else:
            output = improve_report(
                content,
                title=report_path.name,
                instructions_file=instructions_file,
            )
            summary = f"Improved report: {report_path.name}"
    except OSError as exc:
        return BotResult.failure(
            "reportbot",
            f"Could not load instructions file: {exc}",
        )
    except Exception as exc:
        return BotResult.failure("reportbot", f"LLM call failed: {exc}")

    return BotResult(
        bot_name="reportbot",
        status=BotStatus.SUCCESS,
        summary=summary,
        markdown_report=output,
        data={
            "mode": mode,
            "report": report_path.name,
            "source_path": str(report_path.resolve()),
            "instructions_file": str(Path(instructions_file).resolve())
            if instructions_file
            else None,
        },
        timestamp=datetime.utcnow(),
    )
