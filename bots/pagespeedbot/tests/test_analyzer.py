from __future__ import annotations

from pathlib import Path

from pagespeedbot import analyzer
from shared.models import BotStatus, ProjectScope
from shared.report_export import ReportExportResult


def _sample_payload(strategy: str) -> dict:
    return {
        "id": f"https://example.com/{strategy}",
        "loadingExperience": {
            "overall_category": "FAST",
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {"category": "FAST", "percentile": 1800, "distributions": []},
                "CUMULATIVE_LAYOUT_SHIFT_SCORE": {"category": "FAST", "percentile": 10, "distributions": []},
            },
        },
        "originLoadingExperience": {
            "overall_category": "AVERAGE",
            "metrics": {
                "LARGEST_CONTENTFUL_PAINT_MS": {"category": "AVERAGE", "percentile": 2400, "distributions": []},
            },
        },
        "lighthouseResult": {
            "finalDisplayedUrl": "https://example.com/",
            "fetchTime": "2026-03-16T12:00:00.000Z",
            "userAgent": "Mozilla/5.0 Test Agent",
            "categories": {
                "performance": {"score": 0.91},
                "accessibility": {"score": 0.88},
                "best-practices": {"score": 0.95},
                "seo": {"score": 1.0},
                "pwa": {"score": 0.42},
            },
            "audits": {
                "first-contentful-paint": {"displayValue": "1.1 s", "numericValue": 1100},
                "largest-contentful-paint": {"displayValue": "1.8 s", "numericValue": 1800},
                "speed-index": {"displayValue": "2.0 s", "numericValue": 2000},
                "total-blocking-time": {"displayValue": "10 ms", "numericValue": 10},
                "cumulative-layout-shift": {"displayValue": "0.01", "numericValue": 0.01},
                "interactive": {"displayValue": "2.2 s", "numericValue": 2200},
                "server-response-time": {"displayValue": "120 ms", "numericValue": 120},
                "render-blocking-resources": {"displayValue": "Potential savings of 120 ms", "score": 0.5, "details": {"overallSavingsMs": 120}},
                "unused-css-rules": {"displayValue": "Potential savings of 10 KiB", "score": 0.7, "details": {"overallSavingsBytes": 10240}},
                "largest-contentful-paint-element": {"displayValue": "Hero image", "score": 0.3},
                "dom-size": {"displayValue": "120 elements", "score": 0.9},
                "document-title": {"displayValue": "Document has a title element", "score": 1},
            },
        },
    }


def _sample_html() -> str:
    return """
    <html lang="en">
      <head>
        <title>Example Title for Testing Search Visibility and Clicks</title>
        <meta name="description" content="This is a sample meta description used to verify the on-page SEO parser inside PageSpeedBot for reporting and issue detection output.">
        <meta property="og:title" content="Example OG Title">
        <meta property="og:description" content="Example OG Description">
        <meta property="og:url" content="https://example.com/">
        <meta name="twitter:card" content="summary_large_image">
        <link rel="canonical" href="https://example.com/">
        <script type="application/ld+json">{"@context":"https://schema.org"}</script>
      </head>
      <body>
        <h1>Main heading</h1>
        <h2>Support heading</h2>
        <img src="hero.jpg" alt="Hero image" width="800" height="600">
      </body>
    </html>
    """


def _fake_text_response(url: str, timeout: int = 30):
    if url.endswith("/robots.txt"):
        return 200, "User-agent: *\nAllow: /\nSitemap: https://example.com/sitemap.xml\n", ""
    if url.endswith("/sitemap.xml"):
        return 200, "<urlset><url><loc>https://example.com/</loc></url></urlset>", ""
    if url.endswith("/llms.txt"):
        return 200, "# llms\nAllow: /\n", ""
    raise AssertionError(f"Unexpected URL: {url}")


def test_get_bot_result_collects_mobile_and_desktop_and_saves_files(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        analyzer,
        "fetch_pagespeed_payload",
        lambda url, strategy, categories, timeout=120: _sample_payload(strategy),
    )
    monkeypatch.setattr(analyzer, "fetch_html", lambda url, timeout=30: _sample_html())
    monkeypatch.setattr(analyzer, "fetch_text_response", _fake_text_response)

    saved_reports: list[tuple[str, str, str, ProjectScope]] = []
    saved_artifacts: list[tuple[str, str, dict, ProjectScope]] = []

    monkeypatch.setattr(
        analyzer,
        "save_report",
        lambda project_name, bot, content, scope=ProjectScope.TEAM: (
            saved_reports.append((project_name, bot, content, scope)) or tmp_path / "latest.md",
            tmp_path / "timestamped.md",
        ),
    )
    monkeypatch.setattr(
        analyzer,
        "save_json_artifact",
        lambda project_name, bot, data, scope=ProjectScope.TEAM: (
            saved_artifacts.append((project_name, bot, data, scope)) or tmp_path / "latest.json",
            tmp_path / "timestamped.json",
        ),
    )
    monkeypatch.setattr(
        analyzer,
        "export_report_files",
        lambda markdown_content, **kwargs: ReportExportResult(
            html="<html><body>export</body></html>",
            pdf_bytes=b"%PDF-1.7",
            html_paths=(tmp_path / "latest.html", tmp_path / "timestamped.html"),
            pdf_paths=(tmp_path / "latest.pdf", tmp_path / "timestamped.pdf"),
        ),
    )

    result = analyzer.get_bot_result(
        "https://example.com",
        audit_urls=("https://example.com/about",),
        project_name="Demo",
    )

    assert result.status == BotStatus.SUCCESS
    assert "2 URL(s)" in result.summary
    assert "| Metric | Value |" in result.markdown_report
    assert "## Priority Summary" in result.markdown_report
    assert "| Category | Score |" in result.markdown_report
    assert "## Top 5 Recommended Fixes" in result.markdown_report
    assert "| Priority | Source | Recommendation |" in result.markdown_report
    assert "#### Field Data" in result.markdown_report
    assert "#### Opportunities" in result.markdown_report
    assert "#### Diagnostics" in result.markdown_report
    assert "#### Environment" in result.markdown_report
    assert "## Site Files" in result.markdown_report
    assert "| robots.txt | 200 | yes |" in result.markdown_report
    assert saved_reports[0][0] == "Demo"
    assert saved_reports[0][1] == "pagespeedbot"
    assert saved_artifacts[0][0] == "Demo"
    assert set(saved_artifacts[0][2]["raw"].keys()) == {
        "https://example.com",
        "https://example.com/about",
    }
    assert set(saved_artifacts[0][2]["raw"]["https://example.com"].keys()) == {"mobile", "desktop"}
    assert result.data["export_saved"]["html"]["latest"].endswith("latest.html")
    assert result.data["export_saved"]["pdf"]["latest"].endswith("latest.pdf")


def test_get_bot_result_returns_partial_when_one_strategy_fails(monkeypatch) -> None:
    def _fake_fetch(url, strategy, categories, timeout=120):
        if strategy == "desktop":
            raise RuntimeError("desktop failed")
        return _sample_payload(strategy)

    monkeypatch.setattr(analyzer, "fetch_pagespeed_payload", _fake_fetch)
    monkeypatch.setattr(analyzer, "fetch_html", lambda url, timeout=30: _sample_html())
    monkeypatch.setattr(analyzer, "fetch_text_response", _fake_text_response)
    monkeypatch.setattr(
        analyzer,
        "export_report_files",
        lambda markdown_content, **kwargs: ReportExportResult(html="<html></html>"),
    )

    result = analyzer.get_bot_result("https://example.com")

    assert result.status == BotStatus.PARTIAL
    assert result.errors == ["https://example.com [desktop]: desktop failed"]
    assert "### Mobile" in result.markdown_report
    assert "## Errors" in result.markdown_report


def test_get_bot_result_marks_partial_when_report_export_fails(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        analyzer,
        "fetch_pagespeed_payload",
        lambda url, strategy, categories, timeout=120: _sample_payload(strategy),
    )
    monkeypatch.setattr(analyzer, "fetch_html", lambda url, timeout=30: _sample_html())
    monkeypatch.setattr(analyzer, "fetch_text_response", _fake_text_response)
    monkeypatch.setattr(
        analyzer,
        "save_report",
        lambda project_name, bot, content, scope=ProjectScope.TEAM: (tmp_path / "latest.md", tmp_path / "timestamped.md"),
    )
    monkeypatch.setattr(
        analyzer,
        "save_json_artifact",
        lambda project_name, bot, data, scope=ProjectScope.TEAM: (tmp_path / "latest.json", tmp_path / "timestamped.json"),
    )
    monkeypatch.setattr(
        analyzer,
        "export_report_files",
        lambda markdown_content, **kwargs: ReportExportResult(
            html="<html></html>",
            errors=["PDF export requires WeasyPrint to be installed."],
        ),
    )

    result = analyzer.get_bot_result("https://example.com", project_name="Demo")

    assert result.status == BotStatus.PARTIAL
    assert "report-export: PDF export requires WeasyPrint to be installed." in result.errors


def test_build_pagespeed_url_includes_categories_and_strategy() -> None:
    url = analyzer.build_pagespeed_url(
        "https://example.com",
        "mobile",
        categories=("performance", "seo"),
    )

    assert "url=https%3A%2F%2Fexample.com" in url
    assert "strategy=mobile" in url
    assert "category=performance" in url
    assert "category=seo" in url


def test_build_audit_url_list_deduplicates_and_keeps_order() -> None:
    urls = analyzer.build_audit_url_list(
        "https://example.com",
        audit_urls=("https://example.com/about", "https://example.com", "  ", "https://example.com/contact"),
    )

    assert urls == [
        "https://example.com",
        "https://example.com/about",
        "https://example.com/contact",
    ]


def test_analyze_on_page_seo_extracts_core_signals() -> None:
    result = analyzer.analyze_on_page_seo("https://example.com", _sample_html())

    assert result["score"] >= 80
    assert result["h1_count"] == 1
    assert result["schema_count"] == 1
    assert result["images_missing_alt"] == 0
    assert result["canonical"] == "https://example.com/"


def test_analyze_site_files_detects_robots_sitemap_and_llms(monkeypatch) -> None:
    monkeypatch.setattr(analyzer, "fetch_text_response", _fake_text_response)

    result = analyzer.analyze_site_files("https://example.com")

    assert result["robots"]["exists"] is True
    assert result["sitemap"]["exists"] is True
    assert result["sitemap"]["valid_xml"] is True
    assert result["sitemap"]["url_count"] == 1
    assert result["llms"]["exists"] is True
