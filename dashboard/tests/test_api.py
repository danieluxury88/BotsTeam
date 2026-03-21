from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = REPO_ROOT / "dashboard"
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

import api  # noqa: E402


def _install_fake_reportbot(monkeypatch, improved_text: str) -> None:
    package = ModuleType("reportbot")
    analyzer = ModuleType("reportbot.analyzer")

    def improve_report(content: str, title: str = "", instructions_file=None) -> str:
        assert content
        assert title
        return improved_text

    analyzer.improve_report = improve_report
    package.analyzer = analyzer
    monkeypatch.setitem(sys.modules, "reportbot", package)
    monkeypatch.setitem(sys.modules, "reportbot.analyzer", analyzer)


class _InlineThread:
    def __init__(self, target, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self) -> None:
        self._target(*self._args, **self._kwargs)


def _clear_voice_jobs() -> None:
    with api.VOICE_COMMAND_JOBS_LOCK:
        api.VOICE_COMMAND_JOBS.clear()


def test_preview_report_improvement_returns_improved_markdown(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "report.md"
    source.write_text("# Report\n\nOriginal text", encoding="utf-8")
    _install_fake_reportbot(monkeypatch, "# Report\n\nImproved text")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        api,
        "_parse_report_reference",
        lambda _path: (
            {
                "scope": api.ProjectScope.TEAM,
                "project_name": "demo",
                "bot_name": "gitbot",
                "source": source,
            },
            None,
            None,
        ),
    )

    body, status = api.preview_report_improvement(
        {"path": "reports/demo/gitbot/report.md"}
    )

    assert status == 200
    assert body["improved"] == "# Report\n\nImproved text"
    assert body["source"]["filename"] == "report.md"


def test_save_report_improvement_writes_timestamped_sibling(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "report.md"
    source.write_text("# Report\n\nOriginal text", encoding="utf-8")
    monkeypatch.setattr(api, "_regenerate_dashboard", lambda: None)
    reports_dir = tmp_path / "data" / "demo" / "reports" / "reportbot"
    monkeypatch.setattr(api, "get_reports_dir", lambda *args, **kwargs: reports_dir)
    monkeypatch.setattr(
        api,
        "_parse_report_reference",
        lambda _path: (
            {
                "scope": api.ProjectScope.TEAM,
                "project_name": "demo",
                "bot_name": "gitbot",
                "source": source,
            },
            None,
            None,
        ),
    )

    body, status = api.save_report_improvement(
        {
            "path": "reports/demo/gitbot/report.md",
            "improved": "# Report\n\nImproved text",
        }
    )

    assert status == 201
    assert body["artifacts"]["md"].startswith("reports/demo/reportbot/gitbot-report-reportbot-improved-")
    saved_file = reports_dir / body["saved"]["filename"]
    assert saved_file.exists()
    assert saved_file.read_text(encoding="utf-8") == "# Report\n\nImproved text"


def test_preview_report_improvement_requires_api_key(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "report.md"
    source.write_text("# Report\n\nOriginal text", encoding="utf-8")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(
        api,
        "_parse_report_reference",
        lambda _path: (
            {
                "scope": api.ProjectScope.TEAM,
                "project_name": "demo",
                "bot_name": "gitbot",
                "source": source,
            },
            None,
            None,
        ),
    )

    body, status = api.preview_report_improvement(
        {"path": "reports/demo/gitbot/report.md"}
    )

    assert status == 400
    assert body["error"] == "ANTHROPIC_API_KEY is not set."


def test_start_voice_command_job_runs_inline_and_persists_result(monkeypatch) -> None:
    _clear_voice_jobs()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        api,
        "_execute_voice_command_payload",
        lambda data: (
            {
                "kind": "bot_result",
                "transcript": data["transcript"],
                "result": {
                    "bot_name": "taskbot",
                    "project_name": "journal",
                    "summary": "Found open tasks.",
                },
            },
            200,
        ),
    )
    monkeypatch.setattr(api.threading, "Thread", _InlineThread)

    body, status = api.start_voice_command_job(
        {"transcript": "analiza mis tareas", "locale": "es-CO"}
    )

    assert status == 202
    assert body["status"] == "queued"
    job_body, job_status = api.get_voice_command_job(body["job_id"])
    assert job_status == 200
    assert job_body["status"] == "completed"
    assert job_body["result"]["kind"] == "bot_result"
    assert job_body["result"]["transcript"] == "analiza mis tareas"
    _clear_voice_jobs()


def test_start_voice_command_job_requires_api_key(monkeypatch) -> None:
    _clear_voice_jobs()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    body, status = api.start_voice_command_job({"transcript": "analiza mis tareas"})

    assert status == 400
    assert "ANTHROPIC_API_KEY" in body["error"]


def test_get_voice_command_job_returns_not_found_for_unknown_id() -> None:
    _clear_voice_jobs()

    body, status = api.get_voice_command_job("missing-job")

    assert status == 404
    assert "was not found" in body["error"]
