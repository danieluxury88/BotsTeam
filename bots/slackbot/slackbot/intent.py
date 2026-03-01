"""Rule-based intent parser: Slack message → (action, bot, project)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Intent:
    action: str           # "run_bot" | "list" | "help"
    bot: str | None = None
    project_name: str | None = None


# Aliases mapped to canonical bot names — longest-match wins.
BOT_ALIASES: dict[str, str] = {
    "gitbot": "gitbot",
    "git": "gitbot",
    "analyze": "gitbot",
    "history": "gitbot",
    "qabot": "qabot",
    "qa": "qabot",
    "tests": "qabot",
    "test": "qabot",
    "pmbot": "pmbot",
    "pm": "pmbot",
    "issues": "pmbot",
    "sprint": "pmbot",
    "journalbot": "journalbot",
    "journal": "journalbot",
    "taskbot": "taskbot",
    "tasks": "taskbot",
    "task": "taskbot",
    "habitbot": "habitbot",
    "habits": "habitbot",
    "habit": "habitbot",
    "notebot": "notebot",
    "notes": "notebot",
    "note": "notebot",
}

_LIST_PHRASES = {"list", "projects", "list projects", "show projects", "list all projects"}
_HELP_PHRASES = {"help", "?", "h", "commands", "usage"}


def parse_intent(text: str) -> Intent | None:
    """
    Parse a Slack message into an Intent.

    Returns:
        Intent with action "help", "list", or "run_bot".
        None if the message doesn't match any known pattern.
    """
    normalized = text.strip().lower()

    if not normalized or normalized in _HELP_PHRASES:
        return Intent(action="help")

    if normalized in _LIST_PHRASES:
        return Intent(action="list")

    words = normalized.split()

    # Try longest alias match first (2-word then 1-word) to avoid "test" beating "tests".
    for length in (2, 1):
        if len(words) >= length:
            candidate = " ".join(words[:length])
            if candidate in BOT_ALIASES:
                bot = BOT_ALIASES[candidate]
                remaining = words[length:]
                project = " ".join(remaining) if remaining else None
                return Intent(action="run_bot", bot=bot, project_name=project)

    return None
