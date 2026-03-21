"""Language helpers for spoken command recognition."""

from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_SPANISH_LOCALE = "es-CO"
DEFAULT_ENGLISH_LOCALE = "en-US"
AUTO_LANGUAGE_ORDER = (DEFAULT_SPANISH_LOCALE, "es-ES", DEFAULT_ENGLISH_LOCALE)

_LANGUAGE_ALIASES = {
    "auto": "auto",
    "es": DEFAULT_SPANISH_LOCALE,
    "es-co": DEFAULT_SPANISH_LOCALE,
    "es-es": "es-ES",
    "spanish": DEFAULT_SPANISH_LOCALE,
    "en": DEFAULT_ENGLISH_LOCALE,
    "en-us": DEFAULT_ENGLISH_LOCALE,
    "en-gb": "en-GB",
    "english": DEFAULT_ENGLISH_LOCALE,
}

_SPANISH_HINTS = {
    "analiza",
    "ayuda",
    "bot",
    "comandos",
    "commits",
    "el",
    "esta",
    "mi",
    "mis",
    "notas",
    "para",
    "por",
    "proyecto",
    "quiero",
    "reporte",
    "revisa",
    "tareas",
    "habitos",
}
_ENGLISH_HINTS = {
    "analyze",
    "bot",
    "check",
    "commits",
    "for",
    "my",
    "notes",
    "please",
    "project",
    "report",
    "review",
    "tasks",
    "the",
}


@dataclass(frozen=True)
class LanguageDetection:
    """Heuristic language detection for recognized text."""

    language: str
    confidence: float


def normalize_requested_language(language: str | None) -> str:
    """Normalize a CLI language option into a speech locale or `auto`."""
    if not language:
        return "auto"

    normalized = language.strip().lower()
    if normalized in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[normalized]
    if re.fullmatch(r"[a-z]{2}-[A-Z]{2}", language.strip()):
        return language.strip()
    return _LANGUAGE_ALIASES.get(normalized, "auto")


def build_language_candidates(language: str | None) -> tuple[str, ...]:
    """Return the ordered speech locales to try for a request."""
    normalized = normalize_requested_language(language)
    if normalized == "auto":
        return AUTO_LANGUAGE_ORDER
    return (normalized,)


def detect_language(text: str) -> LanguageDetection:
    """Estimate whether a transcript is Spanish or English."""
    words = re.findall(r"[a-záéíóúñ]+", text.lower())
    if not words:
        return LanguageDetection(language="unknown", confidence=0.0)

    spanish_score = sum(1 for word in words if word in _SPANISH_HINTS)
    english_score = sum(1 for word in words if word in _ENGLISH_HINTS)

    if any(char in text for char in "áéíóúñ¿¡"):
        spanish_score += 2

    if spanish_score == 0 and english_score == 0:
        return LanguageDetection(language="unknown", confidence=0.0)

    total = spanish_score + english_score
    if spanish_score >= english_score:
        return LanguageDetection(language="es", confidence=spanish_score / total)
    return LanguageDetection(language="en", confidence=english_score / total)
