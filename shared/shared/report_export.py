"""HTML/PDF report export helpers.

Markdown remains the canonical report format. This module renders branded HTML
from markdown plus metadata and optionally converts that HTML to PDF.
"""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from jinja2 import Template
from markdown import markdown

from shared.data_manager import get_workspace_root, save_report_artifact
from shared.models import ProjectScope

ASSET_DIR = Path(__file__).resolve().parent / "assets"
PROTONSYSTEMS_LOGO_PATH = ASSET_DIR / "protonsystems-logo-reverse.svg"
PROTONSYSTEMS_LOGO_LIGHT_PATH = ASSET_DIR / "protonsystems-logo.svg"

DEFAULT_LOGO_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" width="320" height="80" viewBox="0 0 320 80" role="img" aria-label="DevBots">
  <rect width="320" height="80" rx="16" fill="#0f172a"/>
  <circle cx="40" cy="40" r="18" fill="#14b8a6"/>
  <circle cx="34" cy="34" r="3.5" fill="#0f172a"/>
  <circle cx="46" cy="34" r="3.5" fill="#0f172a"/>
  <rect x="33" y="46" width="14" height="4" rx="2" fill="#0f172a"/>
  <text x="72" y="49" font-size="28" font-weight="700" font-family="Arial, Helvetica, sans-serif" fill="#f8fafc">DevBots</text>
</svg>
""".strip()

AUDIT_CSS = """
@page {
  size: A4;
  margin: 18mm 15mm 18mm;
  @bottom-left {
    content: "{{ branding.company_name }}";
    color: #8f9eb3;
    font-size: 9px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  @bottom-right {
    content: counter(page);
    color: #8f9eb3;
    font-size: 9px;
  }
}

:root {
  --brand-primary: {{ branding.primary_color }};
  --brand-secondary: {{ branding.secondary_color }};
  --brand-accent: {{ branding.accent_color }};
  --ink-950: #07111f;
  --ink-900: #0b1628;
  --ink-850: #102238;
  --ink-700: #203550;
  --slate-500: #72839c;
  --slate-300: #b7c4d5;
  --surface: #ffffff;
  --surface-alt: #f4f7fb;
  --surface-soft: #eef5fb;
  --line: #d5dfeb;
  --text: #101726;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  color: var(--text);
  background: var(--surface);
  font-family: "DejaVu Sans", "Segoe UI", Arial, sans-serif;
  font-size: 11.5px;
  line-height: 1.58;
}

.report-shell {
  display: block;
}

.report-cover {
  position: relative;
  overflow: hidden;
  padding: 26px 26px 24px;
  border-radius: 22px;
  background:
    radial-gradient(circle at top right, rgba(21, 133, 198, 0.34), transparent 32%),
    linear-gradient(148deg, var(--ink-950) 0%, var(--ink-900) 48%, #132843 100%);
  color: #f8fbff;
}

.report-cover::before,
.report-cover::after {
  content: "";
  position: absolute;
  background: linear-gradient(135deg, rgba(21, 133, 198, 0.3), rgba(21, 133, 198, 0.0));
  transform: skewX(-28deg);
}

.report-cover::before {
  top: -48px;
  right: 110px;
  width: 160px;
  height: 220px;
}

.report-cover::after {
  top: 80px;
  right: -26px;
  width: 120px;
  height: 180px;
}

.cover-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1.65fr) minmax(220px, 0.9fr);
  gap: 22px;
}

.brand-lockup {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
}

.cover-kicker {
  font-size: 10px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: rgba(248, 251, 255, 0.68);
}

.report-logo {
  width: 240px;
  max-width: 100%;
  height: auto;
}

.report-title {
  margin: 26px 0 10px;
  max-width: 10.5cm;
  font-size: 31px;
  line-height: 1.05;
  font-weight: 700;
}

.report-subtitle {
  margin: 0;
  max-width: 9.5cm;
  color: rgba(248, 251, 255, 0.75);
  font-size: 13px;
}

.cover-summary {
  margin-top: 22px;
  max-width: 11cm;
  padding-left: 16px;
  border-left: 3px solid rgba(21, 133, 198, 0.95);
  color: rgba(248, 251, 255, 0.86);
}

.cover-panel {
  align-self: end;
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03));
  backdrop-filter: blur(4px);
}

.panel-label,
.meta-label,
.highlight-label {
  display: block;
  font-size: 9px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--slate-500);
}

.panel-value {
  margin-top: 6px;
  font-size: 14px;
  font-weight: 700;
  color: #f8fbff;
}

.panel-divider {
  height: 1px;
  margin: 14px 0;
  background: rgba(255, 255, 255, 0.12);
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0 0;
}

.meta-card {
  padding: 14px 15px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: var(--surface);
}

.meta-value {
  margin-top: 4px;
  font-size: 13px;
  font-weight: 700;
  color: var(--ink-900);
}

.highlights {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0 0;
}

.highlight-card {
  padding: 16px;
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff, var(--surface-alt));
  border: 1px solid var(--line);
}

.highlight-card.is-accent {
  background: linear-gradient(160deg, #e7f6ff, #f8fbff);
  border-color: rgba(21, 133, 198, 0.32);
}

.highlight-value {
  margin-top: 7px;
  font-size: 18px;
  line-height: 1.1;
  font-weight: 700;
  color: var(--ink-900);
}

.report-body {
  margin-top: 18px;
}

.report-chapter {
  margin-top: 16px;
  padding: 18px 18px 16px;
  border: 1px solid var(--line);
  border-radius: 18px;
  background: #ffffff;
}

.report-chapter-summary {
  background: linear-gradient(180deg, #ffffff, #fbfdff);
}

.report-body h1,
.report-body h2,
.report-body h3,
.report-body h4 {
  color: var(--brand-secondary);
  page-break-after: avoid;
}

.report-body h1 {
  margin: 32px 0 10px;
  font-size: 23px;
}

.report-body h2 {
  margin: 0 0 10px;
  padding-bottom: 5px;
  border-bottom: 1px solid var(--line);
  font-size: 18px;
}

.report-body h3 {
  margin: 18px 0 8px;
  font-size: 14px;
}

.report-body h4 {
  margin: 16px 0 8px;
  font-size: 12px;
}

.report-body p,
.report-body ul,
.report-body ol,
.report-body table,
.report-body pre,
.report-body blockquote {
  margin: 0 0 14px;
}

.report-body ul,
.report-body ol {
  padding-left: 20px;
}

.report-body table {
  width: 100%;
  border-collapse: collapse;
  font-size: 10.5px;
  table-layout: fixed;
}

.report-body thead {
  display: table-header-group;
}

.report-body tr {
  page-break-inside: avoid;
}

.report-body th,
.report-body td {
  border: 1px solid var(--line);
  padding: 8px 9px;
  vertical-align: top;
  word-break: break-word;
  overflow-wrap: anywhere;
}

.report-body th {
  background: var(--surface-soft);
  color: var(--ink-900);
  text-align: left;
}

.report-body tbody tr:nth-child(even) td {
  background: #fbfdff;
}

.report-body code {
  padding: 1px 4px;
  border-radius: 4px;
  background: #e8eef6;
  font-size: 0.92em;
}

.report-body pre {
  padding: 12px 14px;
  overflow: hidden;
  border-radius: 10px;
  background: var(--ink-950);
  color: #e6eef8;
  white-space: pre-wrap;
}

.report-body pre code {
  padding: 0;
  background: transparent;
  color: inherit;
}

.report-body blockquote {
  margin-left: 0;
  padding: 12px 14px;
  border-left: 4px solid var(--brand-primary);
  background: var(--surface-alt);
}

.report-footer {
  margin-top: 22px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--slate-500);
  font-size: 10px;
}

.footer-logo {
  width: 132px;
  height: auto;
}

.audit-target {
  page-break-before: always;
  background: linear-gradient(180deg, #ffffff, #f9fbfe);
}

.audit-target-title {
  padding: 0 0 12px;
  border-bottom: 1px solid rgba(21, 133, 198, 0.18);
}

.audit-target-label {
  display: block;
  margin-bottom: 6px;
  color: var(--slate-500);
  font-size: 9px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}

.audit-target-url {
  display: block;
  color: var(--ink-900);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.25;
  word-break: break-word;
}

.audit-subsection {
  margin-top: 14px;
  padding: 14px 14px 12px;
  border: 1px solid var(--line);
  border-radius: 14px;
  background: #ffffff;
}

.audit-subsection-mobile {
  border-left: 4px solid #1585c6;
}

.audit-subsection-desktop {
  border-left: 4px solid #0a1028;
}

.audit-subsection-seo {
  border-left: 4px solid #76b9df;
  background: linear-gradient(180deg, #fbfdff, #f4f9fd);
}

.audit-mode-heading {
  display: inline-block;
  margin: 0 0 10px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(21, 133, 198, 0.18);
  background: #eef7fd;
  color: var(--ink-900);
  font-size: 12px;
  font-weight: 700;
}

.audit-subsection-desktop > .audit-mode-heading {
  border-color: rgba(10, 16, 40, 0.16);
  background: #f2f5fa;
}

.audit-subsection-seo > .audit-mode-heading {
  border-color: rgba(118, 185, 223, 0.3);
  background: #f5fbfe;
}

.audit-detail-heading {
  margin: 12px 0 8px;
  display: inline-block;
  color: var(--ink-700);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.report-chapter-summary > ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.report-chapter-summary > ul li {
  padding: 12px 12px 10px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface-alt);
  font-weight: 700;
}
""".strip()

DEFAULT_TEMPLATE = Template(
    """
<!DOCTYPE html>
<html lang="{{ metadata.lang }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ metadata.title }}</title>
  <style>{{ css }}</style>
</head>
<body>
  <main class="report-shell">
    <section class="report-cover">
      <div class="cover-grid">
        <div>
          <div class="brand-lockup">
            <div class="cover-kicker">{{ metadata.kicker }}</div>
            {% if branding.logo_data_uri %}
            <img class="report-logo" src="{{ branding.logo_data_uri }}" alt="{{ branding.company_name }} logo">
            {% endif %}
          </div>
          <h1 class="report-title">{{ metadata.title }}</h1>
          {% if metadata.subtitle %}<p class="report-subtitle">{{ metadata.subtitle }}</p>{% endif %}
          {% if metadata.summary %}<div class="cover-summary">{{ metadata.summary }}</div>{% endif %}
        </div>
        <aside class="cover-panel">
          <span class="panel-label">{{ metadata.labels.prepared_for }}</span>
          <div class="panel-value">{{ metadata.project_name }}</div>
          <div class="panel-divider"></div>
          <span class="panel-label">{{ metadata.labels.report_date }}</span>
          <div class="panel-value">{{ metadata.generated_at }}</div>
          <div class="panel-divider"></div>
          <span class="panel-label">{{ metadata.labels.prepared_by }}</span>
          <div class="panel-value">{{ metadata.author }}</div>
        </aside>
      </div>
    </section>

    <section class="meta-grid">
      <article class="meta-card">
        <span class="meta-label">{{ metadata.labels.document_type }}</span>
        <div class="meta-value">{{ metadata.document_type }}</div>
      </article>
      <article class="meta-card">
        <span class="meta-label">{{ metadata.labels.primary_scope }}</span>
        <div class="meta-value">{{ metadata.primary_scope }}</div>
      </article>
      <article class="meta-card">
        <span class="meta-label">{{ metadata.labels.confidentiality }}</span>
        <div class="meta-value">{{ metadata.confidentiality }}</div>
      </article>
    </section>

    {% if metadata.highlights %}
    <section class="highlights">
      {% for item in metadata.highlights %}
      <article class="highlight-card{% if item.accent %} is-accent{% endif %}">
        <span class="highlight-label">{{ item.label }}</span>
        <div class="highlight-value">{{ item.value }}</div>
      </article>
      {% endfor %}
    </section>
    {% endif %}

    <article class="report-body">
      {{ body_html | safe }}
    </article>

    <footer class="report-footer">
      <span>{{ metadata.footer_text }}</span>
      {% if branding.logo_light_data_uri %}
      <img class="footer-logo" src="{{ branding.logo_light_data_uri }}" alt="{{ branding.company_name }} logo">
      {% endif %}
    </footer>
  </main>
</body>
</html>
""".strip()
)

AUDIT_TEMPLATE = Template(
    """
<!DOCTYPE html>
<html lang="{{ metadata.lang }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ metadata.title }}</title>
  <style>{{ css }}</style>
</head>
<body>
  <main class="report-shell">
    <section class="report-cover">
      <div class="cover-grid">
        <div>
          <div class="brand-lockup">
            <div class="cover-kicker">{{ metadata.kicker }}</div>
            {% if branding.logo_data_uri %}
            <img class="report-logo" src="{{ branding.logo_data_uri }}" alt="{{ branding.company_name }} logo">
            {% endif %}
          </div>
          <h1 class="report-title">{{ metadata.title }}</h1>
          {% if metadata.subtitle %}<p class="report-subtitle">{{ metadata.subtitle }}</p>{% endif %}
          {% if metadata.summary %}<div class="cover-summary">{{ metadata.summary }}</div>{% endif %}
        </div>
        <aside class="cover-panel">
          <span class="panel-label">{{ metadata.labels.client_project }}</span>
          <div class="panel-value">{{ metadata.project_name }}</div>
          <div class="panel-divider"></div>
          <span class="panel-label">{{ metadata.labels.primary_url }}</span>
          <div class="panel-value">{{ metadata.primary_url }}</div>
          <div class="panel-divider"></div>
          <span class="panel-label">{{ metadata.labels.generated }}</span>
          <div class="panel-value">{{ metadata.generated_at }}</div>
          {% if metadata.author %}
          <div class="panel-divider"></div>
          <span class="panel-label">{{ metadata.labels.prepared_by }}</span>
          <div class="panel-value">{{ metadata.author }}</div>
          {% endif %}
        </aside>
      </div>
    </section>

    <section class="meta-grid">
      <article class="meta-card">
        <span class="meta-label">{{ metadata.labels.audit_type }}</span>
        <div class="meta-value">{{ metadata.document_type }}</div>
      </article>
      <article class="meta-card">
        <span class="meta-label">{{ metadata.labels.focus }}</span>
        <div class="meta-value">{{ metadata.primary_scope }}</div>
      </article>
      <article class="meta-card">
        <span class="meta-label">{{ metadata.labels.confidentiality }}</span>
        <div class="meta-value">{{ metadata.confidentiality }}</div>
      </article>
    </section>

    {% if metadata.highlights %}
    <section class="highlights">
      {% for item in metadata.highlights %}
      <article class="highlight-card{% if item.accent %} is-accent{% endif %}">
        <span class="highlight-label">{{ item.label }}</span>
        <div class="highlight-value">{{ item.value }}</div>
      </article>
      {% endfor %}
    </section>
    {% endif %}

    <article class="report-body">
      {{ body_html | safe }}
    </article>

    <footer class="report-footer">
      <span>{{ metadata.footer_text }}</span>
      {% if branding.logo_light_data_uri %}
      <img class="footer-logo" src="{{ branding.logo_light_data_uri }}" alt="{{ branding.company_name }} logo">
      {% endif %}
    </footer>
  </main>
</body>
</html>
""".strip()
)


@dataclass(frozen=True)
class ReportBranding:
    """Branding configuration applied to exported reports."""

    company_name: str = "DevBots"
    logo_path: str | None = None
    logo_path_light: str | None = None
    primary_color: str = "#0f766e"
    secondary_color: str = "#0f172a"
    accent_color: str = "#14b8a6"
    footer_text: str = "Generated by DevBots"


@dataclass(frozen=True)
class ReportSettings:
    """Project-level report delivery overrides."""

    branding_profile: str | None = None
    prepared_by: str | None = None
    client_name: str | None = None
    footer_text: str | None = None


REPORT_LANGUAGE_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "prepared_for": "Prepared For",
        "report_date": "Report Date",
        "prepared_by": "Prepared By",
        "document_type": "Document Type",
        "primary_scope": "Primary Scope",
        "confidentiality": "Confidentiality",
        "client_project": "Client / Project",
        "primary_url": "Primary URL",
        "generated": "Generated",
        "audit_type": "Audit Type",
        "focus": "Focus",
    },
    "de": {
        "prepared_for": "Erstellt Fuer",
        "report_date": "Berichtsdatum",
        "prepared_by": "Erstellt Von",
        "document_type": "Dokumenttyp",
        "primary_scope": "Primaerer Fokus",
        "confidentiality": "Vertraulichkeit",
        "client_project": "Kunde / Projekt",
        "primary_url": "Primaere URL",
        "generated": "Erstellt",
        "audit_type": "Audit-Typ",
        "focus": "Fokus",
    },
    "es": {
        "prepared_for": "Preparado Para",
        "report_date": "Fecha del Informe",
        "prepared_by": "Preparado Por",
        "document_type": "Tipo de Documento",
        "primary_scope": "Alcance Principal",
        "confidentiality": "Confidencialidad",
        "client_project": "Cliente / Proyecto",
        "primary_url": "URL Principal",
        "generated": "Generado",
        "audit_type": "Tipo de Auditoria",
        "focus": "Enfoque",
    },
}


@dataclass(frozen=True)
class ReportHighlight:
    """Small summary card rendered near the top of the HTML/PDF report."""

    label: str
    value: str
    accent: bool = False


@dataclass
class ReportExportResult:
    """Export result containing generated content, saved paths, and warnings."""

    html: str
    pdf_bytes: bytes | None = None
    html_paths: tuple[Path, Path | None] | None = None
    pdf_paths: tuple[Path, Path | None] | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "html": {
                "latest": str(self.html_paths[0]) if self.html_paths else None,
                "timestamped": str(self.html_paths[1]) if self.html_paths and self.html_paths[1] else None,
            },
            "pdf": {
                "latest": str(self.pdf_paths[0]) if self.pdf_paths else None,
                "timestamped": str(self.pdf_paths[1]) if self.pdf_paths and self.pdf_paths[1] else None,
            },
            "errors": self.errors,
        }


BRANDING_PROFILES: dict[str, ReportBranding] = {
    "default": ReportBranding(),
    "protonsystems": ReportBranding(
        company_name="ProtonSystems",
        logo_path=str(PROTONSYSTEMS_LOGO_PATH),
        logo_path_light=str(PROTONSYSTEMS_LOGO_LIGHT_PATH),
        primary_color="#1585C6",
        secondary_color="#0A1028",
        accent_color="#76B9DF",
        footer_text="Prepared by ProtonSystems",
    ),
}


def resolve_report_branding_name(bot: str, branding_profile: str | None = None) -> str:
    """Resolve the branding profile to use for a report export."""

    if branding_profile:
        return branding_profile
    if bot == "pagespeedbot":
        return "protonsystems"
    return "default"


def normalize_report_language(language: str | None = None) -> str:
    """Normalize a requested report language into a supported export locale."""

    if not language:
        return "en"
    normalized = language.strip().lower()
    if normalized.startswith("de"):
        return "de"
    if normalized.startswith("es"):
        return "es"
    return "en"


def resolve_report_template_name(bot: str, branding_profile: str | None = None) -> str:
    """Resolve the HTML template alias for a report export."""

    branding_name = resolve_report_branding_name(bot, branding_profile)
    if bot == "pagespeedbot":
        return "protonsystems_audit" if branding_name == "protonsystems" else "pagespeed"
    return "default"


def resolve_report_presenter(bot: str, settings: ReportSettings | None = None) -> str:
    """Resolve who is presented as the report author/delivery owner."""

    settings = settings or ReportSettings()
    if settings.prepared_by:
        return settings.prepared_by
    branding_name = resolve_report_branding_name(bot, settings.branding_profile)
    return default_branding(branding_name).company_name


def resolve_report_client_name(project_name: str, settings: ReportSettings | None = None) -> str:
    """Resolve the final client/project name shown on the report."""

    settings = settings or ReportSettings()
    return settings.client_name or project_name


def resolve_report_footer_text(
    bot: str,
    subject: str | None = None,
    settings: ReportSettings | None = None,
    language: str | None = None,
) -> str:
    """Resolve footer text using project overrides plus branding defaults."""

    settings = settings or ReportSettings()
    lang = normalize_report_language(language)
    if settings.footer_text and lang == "en":
        return settings.footer_text

    presenter = resolve_report_presenter(bot, settings)
    should_prepare = (
        bot == "pagespeedbot"
        or settings.prepared_by is not None
        or resolve_report_branding_name(bot, settings.branding_profile) == "protonsystems"
    )
    verbs = {
        "en": ("Prepared by", "Generated by"),
        "de": ("Erstellt von", "Generiert von"),
        "es": ("Preparado por", "Generado por"),
    }
    prepared_label, generated_label = verbs.get(lang, verbs["en"])
    prefix = f"{prepared_label if should_prepare else generated_label} {presenter}"
    subject_prefix = {
        "en": "for",
        "de": "fuer",
        "es": "para",
    }.get(lang, "for")
    if subject:
        return f"{prefix} {subject_prefix} {subject}"
    return prefix


def default_branding(branding_name: str = "default") -> ReportBranding:
    """Resolve report branding from a named profile plus optional env overrides."""

    base = BRANDING_PROFILES.get(branding_name, BRANDING_PROFILES["default"])
    env_name = os.environ.get("REPORT_COMPANY_NAME")
    env_logo = os.environ.get("REPORT_COMPANY_LOGO")
    env_primary = os.environ.get("REPORT_PRIMARY_COLOR")
    env_secondary = os.environ.get("REPORT_SECONDARY_COLOR")
    env_footer = os.environ.get("REPORT_FOOTER_TEXT")

    return ReportBranding(
        company_name=env_name or base.company_name,
        logo_path=env_logo or base.logo_path,
        logo_path_light=base.logo_path_light,
        primary_color=env_primary or base.primary_color,
        secondary_color=env_secondary or base.secondary_color,
        accent_color=base.accent_color,
        footer_text=env_footer or base.footer_text,
    )


def render_report_html(
    markdown_content: str,
    template_name: str = "default",
    metadata: dict[str, Any] | None = None,
    branding: ReportBranding | None = None,
    branding_name: str = "default",
) -> str:
    """Render markdown into branded HTML."""

    branding = branding or default_branding(branding_name)
    metadata = _normalize_metadata(metadata)
    metadata["footer_text"] = metadata.get("footer_text") or branding.footer_text
    branding_context = _branding_context(branding)
    template = _template_for(template_name)

    body_html = markdown(
        markdown_content,
        extensions=["extra", "sane_lists", "toc"],
        output_format="html5",
    )
    body_html = _enhance_body_html(body_html)

    css = Template(AUDIT_CSS).render(branding=branding_context)
    return template.render(
        metadata=metadata,
        branding=branding_context,
        body_html=body_html,
        css=css,
    )


def render_pdf(html_content: str, base_url: str | None = None) -> bytes:
    """Render HTML to a PDF payload."""

    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise RuntimeError("PDF export requires WeasyPrint to be installed.") from exc

    return HTML(string=html_content, base_url=base_url).write_pdf()


def export_report_files(
    markdown_content: str,
    *,
    project_name: str | None,
    bot: str,
    scope: ProjectScope = ProjectScope.TEAM,
    template_name: str = "default",
    metadata: dict[str, Any] | None = None,
    branding: ReportBranding | None = None,
    branding_name: str = "default",
) -> ReportExportResult:
    """
    Render branded HTML and, when possible, generate a sibling PDF artifact.

    The markdown report remains the source artifact and should already have been
    saved through ``save_report``. This helper only manages additional formats.
    """

    html = render_report_html(
        markdown_content,
        template_name=template_name,
        metadata=metadata,
        branding=branding,
        branding_name=branding_name,
    )
    result = ReportExportResult(html=html)

    if project_name:
        result.html_paths = save_report_artifact(
            project_name,
            bot,
            html,
            extension="html",
            scope=scope,
        )

    try:
        pdf_bytes = render_pdf(html, base_url=str(get_workspace_root()))
        result.pdf_bytes = pdf_bytes
        if project_name:
            result.pdf_paths = save_report_artifact(
                project_name,
                bot,
                pdf_bytes,
                extension="pdf",
                scope=scope,
            )
    except Exception as exc:
        result.errors.append(str(exc))

    return result


def export_report_file(
    report_path: Path,
    *,
    template_name: str = "default",
    metadata: dict[str, Any] | None = None,
    branding: ReportBranding | None = None,
    branding_name: str = "default",
) -> ReportExportResult:
    """Render HTML/PDF siblings for an existing markdown report file."""

    markdown_content = report_path.read_text(encoding="utf-8")
    html = render_report_html(
        markdown_content,
        template_name=template_name,
        metadata=metadata,
        branding=branding,
        branding_name=branding_name,
    )

    result = ReportExportResult(html=html)
    html_path = report_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    result.html_paths = (html_path, None)

    try:
        pdf_bytes = render_pdf(html, base_url=str(get_workspace_root()))
        pdf_path = report_path.with_suffix(".pdf")
        pdf_path.write_bytes(pdf_bytes)
        result.pdf_bytes = pdf_bytes
        result.pdf_paths = (pdf_path, None)
    except Exception as exc:
        result.errors.append(str(exc))

    return result


def _normalize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(metadata or {})
    lang = normalize_report_language(raw.get("lang"))
    generated_at = raw.get("generated_at") or datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    highlights_raw = raw.get("highlights") or []
    highlights = [
        item if isinstance(item, ReportHighlight) else ReportHighlight(**item)
        for item in highlights_raw
    ]

    raw["title"] = raw.get("title") or "Report"
    raw["subtitle"] = raw.get("subtitle") or ""
    raw["project_name"] = raw.get("project_name") or "Unspecified Project"
    raw["lang"] = lang
    raw["generated_at"] = generated_at
    raw["author"] = raw.get("author") or "DevBots"
    raw["summary"] = raw.get("summary") or ""
    raw["footer_text"] = raw.get("footer_text") or ""
    raw["highlights"] = highlights
    raw["primary_url"] = raw.get("primary_url") or raw["project_name"]
    raw["kicker"] = raw.get("kicker") or "Technical Audit Report"
    raw["document_type"] = raw.get("document_type") or "Technical Review"
    raw["primary_scope"] = raw.get("primary_scope") or "Web Experience"
    raw["confidentiality"] = raw.get("confidentiality") or "Internal Use"
    raw["labels"] = {
        **REPORT_LANGUAGE_LABELS["en"],
        **REPORT_LANGUAGE_LABELS.get(lang, REPORT_LANGUAGE_LABELS["en"]),
        **dict(raw.get("labels") or {}),
    }
    return raw


def _enhance_body_html(body_html: str) -> str:
    sections = _split_level_sections(body_html, "h2")
    if not sections:
        return body_html

    enhanced: list[str] = []
    for section in sections:
        if not section.startswith("<h2"):
            enhanced.append(section)
            continue

        heading_html, body = _extract_heading_and_body(section, "h2")
        heading_text = _strip_html(heading_html)
        if heading_text.startswith(("http://", "https://")):
            enhanced.append(_enhance_target_section(heading_html, heading_text, body))
        else:
            enhanced.append(
                f'<section class="report-chapter report-chapter-summary">{heading_html}{_enhance_minor_headings(body)}</section>'
            )

    return "".join(enhanced)


def _enhance_target_section(heading_html: str, heading_text: str, body: str) -> str:
    heading_html = _replace_heading_content(
        heading_html,
        "h2",
        '<span class="audit-target-label">Audited URL</span>'
        f'<span class="audit-target-url">{heading_text}</span>',
        "audit-target-title",
    )

    subsections = _split_level_sections(body, "h3")
    if not subsections:
        return f'<section class="report-chapter audit-target">{heading_html}{_enhance_minor_headings(body)}</section>'

    content: list[str] = []
    for subsection in subsections:
        if not subsection.startswith("<h3"):
            if subsection.strip():
                content.append(_enhance_minor_headings(subsection))
            continue

        sub_heading_html, sub_body = _extract_heading_and_body(subsection, "h3")
        sub_heading_text = _strip_html(sub_heading_html).lower()
        subsection_class = "audit-subsection"
        if "mobile" == sub_heading_text:
            subsection_class += " audit-subsection-mobile"
        elif "desktop" == sub_heading_text:
            subsection_class += " audit-subsection-desktop"
        elif "on-page seo" == sub_heading_text:
            subsection_class += " audit-subsection-seo"

        sub_heading_html = _append_class_to_heading(sub_heading_html, "h3", "audit-mode-heading")
        content.append(
            f'<section class="{subsection_class}">{sub_heading_html}{_enhance_minor_headings(sub_body)}</section>'
        )

    return f'<section class="report-chapter audit-target">{heading_html}{"".join(content)}</section>'


def _enhance_minor_headings(content: str) -> str:
    for label in ("SEO Issues", "Metrics", "Lighthouse Issues", "Opportunities", "Diagnostics", "Environment"):
        content = re.sub(
            rf"<h4([^>]*)>{re.escape(label)}</h4>",
            lambda match: f'<h4{_append_class_attr(match.group(1), "audit-detail-heading")}>{label}</h4>',
            content,
        )
    return content


def _split_level_sections(content: str, tag: str) -> list[str]:
    pattern = re.compile(rf"(?=<{tag}\b)", re.IGNORECASE)
    parts = pattern.split(content)
    return [part for part in parts if part]


def _extract_heading_and_body(section: str, tag: str) -> tuple[str, str]:
    match = re.match(rf"(?P<heading><{tag}\b[^>]*>.*?</{tag}>)(?P<body>.*)", section, re.DOTALL | re.IGNORECASE)
    if not match:
        return section, ""
    return match.group("heading"), match.group("body")


def _replace_heading_content(heading_html: str, tag: str, new_content: str, class_name: str) -> str:
    match = re.match(rf"<{tag}(?P<attrs>[^>]*)>.*?</{tag}>", heading_html, re.DOTALL | re.IGNORECASE)
    if not match:
        return heading_html
    attrs = _append_class_attr(match.group("attrs"), class_name)
    return f"<{tag}{attrs}>{new_content}</{tag}>"


def _append_class_to_heading(heading_html: str, tag: str, class_name: str) -> str:
    match = re.match(rf"<{tag}(?P<attrs>[^>]*)>(?P<content>.*)</{tag}>", heading_html, re.DOTALL | re.IGNORECASE)
    if not match:
        return heading_html
    attrs = _append_class_attr(match.group("attrs"), class_name)
    return f"<{tag}{attrs}>{match.group('content')}</{tag}>"


def _append_class_attr(attrs: str, class_name: str) -> str:
    if 'class="' in attrs:
        return re.sub(r'class="([^"]*)"', lambda match: f'class="{match.group(1)} {class_name}"', attrs, count=1)
    return f'{attrs} class="{class_name}"'


def _strip_html(value: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", value)).strip()


def _branding_context(branding: ReportBranding) -> dict[str, str]:
    return {
        "company_name": branding.company_name,
        "primary_color": branding.primary_color,
        "secondary_color": branding.secondary_color,
        "accent_color": branding.accent_color,
        "footer_text": branding.footer_text,
        "logo_data_uri": _logo_to_data_uri(branding.logo_path),
        "logo_light_data_uri": _logo_to_data_uri(branding.logo_path_light) if branding.logo_path_light else "",
    }


def _logo_to_data_uri(logo_path: str | None) -> str:
    if logo_path:
        path = Path(logo_path).expanduser()
        if path.exists():
            mime = "image/svg+xml" if path.suffix.lower() == ".svg" else "image/png"
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{data}"

    data = base64.b64encode(DEFAULT_LOGO_SVG.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{data}"


def _template_for(template_name: str) -> Template:
    templates = {
        "default": DEFAULT_TEMPLATE,
        "audit": AUDIT_TEMPLATE,
        "pagespeed": AUDIT_TEMPLATE,
        "seo": AUDIT_TEMPLATE,
        "protonsystems_audit": AUDIT_TEMPLATE,
    }
    return templates.get(template_name, DEFAULT_TEMPLATE)
