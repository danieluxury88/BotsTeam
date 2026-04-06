"""Format DevBots content into Microsoft Teams card payloads."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from shared.bot_registry import BOTS
from shared.models import BotResult, BotStatus

CardFormat = Literal["adaptive-card", "message-card"]

_STATUS_THEME_COLORS: dict[str, str] = {
    "success": "2E7D32",
    "partial": "C77700",
    "failed": "C62828",
    "error": "C62828",
    "warning": "C77700",
    "skipped": "546E7A",
}


def markdown_to_teams_text(markdown: str) -> str:
    """Convert simple Markdown into plain text that renders acceptably in Teams cards."""
    text = markdown.strip().replace("\r\n", "\n")
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)
    text = re.sub(r"^\s*[-*]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_text(text: str, max_chars: int) -> str:
    """Truncate long text for card delivery."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    if max_chars <= 1:
        return "…"
    return f"{text[: max_chars - 1].rstrip()}…"


def bot_display_name(bot_name: str) -> str:
    """Return a human-friendly bot label."""
    return BOTS.get(bot_name).name if bot_name in BOTS else bot_name


def build_adaptive_card_payload(
    title: str,
    message: str,
    *,
    facts: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Build a Teams Adaptive Card payload."""
    body: list[dict[str, Any]] = [
        {
            "type": "TextBlock",
            "text": title,
            "weight": "Bolder",
            "size": "Medium",
            "wrap": True,
        }
    ]

    if facts:
        body.append(
            {
                "type": "FactSet",
                "facts": [{"title": f"{label}:", "value": value} for label, value in facts],
            }
        )

    body.append(
        {
            "type": "TextBlock",
            "text": message,
            "wrap": True,
        }
    )

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "contentUrl": None,
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.2",
                    "body": body,
                },
            }
        ],
    }


def build_message_card_payload(
    title: str,
    message: str,
    *,
    facts: list[tuple[str, str]] | None = None,
    theme_color: str = "0078D7",
) -> dict[str, Any]:
    """Build a legacy MessageCard payload."""
    sections: list[dict[str, Any]] = [{"text": message}]
    if facts:
        sections.insert(
            0,
            {
                "facts": [{"name": label, "value": value} for label, value in facts],
            },
        )

    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": title,
        "themeColor": theme_color,
        "title": title,
        "sections": sections,
    }


def build_saved_report_payload(
    *,
    project_name: str,
    bot_name: str,
    report_markdown: str,
    report_path: Path,
    card_format: CardFormat = "adaptive-card",
    max_chars: int = 3500,
) -> dict[str, Any]:
    """Build a Teams payload for an existing saved report."""
    title = f"DevBots {bot_display_name(bot_name)} report"
    message = truncate_text(markdown_to_teams_text(report_markdown), max_chars=max_chars)
    facts = [
        ("Project", project_name),
        ("Bot", bot_display_name(bot_name)),
        ("Report", report_path.name),
    ]

    if card_format == "message-card":
        return build_message_card_payload(title, message, facts=facts)

    return build_adaptive_card_payload(title, message, facts=facts)


def build_bot_result_payload(
    result: BotResult,
    *,
    project_name: str | None = None,
    card_format: CardFormat = "adaptive-card",
    max_chars: int = 3500,
) -> dict[str, Any]:
    """Build a Teams payload directly from a BotResult."""
    status_value = result.status.value if isinstance(result.status, BotStatus) else str(result.status)
    title = f"DevBots {bot_display_name(result.bot_name)}"
    report_text = result.markdown_report or result.report_md or result.summary
    message = truncate_text(markdown_to_teams_text(report_text), max_chars=max_chars)

    facts = [("Status", status_value)]
    if project_name:
        facts.insert(0, ("Project", project_name))
    if result.summary:
        facts.append(("Summary", truncate_text(markdown_to_teams_text(result.summary), 200)))

    if card_format == "message-card":
        return build_message_card_payload(
            title,
            message,
            facts=facts,
            theme_color=_STATUS_THEME_COLORS.get(status_value, "0078D7"),
        )

    return build_adaptive_card_payload(title, message, facts=facts)
