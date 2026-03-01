"""Format BotResult → Slack Block Kit blocks."""

from __future__ import annotations

import re

from shared.models import BotResult

_STATUS_EMOJI: dict[str, str] = {
    "success": "✅",
    "partial": "⚠️",
    "failed": "❌",
    "skipped": "⏭️",
    "error": "❌",
    "warning": "⚠️",
}

# Slack section text limit
_MAX_LEN = 2800


def md_to_mrkdwn(text: str) -> str:
    """Convert basic Markdown to Slack mrkdwn."""
    # Headings: # Heading → *Heading*
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # Bold: **text** → *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Links: [label](url) → <url|label>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
    return text


def format_result(result: BotResult) -> list[dict]:
    """Return Slack Block Kit blocks for a BotResult."""
    status_str = result.status if isinstance(result.status, str) else result.status.value
    emoji = _STATUS_EMOJI.get(status_str, "🤖")

    blocks: list[dict] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"{emoji} {result.bot_name}",
            "emoji": True,
        },
    })

    # Summary section
    summary = md_to_mrkdwn(result.summary or "No summary.")
    if len(summary) > _MAX_LEN:
        summary = summary[:_MAX_LEN] + "…"
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": summary},
    })

    # Full report (only if it adds content beyond the summary)
    report = result.markdown_report or result.report_md or ""
    if report and report.strip() != result.summary.strip():
        mrkdwn_report = md_to_mrkdwn(report)
        if len(mrkdwn_report) <= _MAX_LEN:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": mrkdwn_report},
            })
        else:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": mrkdwn_report[:_MAX_LEN] + "…"},
            })
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": "_Report truncated. Full report saved to dashboard._",
                }],
            })

    return blocks
