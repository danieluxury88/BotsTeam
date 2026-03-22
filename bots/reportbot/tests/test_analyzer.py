from __future__ import annotations

from pathlib import Path

from reportbot import analyzer
from shared.models import BotStatus


def test_get_bot_result_reviews_markdown_report(monkeypatch, tmp_path: Path) -> None:
    report_file = tmp_path / "weekly-report.md"
    report_file.write_text("# Weekly Report\n\nA short draft.", encoding="utf-8")

    calls: list[dict[str, str]] = []

    def _fake_chat(system: str, user: str, max_tokens: int = 0, bot_env_key: str | None = None) -> str:
        calls.append(
            {
                "system": system,
                "user": user,
                "bot_env_key": bot_env_key or "",
                "max_tokens": str(max_tokens),
            }
        )
        return "## Overall Assessment\n\nNeeds work."

    monkeypatch.setattr(analyzer, "chat", _fake_chat)

    result = analyzer.get_bot_result(report_file, mode="review")

    assert result.status == BotStatus.SUCCESS
    assert result.summary == "Reviewed report: weekly-report.md"
    assert result.markdown_report == "## Overall Assessment\n\nNeeds work."
    assert calls[0]["bot_env_key"] == "REPORTBOT_MODEL"
    assert "Review the following markdown report." in calls[0]["user"]
    assert "## Overall Assessment" not in calls[0]["user"]
    assert "technical and business reports" in calls[0]["system"]


def test_get_bot_result_improves_report_with_custom_instructions(
    monkeypatch,
    tmp_path: Path,
) -> None:
    report_file = tmp_path / "audit.md"
    report_file.write_text("# Audit\n\nMessy draft.", encoding="utf-8")
    instructions_file = tmp_path / "custom-improve.md"
    instructions_file.write_text("Custom improve prompt", encoding="utf-8")

    captured: dict[str, str] = {}

    def _fake_chat(system: str, user: str, max_tokens: int = 0, bot_env_key: str | None = None) -> str:
        captured["system"] = system
        captured["user"] = user
        return "# Audit\n\nClean draft."

    monkeypatch.setattr(analyzer, "chat", _fake_chat)

    result = analyzer.get_bot_result(
        report_file,
        mode="improve",
        instructions_file=instructions_file,
    )

    assert result.status == BotStatus.SUCCESS
    assert result.summary == "Improved report: audit.md"
    assert result.markdown_report == "# Audit\n\nClean draft."
    assert captured["system"] == "Custom improve prompt"
    assert "Improve the following markdown report." in captured["user"]
    assert result.data["instructions_file"] == str(instructions_file.resolve())


def test_get_bot_result_translates_report(monkeypatch, tmp_path: Path) -> None:
    report_file = tmp_path / "audit.md"
    report_file.write_text("# Audit\n\nPerformance summary.", encoding="utf-8")

    captured: dict[str, str] = {}

    def _fake_chat(system: str, user: str, max_tokens: int = 0, bot_env_key: str | None = None) -> str:
        captured["system"] = system
        captured["user"] = user
        return "# Bericht\n\nLeistungszusammenfassung."

    monkeypatch.setattr(analyzer, "chat", _fake_chat)

    result = analyzer.get_bot_result(
        report_file,
        mode="translate",
        target_language="de",
    )

    assert result.status == BotStatus.SUCCESS
    assert result.summary == "Translated report to German: audit.md"
    assert result.markdown_report == "# Bericht\n\nLeistungszusammenfassung."
    assert "Translate the following markdown report into German (de)." in captured["user"]
    assert result.data["target_language"] == "de"


def test_get_bot_result_fails_for_missing_report_file(tmp_path: Path) -> None:
    result = analyzer.get_bot_result(tmp_path / "missing.md")

    assert result.status == BotStatus.FAILED
    assert "Report file not found" in result.summary


def test_get_bot_result_requires_target_language_for_translate(tmp_path: Path) -> None:
    report_file = tmp_path / "audit.md"
    report_file.write_text("# Audit", encoding="utf-8")

    result = analyzer.get_bot_result(report_file, mode="translate")

    assert result.status == BotStatus.FAILED
    assert "target_language is required" in result.summary
