"""Bot registry — single source of truth for all DevBots bot metadata.

When adding a new bot:
  1. Write the bot package under bots/<newbot>/
  2. Add ONE entry to the BOTS dict below
  3. Add routing logic to bots/orchestrator/orchestrator/bot_invoker.py

Everything else (dashboard, API, data generator) picks the new bot up
automatically via imports from this module.
"""

from dataclasses import dataclass
from typing import Literal

BotScope = Literal["team", "personal", "both"]


@dataclass(frozen=True)
class BotMeta:
    id: str
    name: str
    icon: str
    description: str
    scope: BotScope
    requires_field: str | None = None
    """For personal bots: the Project field that must be set to enable this bot.
    e.g. "notes_dir", "task_file", "habit_file"."""


# ── Registry ──────────────────────────────────────────────────────────────────
# Add new bots here. Order determines display order on the dashboard.

BOTS: dict[str, BotMeta] = {
    "gitbot":       BotMeta("gitbot",       "GitBot",       "🔍", "Git history analyzer",                  "team"),
    "qabot":        BotMeta("qabot",        "QABot",        "🧪", "Test suggestion and execution",          "team"),
    "pmbot":        BotMeta("pmbot",        "PMBot",        "📊", "Issue analyzer and sprint planner",      "team"),
    "orchestrator": BotMeta("orchestrator", "Orchestrator", "🎭", "Conversational bot interface",           "team"),
    "journalbot":   BotMeta("journalbot",   "JournalBot",   "📓", "Personal journal and notes analyzer",   "personal", requires_field="notes_dir"),
    "taskbot":      BotMeta("taskbot",      "TaskBot",      "✅", "Personal task list analyzer",            "personal", requires_field="task_file"),
    "habitbot":     BotMeta("habitbot",     "HabitBot",     "🔄", "Habit and goal tracking analyzer",       "personal", requires_field="habit_file"),
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def team_bots() -> list[str]:
    """IDs of all bots scoped to team projects."""
    return [m.id for m in BOTS.values() if m.scope in ("team", "both")]


def personal_bots() -> list[str]:
    """IDs of all bots scoped to personal projects."""
    return [m.id for m in BOTS.values() if m.scope in ("personal", "both")]


def all_bots() -> list[str]:
    """IDs of every registered bot."""
    return list(BOTS.keys())


def to_json() -> list[dict]:
    """Serialize the registry for dashboard/data/bots.json."""
    return [
        {
            "id": m.id,
            "name": m.name,
            "icon": m.icon,
            "description": m.description,
            "scope": m.scope,
            "requires_field": m.requires_field,
        }
        for m in BOTS.values()
    ]
