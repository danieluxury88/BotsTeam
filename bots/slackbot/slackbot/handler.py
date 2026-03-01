"""Slack event handlers: app_mention and message.im."""

from __future__ import annotations

import re

from slack_bolt import App

from orchestrator.bot_invoker import invoke_bot
from orchestrator.registry import ProjectRegistry
from slackbot.formatter import format_result
from slackbot.intent import parse_intent

HELP_TEXT = """\
*DevBots — Available Commands*

*Run a bot:*
• `analyze <project>` — Git history analysis (gitbot)
• `qa <project>` — Test suggestions (qabot)
• `issues <project>` — Issue analysis (pmbot)
• `journal <project>` — Journal analysis (journalbot)
• `tasks <project>` — Task analysis (taskbot)
• `habits <project>` — Habit tracking (habitbot)
• `notes <project>` — Note analysis (notebot)

*Shortcuts:* `git`, `tests`, `pm`, `sprint`, `task`, `habit`, `note`

*Other commands:*
• `list` / `projects` — List registered projects
• `help` — Show this message

*Examples:*
• `analyze myproject`
• `issues myproject`
• `list projects`
"""


def register_handlers(app: App, registry: ProjectRegistry) -> None:
    """Register all Slack event handlers on the Bolt app."""

    @app.event("app_mention")
    def handle_mention(event, say, client):
        # Strip the @mention prefix before parsing.
        text = re.sub(r"<@[A-Z0-9]+>", "", event.get("text", "")).strip()
        _dispatch(text, event, say, client, registry)

    @app.event("message")
    def handle_dm(event, say, client):
        # Only handle direct messages; skip bot messages and subtypes.
        if event.get("channel_type") != "im":
            return
        if event.get("subtype") or event.get("bot_id"):
            return
        text = event.get("text", "").strip()
        _dispatch(text, event, say, client, registry)


def _dispatch(
    text: str,
    event: dict,
    say,
    client,
    registry: ProjectRegistry,
) -> None:
    channel = event["channel"]
    ts = event["ts"]
    thread_ts = event.get("thread_ts", ts)

    intent = parse_intent(text)

    if intent is None or intent.action == "help":
        say(text=HELP_TEXT, thread_ts=thread_ts)
        return

    if intent.action == "list":
        projects = registry.list_projects()
        if not projects:
            say(
                text="No projects registered yet. Use the dashboard to add projects.",
                thread_ts=thread_ts,
            )
            return
        lines = ["*Registered projects:*"]
        for p in projects:
            scope_icon = "👤" if p.is_personal else "👥"
            desc = f" — {p.description}" if p.description else ""
            lines.append(f"• `{p.name}` ({scope_icon} {p.scope.value}){desc}")
        say(text="\n".join(lines), thread_ts=thread_ts)
        return

    if intent.action == "run_bot":
        if not intent.project_name:
            say(
                text=f"Please specify a project name. Example: `{intent.bot} myproject`",
                thread_ts=thread_ts,
            )
            return

        project = registry.get_project(intent.project_name)
        if not project:
            say(
                text=(
                    f"Project `{intent.project_name}` not found. "
                    "Use `list` to see registered projects."
                ),
                thread_ts=thread_ts,
            )
            return

        # Add hourglass reaction as immediate visual feedback.
        try:
            client.reactions_add(channel=channel, timestamp=ts, name="hourglass_flowing_sand")
        except Exception:
            pass  # reactions:write scope may not be configured

        try:
            result = invoke_bot(intent.bot, project=project)
        except Exception as e:
            say(text=f"❌ Error running {intent.bot}: {e}", thread_ts=thread_ts)
            return
        finally:
            try:
                client.reactions_remove(
                    channel=channel, timestamp=ts, name="hourglass_flowing_sand"
                )
            except Exception:
                pass

        blocks = format_result(result)
        say(blocks=blocks, text=result.summary, thread_ts=thread_ts)
