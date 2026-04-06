from __future__ import annotations

from pathlib import Path

from shared.models import BotResult, BotStatus
from teamsbot.formatter import (
    build_bot_result_payload,
    build_saved_report_payload,
    markdown_to_teams_text,
)


def test_markdown_to_teams_text_simplifies_common_markdown() -> None:
    markdown = "# Title\n\n**Bold** item\n- bullet\n[Docs](https://example.com)"

    rendered = markdown_to_teams_text(markdown)

    assert "Title" in rendered
    assert "Bold item" in rendered
    assert "• bullet" in rendered
    assert "Docs (https://example.com)" in rendered


def test_build_saved_report_payload_includes_report_facts() -> None:
    payload = build_saved_report_payload(
        project_name="BotsTeam",
        bot_name="gitbot",
        report_markdown="# Overview\n\nRecent changes landed.",
        report_path=Path("/tmp/latest.md"),
    )

    attachment = payload["attachments"][0]["content"]
    body = attachment["body"]

    assert body[0]["text"] == "DevBots GitBot report"
    assert any(fact["title"] == "Project:" and fact["value"] == "BotsTeam" for fact in body[1]["facts"])
    assert "Recent changes landed." in body[2]["text"]


def test_build_bot_result_payload_uses_status_theme_for_message_cards() -> None:
    result = BotResult(
        bot_name="qabot",
        status=BotStatus.PARTIAL,
        summary="Warnings present",
        markdown_report="## Risk\n\nCheck dashboard navigation.",
    )

    payload = build_bot_result_payload(result, project_name="BotsTeam", card_format="message-card")

    assert payload["themeColor"] == "C77700"
    assert payload["title"] == "DevBots QABot"
    assert payload["sections"][0]["facts"][0]["name"] == "Project"
