"""PageSpeedBot analyzer — collect raw PageSpeed Insights reports."""

from __future__ import annotations

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from shared.data_manager import save_json_artifact, save_report
from shared.models import BotResult, BotStatus, ProjectScope
from shared.report_export import (
    ReportHighlight,
    ReportSettings,
    export_report_files,
    resolve_report_branding_name,
    resolve_report_client_name,
    resolve_report_footer_text,
    resolve_report_presenter,
    resolve_report_template_name,
)

PAGESPEED_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
DEFAULT_CATEGORIES = (
    "performance",
    "accessibility",
    "best-practices",
    "seo",
    "pwa",
)
DEFAULT_STRATEGIES = ("mobile", "desktop")
CORE_AUDITS = {
    "first-contentful-paint": "FCP",
    "largest-contentful-paint": "LCP",
    "speed-index": "Speed Index",
    "total-blocking-time": "TBT",
    "cumulative-layout-shift": "CLS",
    "interactive": "TTI",
    "server-response-time": "Server Response Time",
}
LIGHTHOUSE_ISSUE_AUDITS = {
    "document-title": "Document title",
    "meta-description": "Meta description",
    "http-status-code": "HTTP status code",
    "crawlable-anchors": "Crawlable anchors",
    "is-crawlable": "Indexability",
    "link-text": "Link text",
}
OPPORTUNITY_AUDITS = {
    "render-blocking-resources": "Render-blocking resources",
    "unused-css-rules": "Unused CSS",
    "unused-javascript": "Unused JavaScript",
    "modern-image-formats": "Modern image formats",
    "offscreen-images": "Offscreen images",
    "uses-responsive-images": "Responsive images",
    "unminified-css": "Unminified CSS",
    "unminified-javascript": "Unminified JavaScript",
    "server-response-time": "Server response time",
}
DIAGNOSTIC_AUDITS = {
    "largest-contentful-paint-element": "LCP element",
    "mainthread-work-breakdown": "Main thread work",
    "bootup-time": "Bootup time",
    "network-requests": "Network requests",
    "network-rtt": "Network RTT",
    "network-server-latency": "Server latency",
    "total-byte-weight": "Total byte weight",
    "dom-size": "DOM size",
    "third-party-summary": "Third-party impact",
}


class SeoHTMLParser(HTMLParser):
    """Collect a few high-value on-page SEO signals."""

    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.in_title = False
        self.html_lang: str | None = None
        self.meta: dict[str, str] = {}
        self.property_meta: dict[str, str] = {}
        self.links: dict[str, list[str]] = {}
        self.h1_count = 0
        self.h2_count = 0
        self.schema_count = 0
        self.image_count = 0
        self.images_missing_alt = 0
        self.images_missing_dimensions = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): (value or "") for key, value in attrs}
        tag = tag.lower()

        if tag == "html":
            self.html_lang = attr_map.get("lang") or self.html_lang
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            name = attr_map.get("name", "").lower()
            prop = attr_map.get("property", "").lower()
            content = attr_map.get("content", "")
            if name:
                self.meta[name] = content
            if prop:
                self.property_meta[prop] = content
        elif tag == "link":
            rel_values = [value.strip().lower() for value in attr_map.get("rel", "").split() if value.strip()]
            href = attr_map.get("href", "")
            for rel in rel_values:
                self.links.setdefault(rel, []).append(href)
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "h2":
            self.h2_count += 1
        elif tag == "script" and attr_map.get("type", "").lower() == "application/ld+json":
            self.schema_count += 1
        elif tag == "img":
            self.image_count += 1
            if not attr_map.get("alt", "").strip():
                self.images_missing_alt += 1
            if not (attr_map.get("width", "").strip() and attr_map.get("height", "").strip()):
                self.images_missing_dimensions += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)

    @property
    def title(self) -> str:
        return " ".join(part.strip() for part in self.title_parts if part.strip()).strip()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_audit_url_list(site_url: str, audit_urls: tuple[str, ...] = ()) -> list[str]:
    urls: list[str] = []
    for candidate in (site_url, *audit_urls):
        cleaned = candidate.strip()
        if cleaned and cleaned not in urls:
            urls.append(cleaned)
    return urls


def build_pagespeed_url(
    url: str,
    strategy: str,
    categories: tuple[str, ...] = DEFAULT_CATEGORIES,
) -> str:
    params: list[tuple[str, str]] = [("url", url), ("strategy", strategy)]
    for category in categories:
        params.append(("category", category))

    api_key = os.environ.get("PAGESPEED_API_KEY")
    if api_key:
        params.append(("key", api_key))

    return f"{PAGESPEED_ENDPOINT}?{urlencode(params)}"


def fetch_pagespeed_payload(
    url: str,
    strategy: str,
    categories: tuple[str, ...] = DEFAULT_CATEGORIES,
    timeout: int = 120,
) -> dict[str, Any]:
    request = Request(
        build_pagespeed_url(url, strategy, categories),
        headers={"User-Agent": "DevBots-PageSpeedBot/0.1"},
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_html(url: str, timeout: int = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; DevBots-PageSpeedBot/0.1)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def fetch_text_response(url: str, timeout: int = 30) -> tuple[int | None, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; DevBots-PageSpeedBot/0.1)",
            "Accept": "text/plain,text/xml,application/xml,*/*",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.status, response.read().decode(charset, errors="replace"), ""
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
        return exc.code, body, str(exc)
    except URLError as exc:
        return None, "", str(exc)


def analyze_site_files(site_url: str, timeout: int = 30) -> dict[str, dict[str, Any]]:
    robots_url = urljoin(site_url, "/robots.txt")
    llms_url = urljoin(site_url, "/llms.txt")
    default_sitemap_url = urljoin(site_url, "/sitemap.xml")

    robots_status, robots_body, robots_error = fetch_text_response(robots_url, timeout=timeout)
    sitemap_urls = [default_sitemap_url]
    if robots_body:
        for line in robots_body.splitlines():
            if line.lower().startswith("sitemap:") and ":" in line:
                sitemap_url = line.split(":", 1)[1].strip()
                if sitemap_url and sitemap_url not in sitemap_urls:
                    sitemap_urls.append(sitemap_url)

    sitemap_result: dict[str, Any] = {
        "url": sitemap_urls[0],
        "status": None,
        "exists": False,
        "valid_xml": False,
        "url_count": None,
        "notes": [],
    }
    for sitemap_url in sitemap_urls:
        sitemap_status, sitemap_body, sitemap_error = fetch_text_response(sitemap_url, timeout=timeout)
        candidate: dict[str, Any] = {
            "url": sitemap_url,
            "status": sitemap_status,
            "exists": sitemap_status == 200,
            "valid_xml": False,
            "url_count": None,
            "notes": [],
        }
        if sitemap_error:
            candidate["notes"].append(sitemap_error)
        if sitemap_status == 200 and sitemap_body:
            try:
                root = ET.fromstring(sitemap_body)
                candidate["valid_xml"] = True
                loc_count = len(root.findall(".//{*}loc"))
                candidate["url_count"] = loc_count
                candidate["notes"].append(f"Detected {loc_count} loc entries")
            except ET.ParseError as exc:
                candidate["notes"].append(f"Invalid XML: {exc}")
        sitemap_result = candidate
        if candidate["exists"]:
            break

    llms_status, llms_body, llms_error = fetch_text_response(llms_url, timeout=timeout)
    llms_lines = [line.strip() for line in llms_body.splitlines() if line.strip()]

    robots_notes: list[str] = []
    if robots_error:
        robots_notes.append(robots_error)
    if robots_status == 200:
        if any(line.lower().startswith("user-agent:") for line in robots_body.splitlines()):
            robots_notes.append("Contains user-agent directives")
        sitemap_refs = [line for line in robots_body.splitlines() if line.lower().startswith("sitemap:")]
        if sitemap_refs:
            robots_notes.append(f"References {len(sitemap_refs)} sitemap declaration(s)")

    llms_notes: list[str] = []
    if llms_error:
        llms_notes.append(llms_error)
    if llms_status == 200:
        llms_notes.append(f"Contains {len(llms_lines)} non-empty line(s)")

    return {
        "robots": {
            "url": robots_url,
            "status": robots_status,
            "exists": robots_status == 200,
            "notes": robots_notes,
        },
        "sitemap": sitemap_result,
        "llms": {
            "url": llms_url,
            "status": llms_status,
            "exists": llms_status == 200,
            "notes": llms_notes,
        },
    }


def _score_from_category(category: dict[str, Any] | None) -> int | None:
    if not category:
        return None
    score = category.get("score")
    if score is None:
        return None
    return int(round(score * 100))


def _extract_strategy_summary(payload: dict[str, Any]) -> dict[str, Any]:
    lighthouse = payload.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    audits = lighthouse.get("audits", {})

    return {
        "scores": {
            "performance": _score_from_category(categories.get("performance")),
            "accessibility": _score_from_category(categories.get("accessibility")),
            "best_practices": _score_from_category(categories.get("best-practices")),
            "seo": _score_from_category(categories.get("seo")),
            "pwa": _score_from_category(categories.get("pwa")),
        },
        "metrics": {
            audit_id: {
                "label": label,
                "display_value": audits.get(audit_id, {}).get("displayValue"),
                "numeric_value": audits.get(audit_id, {}).get("numericValue"),
                "score": audits.get(audit_id, {}).get("score"),
            }
            for audit_id, label in CORE_AUDITS.items()
        },
        "crux": payload.get("loadingExperience", {}),
        "origin_crux": payload.get("originLoadingExperience", {}),
        "field_data": _extract_field_data(payload.get("loadingExperience", {})),
        "origin_field_data": _extract_field_data(payload.get("originLoadingExperience", {})),
        "requested_url": payload.get("id") or payload.get("lighthouseResult", {}).get("requestedUrl"),
        "final_url": lighthouse.get("finalDisplayedUrl") or lighthouse.get("finalUrl"),
        "environment": {
            "fetch_time": lighthouse.get("fetchTime"),
            "user_agent": lighthouse.get("userAgent"),
        },
        "opportunities": _extract_audit_items(audits, OPPORTUNITY_AUDITS),
        "diagnostics": _extract_audit_items(audits, DIAGNOSTIC_AUDITS),
        "lighthouse_issues": [
            {
                "label": label,
                "score": audits.get(audit_id, {}).get("score"),
                "display_value": audits.get(audit_id, {}).get("displayValue"),
            }
            for audit_id, label in LIGHTHOUSE_ISSUE_AUDITS.items()
            if audits.get(audit_id, {}).get("score") not in (None, 1)
        ],
    }


def _extract_field_data(loading_experience: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = loading_experience.get("metrics", {})
    rows: list[dict[str, Any]] = []
    for metric_name, metric in metrics.items():
        rows.append(
            {
                "name": metric_name,
                "category": metric.get("category"),
                "percentile": metric.get("percentile"),
                "distributions": metric.get("distributions", []),
            }
        )
    return rows


def _extract_audit_items(audits: dict[str, Any], audit_labels: dict[str, str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for audit_id, label in audit_labels.items():
        audit = audits.get(audit_id, {})
        if not audit:
            continue
        display_value = audit.get("displayValue")
        numeric_value = audit.get("numericValue")
        details = audit.get("details", {})
        overall_savings = details.get("overallSavingsMs") or details.get("overallSavingsBytes")
        if display_value or numeric_value is not None or overall_savings is not None:
            items.append(
                {
                    "label": label,
                    "score": audit.get("score"),
                    "display_value": display_value,
                    "numeric_value": numeric_value,
                    "overall_savings_ms": details.get("overallSavingsMs"),
                    "overall_savings_bytes": details.get("overallSavingsBytes"),
                }
            )
    return items


def analyze_on_page_seo(url: str, html: str) -> dict[str, Any]:
    parser = SeoHTMLParser()
    parser.feed(html)

    canonical = next(iter(parser.links.get("canonical", [])), "")
    robots = parser.meta.get("robots", "")
    og_tags = {key: value for key, value in parser.property_meta.items() if key.startswith("og:")}
    twitter_tags = {key: value for key, value in parser.meta.items() if key.startswith("twitter:")}

    checks = {
        "title": bool(parser.title),
        "title_length": 50 <= len(parser.title) <= 60 if parser.title else False,
        "meta_description": bool(parser.meta.get("description", "").strip()),
        "meta_description_length": 150 <= len(parser.meta.get("description", "").strip()) <= 160 if parser.meta.get("description") else False,
        "canonical": bool(canonical),
        "lang": bool(parser.html_lang),
        "single_h1": parser.h1_count == 1,
        "og_core": all(og_tags.get(key) for key in ("og:title", "og:description", "og:url")),
        "twitter_core": any(twitter_tags.get(key) for key in ("twitter:card", "twitter:title", "twitter:description")),
        "schema": parser.schema_count > 0,
        "image_alt": parser.image_count == 0 or parser.images_missing_alt == 0,
        "image_dimensions": parser.image_count == 0 or parser.images_missing_dimensions == 0,
        "indexable": "noindex" not in robots.lower(),
    }
    score = int(round(sum(1 for passed in checks.values() if passed) / len(checks) * 100))

    issues: list[dict[str, str]] = []
    if not checks["indexable"]:
        issues.append({"priority": "critical", "message": "Meta robots contains noindex."})
    if not checks["title"]:
        issues.append({"priority": "critical", "message": "Missing title tag."})
    elif not checks["title_length"]:
        issues.append({"priority": "medium", "message": f"Title length is {len(parser.title)} characters; aim for 50-60."})
    if not checks["meta_description"]:
        issues.append({"priority": "high", "message": "Missing meta description."})
    elif not checks["meta_description_length"]:
        desc_len = len(parser.meta.get("description", "").strip())
        issues.append({"priority": "low", "message": f"Meta description length is {desc_len} characters; aim for 150-160."})
    if not checks["single_h1"]:
        issues.append({"priority": "high", "message": f"Expected exactly one H1, found {parser.h1_count}."})
    if not checks["canonical"]:
        issues.append({"priority": "medium", "message": "Missing canonical tag."})
    if not checks["lang"]:
        issues.append({"priority": "medium", "message": "Missing html lang attribute."})
    if not checks["og_core"]:
        issues.append({"priority": "medium", "message": "Missing core Open Graph tags (og:title, og:description, og:url)."})
    if not checks["twitter_core"]:
        issues.append({"priority": "low", "message": "Missing Twitter card tags."})
    if not checks["schema"]:
        issues.append({"priority": "medium", "message": "No JSON-LD schema detected."})
    if parser.images_missing_alt:
        issues.append({"priority": "medium", "message": f"{parser.images_missing_alt} image(s) missing alt text."})
    if parser.images_missing_dimensions:
        issues.append({"priority": "low", "message": f"{parser.images_missing_dimensions} image(s) missing width/height attributes."})

    return {
        "url": url,
        "title": parser.title,
        "title_length": len(parser.title),
        "meta_description": parser.meta.get("description", "").strip(),
        "meta_description_length": len(parser.meta.get("description", "").strip()),
        "canonical": urljoin(url, canonical) if canonical else "",
        "robots": robots,
        "lang": parser.html_lang,
        "h1_count": parser.h1_count,
        "h2_count": parser.h2_count,
        "schema_count": parser.schema_count,
        "image_count": parser.image_count,
        "images_missing_alt": parser.images_missing_alt,
        "images_missing_dimensions": parser.images_missing_dimensions,
        "open_graph_count": len(og_tags),
        "twitter_tag_count": len(twitter_tags),
        "checks": checks,
        "score": score,
        "issues": issues,
    }


def _render_metric_lines(metrics: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for metric in metrics.values():
        display_value = metric.get("display_value")
        if display_value:
            lines.append(f"- {metric['label']}: {display_value}")
    return lines


def _score_badge(score: int | None) -> str:
    if score is None:
        return "n/a"
    if score >= 90:
        return f"{score}/100 good"
    if score >= 50:
        return f"{score}/100 needs work"
    return f"{score}/100 poor"


def _summarize_issues(issue_items: list[dict[str, str]]) -> list[str]:
    ordered = ["critical", "high", "medium", "low"]
    lines: list[str] = []
    for priority in ordered:
        for item in issue_items:
            if item["priority"] == priority:
                lines.append(f"- {priority.upper()}: {item['message']}")
    return lines


def _format_issue_counts(errors: list[str], seo_by_url: dict[str, dict[str, Any]]) -> list[str]:
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for seo_data in seo_by_url.values():
        for item in seo_data.get("issues", []):
            priority = item.get("priority")
            if priority in counts:
                counts[priority] += 1
    if errors:
        counts["critical"] += len(errors)
    return [
        f"- Critical: {counts['critical']}",
        f"- High: {counts['high']}",
        f"- Medium: {counts['medium']}",
        f"- Low: {counts['low']}",
    ]


def _build_overview_table(report: dict[str, Any], mobile_scores: list[int], seo_scores: list[int]) -> list[str]:
    avg_mobile = round(sum(mobile_scores) / len(mobile_scores)) if mobile_scores else None
    avg_seo = round(sum(seo_scores) / len(seo_scores)) if seo_scores else None
    return [
        "| Metric | Value |",
        "| --- | --- |",
        f"| Primary URL | {report['site_url']} |",
        f"| URLs Audited | {len(report['urls'])} |",
        f"| Strategies | {', '.join(report['strategies'])} |",
        f"| Categories | {', '.join(report['categories'])} |",
        f"| Avg Mobile Performance | {avg_mobile if avg_mobile is not None else 'n/a'} |",
        f"| Avg On-Page SEO | {avg_seo if avg_seo is not None else 'n/a'} |",
        f"| Fetched At | {report['fetched_at']} |",
    ]


def _build_on_page_table(seo_data: dict[str, Any]) -> list[str]:
    return [
        "| Signal | Value |",
        "| --- | --- |",
        f"| Score | {_score_badge(seo_data['score'])} |",
        f"| Title | {seo_data['title'] or 'missing'} |",
        f"| Meta Description | {'present' if seo_data['meta_description'] else 'missing'} |",
        f"| Canonical | {seo_data['canonical'] or 'missing'} |",
        f"| H1 Count | {seo_data['h1_count']} |",
        f"| Lang | {seo_data['lang'] or 'missing'} |",
        f"| Schema Blocks | {seo_data['schema_count']} |",
        f"| Images | {seo_data['image_count']} total / {seo_data['images_missing_alt']} missing alt / {seo_data['images_missing_dimensions']} missing dimensions |",
    ]


def _build_strategy_score_table(summary: dict[str, Any]) -> list[str]:
    scores = summary["scores"]
    return [
        "| Category | Score |",
        "| --- | --- |",
        f"| Performance | {_score_badge(scores['performance'])} |",
        f"| Accessibility | {_score_badge(scores['accessibility'])} |",
        f"| Best Practices | {_score_badge(scores['best_practices'])} |",
        f"| Lighthouse SEO | {_score_badge(scores['seo'])} |",
        f"| PWA | {_score_badge(scores['pwa'])} |",
        f"| CrUX | {summary['crux'].get('overall_category', 'n/a')} |",
        f"| Origin CrUX | {summary['origin_crux'].get('overall_category', 'n/a')} |",
    ]


def _build_metrics_table(metrics: dict[str, Any]) -> list[str]:
    rows = [
        "| Metric | Value |",
        "| --- | --- |",
    ]
    for metric in metrics.values():
        display_value = metric.get("display_value")
        if display_value:
            rows.append(f"| {metric['label']} | {display_value} |")
    return rows


def _build_field_data_table(field_data: list[dict[str, Any]]) -> list[str]:
    rows = [
        "| Field Metric | Category | Percentile |",
        "| --- | --- | --- |",
    ]
    for item in field_data:
        percentile = item["percentile"] if item["percentile"] is not None else "n/a"
        rows.append(f"| {item['name']} | {item['category'] or 'n/a'} | {percentile} |")
    return rows


def _build_audit_item_table(title: str, items: list[dict[str, Any]]) -> list[str]:
    rows = ["", title, "", "| Audit | Score | Value | Savings |", "| --- | --- | --- | --- |"]
    for item in items:
        score = item["score"] if item["score"] is not None else "n/a"
        value = item["display_value"] or item["numeric_value"] or "n/a"
        savings_parts = []
        if item.get("overall_savings_ms"):
            savings_parts.append(f"{item['overall_savings_ms']} ms")
        if item.get("overall_savings_bytes"):
            savings_parts.append(f"{item['overall_savings_bytes']} bytes")
        savings = ", ".join(savings_parts) if savings_parts else "-"
        rows.append(f"| {item['label']} | {score} | {value} | {savings} |")
    return rows


def _build_site_files_table(site_files: dict[str, dict[str, Any]]) -> list[str]:
    rows = [
        "| File | Status | Exists | Notes |",
        "| --- | --- | --- | --- |",
    ]
    labels = (("robots", "robots.txt"), ("sitemap", "sitemap.xml"), ("llms", "llms.txt"))
    for key, label in labels:
        item = site_files.get(key, {})
        notes = "; ".join(item.get("notes", [])) or "-"
        rows.append(f"| {label} | {item.get('status', 'n/a')} | {'yes' if item.get('exists') else 'no'} | {notes} |")
    return rows


def _priority_rank(priority: str) -> int:
    return {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
    }.get(priority, 4)


def _build_recommended_fixes(
    site_url: str,
    summary_by_url: dict[str, dict[str, dict[str, Any]]],
    seo_by_url: dict[str, dict[str, Any]],
    site_files: dict[str, dict[str, Any]],
    errors: list[str],
) -> list[str]:
    recommendations: list[dict[str, Any]] = []

    for error in errors:
        if error.startswith(site_url):
            recommendations.append(
                {
                    "priority": "critical",
                    "source": "Request",
                    "action": error,
                }
            )

    seo_data = seo_by_url.get(site_url)
    if seo_data:
        for issue in seo_data.get("issues", []):
            recommendations.append(
                {
                    "priority": issue["priority"],
                    "source": "On-page SEO",
                    "action": issue["message"],
                }
            )

    robots = site_files.get("robots", {})
    if not robots.get("exists"):
        recommendations.append({"priority": "high", "source": "Site files", "action": "Add a robots.txt file for crawler guidance."})

    sitemap = site_files.get("sitemap", {})
    if not sitemap.get("exists"):
        recommendations.append({"priority": "high", "source": "Site files", "action": "Publish a sitemap.xml and reference it from robots.txt."})
    elif not sitemap.get("valid_xml"):
        recommendations.append({"priority": "high", "source": "Site files", "action": "Fix sitemap.xml so it is valid XML."})

    llms = site_files.get("llms", {})
    if not llms.get("exists"):
        recommendations.append({"priority": "low", "source": "Site files", "action": "Consider adding llms.txt for AI crawler guidance."})

    main_summaries = summary_by_url.get(site_url, {})
    for strategy, summary in main_summaries.items():
        for item in summary.get("opportunities", []):
            score = item.get("score")
            priority = "high" if score is not None and score < 0.5 else "medium"
            savings: list[str] = []
            if item.get("overall_savings_ms"):
                savings.append(f"save ~{int(item['overall_savings_ms'])} ms")
            if item.get("overall_savings_bytes"):
                savings.append(f"save ~{int(item['overall_savings_bytes'])} bytes")
            suffix = f" ({', '.join(savings)})" if savings else ""
            recommendations.append(
                {
                    "priority": priority,
                    "source": f"PSI {strategy}",
                    "action": f"{item['label']}{suffix}",
                }
            )

        for item in summary.get("lighthouse_issues", []):
            recommendations.append(
                {
                    "priority": "medium",
                    "source": f"Lighthouse {strategy}",
                    "action": f"Improve {item['label'].lower()}",
                }
            )

    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in recommendations:
        key = (item["source"], item["action"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    deduped.sort(key=lambda item: (_priority_rank(item["priority"]), item["source"], item["action"]))
    top_five = deduped[:5]
    if not top_five:
        return ["- No major fixes identified for the primary URL."]

    return [
        f"| {item['priority'].upper()} | {item['source']} | {item['action']} |"
        for item in top_five
    ]


def render_markdown_report(
    report: dict[str, Any],
    summary_by_url: dict[str, dict[str, dict[str, Any]]],
    seo_by_url: dict[str, dict[str, Any]],
    site_files: dict[str, dict[str, Any]],
    errors: list[str],
) -> str:
    mobile_scores = [
        item.get("mobile", {}).get("scores", {}).get("performance")
        for item in summary_by_url.values()
        if item.get("mobile")
    ]
    seo_scores = [seo_data["score"] for seo_data in seo_by_url.values() if seo_data]

    lines = [
        "# PageSpeedBot Report",
        "",
        "## Overview",
        "",
        *_build_overview_table(report, [score for score in mobile_scores if score is not None], seo_scores),
    ]

    lines.extend(["", "## Priority Summary", ""])
    lines.extend(_format_issue_counts(errors, seo_by_url))
    lines.extend(["", "## Site Files", ""])
    lines.extend(_build_site_files_table(site_files))
    lines.extend([
        "",
        "## Top 5 Recommended Fixes",
        "",
        "| Priority | Source | Recommendation |",
        "| --- | --- | --- |",
    ])
    lines.extend(_build_recommended_fixes(report["site_url"], summary_by_url, seo_by_url, site_files, errors))

    if errors:
        lines.extend(["", "## Errors"])
        lines.extend(f"- {error}" for error in errors)

    for url in report["urls"]:
        summaries = summary_by_url.get(url, {})
        seo_data = seo_by_url.get(url)
        if not summaries and not seo_data:
            continue
        lines.extend(["", f"## {url}"])
        if seo_data:
            lines.extend([
                "",
                "### On-Page SEO",
                "",
                *_build_on_page_table(seo_data),
            ])
            if seo_data["issues"]:
                lines.extend(["", "#### SEO Issues"])
                lines.extend(_summarize_issues(seo_data["issues"]))
        for strategy in report["strategies"]:
            summary = summaries.get(strategy)
            if not summary:
                continue
            lines.extend([
                "",
                f"### {strategy.title()}",
                "",
                *_build_strategy_score_table(summary),
            ])
            lines.extend(["", "#### Metrics", ""])
            lines.extend(_build_metrics_table(summary["metrics"]))
            if summary["lighthouse_issues"]:
                lines.extend(["", "#### Lighthouse Issues"])
                for item in summary["lighthouse_issues"]:
                    suffix = f" ({item['display_value']})" if item.get("display_value") else ""
                    lines.append(f"- {item['label']} score: {item['score']}{suffix}")

            if url == report["site_url"]:
                if summary["field_data"]:
                    lines.extend(["", "#### Field Data", ""])
                    lines.extend(_build_field_data_table(summary["field_data"]))
                if summary["origin_field_data"]:
                    lines.extend(["", "#### Origin Field Data", ""])
                    lines.extend(_build_field_data_table(summary["origin_field_data"]))
                if summary["opportunities"]:
                    lines.extend(_build_audit_item_table("#### Opportunities", summary["opportunities"]))
                if summary["diagnostics"]:
                    lines.extend(_build_audit_item_table("#### Diagnostics", summary["diagnostics"]))
                environment = summary.get("environment", {})
                if environment.get("fetch_time") or environment.get("user_agent"):
                    lines.extend([
                        "",
                        "#### Environment",
                        "",
                        "| Key | Value |",
                        "| --- | --- |",
                        f"| Fetch Time | {environment.get('fetch_time', 'n/a')} |",
                        f"| User Agent | {environment.get('user_agent', 'n/a')} |",
                        f"| Requested URL | {summary.get('requested_url', 'n/a')} |",
                        f"| Final URL | {summary.get('final_url', 'n/a')} |",
                    ])

    return "\n".join(lines)


def _average_score(values: list[int | None]) -> str:
    present = [value for value in values if value is not None]
    if not present:
        return "n/a"
    return str(round(sum(present) / len(present)))


def _build_export_metadata(
    report: dict[str, Any],
    summary_by_url: dict[str, dict[str, dict[str, Any]]],
    seo_by_url: dict[str, dict[str, Any]],
    summary: str,
    project_name: str | None,
    errors: list[str],
    report_settings: ReportSettings | None = None,
) -> dict[str, Any]:
    mobile_scores = [
        item.get("mobile", {}).get("scores", {}).get("performance")
        for item in summary_by_url.values()
        if item.get("mobile")
    ]
    seo_scores = [seo_data.get("score") for seo_data in seo_by_url.values() if seo_data]
    settings = report_settings or ReportSettings()
    branding_name = resolve_report_branding_name("pagespeedbot", settings.branding_profile)
    presenter = resolve_report_presenter("pagespeedbot", settings)
    delivered_to = resolve_report_client_name(project_name or report["site_url"], settings)

    return {
        "title": "SEO & Performance Report",
        "subtitle": "Technical audit export for search visibility, crawl readiness, and performance signals",
        "project_name": delivered_to,
        "primary_url": report["site_url"],
        "generated_at": report["fetched_at"],
        "author": presenter,
        "kicker": f"{presenter or branding_name} Audit",
        "document_type": "SEO & Performance Audit",
        "primary_scope": "Search, Technical SEO, and Core Web Vitals",
        "confidentiality": "Client Confidential",
        "summary": summary,
        "footer_text": resolve_report_footer_text("pagespeedbot", report["site_url"], settings),
        "highlights": [
            ReportHighlight("URLs Audited", str(len(report["urls"])), accent=True),
            ReportHighlight("Avg Mobile Performance", _average_score(mobile_scores)),
            ReportHighlight("Avg On-Page SEO", _average_score(seo_scores)),
            ReportHighlight("Errors", str(len(errors))),
        ],
    }


def get_bot_result(
    site_url: str,
    audit_urls: tuple[str, ...] = (),
    strategies: tuple[str, ...] = DEFAULT_STRATEGIES,
    categories: tuple[str, ...] = DEFAULT_CATEGORIES,
    timeout: int = 120,
    project_name: str | None = None,
    scope: ProjectScope = ProjectScope.TEAM,
    report_branding_profile: str | None = None,
    report_prepared_by: str | None = None,
    report_client_name: str | None = None,
    report_footer_text: str | None = None,
) -> BotResult:
    if not site_url:
        return BotResult.failure("pagespeedbot", "No site URL configured.")

    fetched_at = _utc_now().isoformat().replace("+00:00", "Z")
    urls = build_audit_url_list(site_url, audit_urls)
    report: dict[str, Any] = {
        "bot": "pagespeedbot",
        "site_url": site_url,
        "urls": urls,
        "fetched_at": fetched_at,
        "categories": list(categories),
        "strategies": list(strategies),
        "raw": {},
        "seo_html": {},
        "site_files": {},
    }
    summary_by_url: dict[str, dict[str, dict[str, Any]]] = {}
    seo_by_url: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    try:
        report["site_files"] = analyze_site_files(site_url, timeout=min(timeout, 30))
    except Exception as exc:
        errors.append(f"{site_url} [site-files]: {exc}")
        report["site_files"] = {}

    for url in urls:
        report["raw"][url] = {}
        summary_by_url[url] = {}
        for strategy in strategies:
            try:
                payload = fetch_pagespeed_payload(url, strategy, categories, timeout=timeout)
                report["raw"][url][strategy] = payload
                summary_by_url[url][strategy] = _extract_strategy_summary(payload)
            except Exception as exc:
                errors.append(f"{url} [{strategy}]: {exc}")

        try:
            html = fetch_html(url, timeout=min(timeout, 30))
            seo_data = analyze_on_page_seo(url, html)
            report["seo_html"][url] = seo_data
            seo_by_url[url] = seo_data
        except Exception as exc:
            errors.append(f"{url} [html]: {exc}")

    if not any(report["raw"].values()) and not seo_by_url:
        return BotResult.failure("pagespeedbot", "; ".join(errors) or "No PageSpeed data returned.")

    report["summary"] = summary_by_url
    report["seo_summary"] = seo_by_url
    report_md = render_markdown_report(report, summary_by_url, seo_by_url, report["site_files"], errors)
    status = BotStatus.PARTIAL if errors else BotStatus.SUCCESS
    fetched_urls = [url for url, payloads in report["raw"].items() if payloads]
    summary = f"Fetched PageSpeed Insights for {len(fetched_urls)} URL(s) from {site_url}"

    data: dict[str, Any] = {
        "url": site_url,
        "audit_urls": urls,
        "strategies": list(strategies),
        "categories": list(categories),
        "summary": summary_by_url,
        "raw_report": report,
    }
    report_settings = ReportSettings(
        branding_profile=report_branding_profile,
        prepared_by=report_prepared_by,
        client_name=report_client_name,
        footer_text=report_footer_text,
    )

    if project_name:
        branding_name = resolve_report_branding_name("pagespeedbot", report_settings.branding_profile)
        latest_report, timestamped_report = save_report(project_name, "pagespeedbot", report_md, scope=scope)
        latest_json, timestamped_json = save_json_artifact(project_name, "pagespeedbot", report, scope=scope)
        export_result = export_report_files(
            report_md,
            project_name=project_name,
            bot="pagespeedbot",
            scope=scope,
            template_name=resolve_report_template_name("pagespeedbot", report_settings.branding_profile),
            branding_name=branding_name,
            metadata=_build_export_metadata(
                report,
                summary_by_url,
                seo_by_url,
                summary,
                project_name,
                errors,
                report_settings,
            ),
        )
        data["report_saved"] = {
            "latest": str(latest_report),
            "timestamped": str(timestamped_report) if timestamped_report else None,
        }
        data["artifact_saved"] = {
            "latest": str(latest_json),
            "timestamped": str(timestamped_json) if timestamped_json else None,
        }
        data["export_saved"] = export_result.to_dict()
        if export_result.errors:
            errors.extend([f"report-export: {error}" for error in export_result.errors])

    return BotResult(
        bot_name="pagespeedbot",
        status=BotStatus.PARTIAL if errors else status,
        summary=summary,
        data=data,
        markdown_report=report_md,
        errors=errors,
        timestamp=_utc_now(),
    )
