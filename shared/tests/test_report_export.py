from __future__ import annotations

from pathlib import Path

from shared.models import ProjectScope
from shared.report_export import (
    ReportBranding,
    ReportHighlight,
    export_report_file,
    export_report_files,
    render_report_html,
)


def test_render_report_html_includes_branding_and_markdown_tables(tmp_path: Path) -> None:
    logo_path = tmp_path / "logo.svg"
    logo_path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20" fill="#000"/></svg>',
        encoding="utf-8",
    )

    html = render_report_html(
        "# Report\n\n| A | B |\n| --- | --- |\n| 1 | 2 |",
        template_name="pagespeed",
        metadata={
            "title": "SEO & Performance Report",
            "project_name": "Example",
            "primary_url": "https://example.com",
            "highlights": [ReportHighlight("URLs Audited", "2", accent=True)],
        },
        branding=ReportBranding(company_name="Example Co", logo_path=str(logo_path)),
    )

    assert "SEO &amp; Performance Report" not in html
    assert "SEO & Performance Report" in html
    assert "Example Co" in html
    assert "data:image/svg+xml;base64," in html
    assert "<table>" in html
    assert "URLs Audited" in html
    assert "report-chapter" in html


def test_export_report_files_saves_html_and_pdf(monkeypatch, tmp_path: Path) -> None:
    saved_calls: list[tuple[str, str, object]] = []

    def _fake_save(project_name, bot, content, extension, scope=ProjectScope.TEAM, save_latest=True, save_timestamped=True):
        saved_calls.append((bot, extension, content))
        return (tmp_path / f"latest.{extension}", tmp_path / f"timestamped.{extension}")

    monkeypatch.setattr("shared.report_export.save_report_artifact", _fake_save)
    monkeypatch.setattr("shared.report_export.render_pdf", lambda html_content, base_url=None: b"%PDF-test")

    result = export_report_files(
        "# Demo",
        project_name="Demo",
        bot="pagespeedbot",
        template_name="pagespeed",
        metadata={"title": "SEO & Performance Report", "project_name": "Demo"},
    )

    assert result.html_paths == (tmp_path / "latest.html", tmp_path / "timestamped.html")
    assert result.pdf_paths == (tmp_path / "latest.pdf", tmp_path / "timestamped.pdf")
    assert result.pdf_bytes == b"%PDF-test"
    assert [call[1] for call in saved_calls] == ["html", "pdf"]


def test_export_report_files_keeps_html_when_pdf_render_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "shared.report_export.save_report_artifact",
        lambda project_name, bot, content, extension, scope=ProjectScope.TEAM, save_latest=True, save_timestamped=True: (
            tmp_path / f"latest.{extension}",
            tmp_path / f"timestamped.{extension}",
        ),
    )
    monkeypatch.setattr(
        "shared.report_export.render_pdf",
        lambda html_content, base_url=None: (_ for _ in ()).throw(RuntimeError("missing weasyprint")),
    )

    result = export_report_files(
        "# Demo",
        project_name="Demo",
        bot="pagespeedbot",
        metadata={"project_name": "Demo"},
    )

    assert result.html_paths == (tmp_path / "latest.html", tmp_path / "timestamped.html")
    assert result.pdf_paths is None
    assert result.errors == ["missing weasyprint"]


def test_export_report_file_writes_sibling_html_and_pdf(monkeypatch, tmp_path: Path) -> None:
    report_path = tmp_path / "2026-03-18-120000.md"
    report_path.write_text("# Demo\n\nContent", encoding="utf-8")
    monkeypatch.setattr("shared.report_export.render_pdf", lambda html_content, base_url=None: b"%PDF-sibling")

    result = export_report_file(
        report_path,
        template_name="protonsystems_audit",
        branding_name="protonsystems",
        metadata={"project_name": "Demo", "primary_url": "https://example.com"},
    )

    assert report_path.with_suffix(".html").exists()
    assert report_path.with_suffix(".pdf").exists()
    assert result.html_paths == (report_path.with_suffix(".html"), None)
    assert result.pdf_paths == (report_path.with_suffix(".pdf"), None)
