from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_DIR = REPO_ROOT / "dashboard"
if str(DASHBOARD_DIR) not in sys.path:
    sys.path.insert(0, str(DASHBOARD_DIR))

import api  # noqa: E402


def _install_fake_reportbot(monkeypatch, improved_text: str, translated_text: str = "# Bericht\n\nUebersetzt") -> None:
    package = ModuleType("reportbot")
    analyzer = ModuleType("reportbot.analyzer")

    def improve_report(content: str, title: str = "", instructions_file=None) -> str:
        assert content
        assert title
        return improved_text

    def translate_report(content: str, target_language: str, title: str = "", instructions_file=None) -> str:
        assert content
        assert title
        assert target_language
        return translated_text

    analyzer.improve_report = improve_report
    analyzer.translate_report = translate_report
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


def test_create_team_project_allows_url_only_setup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    registry = api.ProjectRegistry(tmp_path / "projects.json")
    data_root = tmp_path / "data-root"
    monkeypatch.setattr(api, "_registry", lambda: registry)
    monkeypatch.setattr(api, "_regenerate_dashboard", lambda: None)
    monkeypatch.setattr(api, "get_data_root", lambda: data_root)

    body, status = api.create_project(
        {
            "name": "UniLiLegacy",
            "scope": "team",
            "path": "",
            "site_url": "https://uni.li",
            "report_branding_profile": "protonsystems",
            "report_prepared_by": "ProtonSystems",
            "report_client_name": "UniLi",
        }
    )

    assert status == 201
    assert body["name"] == "UniLiLegacy"
    assert body["site_url"] == "https://uni.li"
    assert body["path"] == str(data_root / "_url_projects" / "UniLiLegacy")
    assert (data_root / "_url_projects" / "UniLiLegacy").is_dir()


def test_create_project_stores_languages_and_frameworks(
    monkeypatch,
    tmp_path: Path,
) -> None:
    registry = api.ProjectRegistry(tmp_path / "projects.json")
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    monkeypatch.setattr(api, "_registry", lambda: registry)
    monkeypatch.setattr(api, "_regenerate_dashboard", lambda: None)

    body, status = api.create_project(
        {
            "name": "UniLi",
            "scope": "team",
            "path": str(repo_path),
            "language": "php",
            "languages": "php, javascript",
            "frameworks": "Drupal, Symfony",
        }
    )

    assert status == 201
    assert body["language"] == "php"
    assert body["languages"] == ["php", "javascript"]
    assert body["frameworks"] == ["Drupal", "Symfony"]


def test_create_team_project_still_requires_path_without_site_url(
    monkeypatch,
    tmp_path: Path,
) -> None:
    registry = api.ProjectRegistry(tmp_path / "projects.json")
    monkeypatch.setattr(api, "_registry", lambda: registry)
    monkeypatch.setattr(api, "_regenerate_dashboard", lambda: None)

    body, status = api.create_project(
        {
            "name": "NoUrlProject",
            "scope": "team",
            "path": "",
        }
    )

    assert status == 400
    assert body["error"] == "Path is required for team projects unless a Site URL is configured."


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


def test_preview_report_translation_returns_translated_markdown(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "report.md"
    source.write_text("# Report\n\nOriginal text", encoding="utf-8")
    _install_fake_reportbot(monkeypatch, "# Report\n\nImproved text", "# Bericht\n\nUebersetzter Text")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        api,
        "_parse_report_reference",
        lambda _path: (
            {
                "scope": api.ProjectScope.TEAM,
                "project_name": "demo",
                "bot_name": "pagespeedbot",
                "source": source,
            },
            None,
            None,
        ),
    )

    body, status = api.preview_report_translation(
        {"path": "reports/demo/pagespeedbot/report.md", "target_language": "de"}
    )

    assert status == 200
    assert body["translated"] == "# Bericht\n\nUebersetzter Text"
    assert body["target_language"] == "de"
    assert body["target_language_name"] == "German"


def test_save_report_translation_writes_source_bot_sibling_and_exports(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "2026-03-21-184926.md"
    source.write_text("# Report\n\nOriginal text", encoding="utf-8")
    monkeypatch.setattr(api, "_regenerate_dashboard", lambda: None)
    reports_dir = tmp_path / "data" / "demo" / "reports" / "pagespeedbot"
    monkeypatch.setattr(api, "get_reports_dir", lambda *args, **kwargs: reports_dir)
    monkeypatch.setattr(
        api,
        "_parse_report_reference",
        lambda _path: (
            {
                "scope": api.ProjectScope.TEAM,
                "project_name": "demo",
                "bot_name": "pagespeedbot",
                "source": source,
            },
            None,
            None,
        ),
    )
    monkeypatch.setattr(
        api,
        "_registry",
        lambda: SimpleNamespace(
            get_project=lambda _name: SimpleNamespace(
                report_branding_profile="protonsystems",
                report_prepared_by="ProtonSystems",
                report_client_name="UniLi",
                report_footer_text=None,
            )
        ),
    )
    monkeypatch.setattr(
        api,
        "export_report_file",
        lambda report_path, **kwargs: SimpleNamespace(
            html_paths=(report_path.with_suffix(".html"), None),
            pdf_paths=(report_path.with_suffix(".pdf"), None),
            errors=[],
        ),
    )

    body, status = api.save_report_translation(
        {
            "path": "reports/demo/pagespeedbot/2026-03-21-184926.md",
            "translated": "# Bericht\n\nUebersetzter Text",
            "target_language": "de",
        }
    )

    assert status == 201
    assert body["artifacts"]["md"].startswith("reports/demo/pagespeedbot/2026-03-21-184926-reportbot-translation-de-")
    assert body["artifacts"]["html"].endswith(".html")
    assert body["artifacts"]["pdf"].endswith(".pdf")
    saved_file = reports_dir / body["saved"]["filename"]
    assert saved_file.exists()
    assert saved_file.read_text(encoding="utf-8") == "# Bericht\n\nUebersetzter Text"
    assert body["saved"]["target_language"] == "de"
    assert body["saved"]["bot_name"] == "pagespeedbot"


def test_save_report_translation_from_reportbot_improvement_uses_original_bot(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "pagespeedbot-2026-03-21-184926-reportbot-improved-2026-03-21-193849.md"
    source.write_text("# Report\n\nImproved text", encoding="utf-8")
    monkeypatch.setattr(api, "_regenerate_dashboard", lambda: None)
    reports_dir = tmp_path / "data" / "demo" / "reports" / "pagespeedbot"
    monkeypatch.setattr(api, "get_reports_dir", lambda *args, **kwargs: reports_dir)
    monkeypatch.setattr(
        api,
        "_parse_report_reference",
        lambda _path: (
            {
                "scope": api.ProjectScope.TEAM,
                "project_name": "demo",
                "bot_name": "reportbot",
                "source": source,
            },
            None,
            None,
        ),
    )
    monkeypatch.setattr(
        api,
        "_registry",
        lambda: SimpleNamespace(
            get_project=lambda _name: SimpleNamespace(
                report_branding_profile="protonsystems",
                report_prepared_by="ProtonSystems",
                report_client_name="UniLi",
                report_footer_text=None,
                site_url="https://unili.proton.systems",
            )
        ),
    )
    monkeypatch.setattr(
        api,
        "export_report_file",
        lambda report_path, **kwargs: SimpleNamespace(
            html_paths=(report_path.with_suffix(".html"), None),
            pdf_paths=(report_path.with_suffix(".pdf"), None),
            errors=[],
        ),
    )

    body, status = api.save_report_translation(
        {
            "path": (
                "reports/demo/reportbot/"
                "pagespeedbot-2026-03-21-184926-reportbot-improved-2026-03-21-193849.md"
            ),
            "translated": "# Bericht\n\nUebersetzter Text",
            "target_language": "de",
        }
    )

    assert status == 201
    assert body["artifacts"]["md"].startswith("reports/demo/pagespeedbot/")
    assert body["artifacts"]["html"].startswith("reports/demo/pagespeedbot/")
    assert body["artifacts"]["pdf"].startswith("reports/demo/pagespeedbot/")
    assert body["saved"]["bot_name"] == "pagespeedbot"


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


def test_metadata_for_existing_pagespeed_report_uses_project_overrides(tmp_path: Path) -> None:
    source = tmp_path / "report.md"
    source.write_text("# Report\n\nDemo", encoding="utf-8")
    project = SimpleNamespace(
        report_branding_profile="default",
        report_prepared_by="Strategy Lab",
        report_client_name="Acme Corp",
        report_footer_text="Prepared by Strategy Lab for Acme Corp",
    )

    metadata = api._metadata_for_existing_report("Demo", "pagespeedbot", source, project=project)

    assert metadata["project_name"] == "Acme Corp"
    assert metadata["primary_url"] == "Acme Corp"
    assert metadata["author"] == "Strategy Lab"
    assert metadata["footer_text"] == "Prepared by Strategy Lab for Acme Corp"


def test_metadata_for_translated_pagespeed_report_is_localized(tmp_path: Path) -> None:
    source = tmp_path / "2026-03-21-184926-reportbot-translation-de-2026-03-22-000001.md"
    source.write_text("# Bericht\n\nDemo", encoding="utf-8")
    project = SimpleNamespace(
        report_branding_profile="protonsystems",
        report_prepared_by="ProtonSystems",
        report_client_name="UniLi",
        report_footer_text=None,
        site_url="https://unili.proton.systems",
    )

    metadata = api._metadata_for_existing_report("Demo", "pagespeedbot", source, project=project)

    assert metadata["lang"] == "de"
    assert metadata["title"] == "SEO- und Performance-Bericht"
    assert metadata["primary_url"] == "https://unili.proton.systems"
    assert metadata["confidentiality"] == "Vertraulich"
    assert metadata["footer_text"] == "Erstellt von ProtonSystems fuer UniLi"
