"""Slack event handlers: app_mention and message.im."""

from __future__ import annotations

import logging
import re
import subprocess

from slack_bolt import App

from orchestrator.bot_invoker import invoke_bot
from orchestrator.registry import ProjectRegistry
from slackbot.formatter import format_result
from slackbot.intent import parse_intent

logger = logging.getLogger(__name__)

ALLOWED_WSL_COMMANDS: dict[str, list[str]] = {
    "ls": ["ls", "-al"],
    "df": ["df", "-h"],
    "uptime": ["uptime"],
    "whoami": ["whoami"],
    "gitman list": ["gitman", "list"],
}

_WSL_TIMEOUT_SECONDS = 10
_WSL_OUTPUT_MAX_CHARS = 3500
_LOG_TEXT_MAX_CHARS = 200

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

*Slash command:*
• `/wsl gitman list` — run allowlisted local command
"""


def _preview_text(text: str | None) -> str:
    if not text:
        return ""
    collapsed = " ".join(text.split())
    if len(collapsed) <= _LOG_TEXT_MAX_CHARS:
        return collapsed
    return f"{collapsed[:_LOG_TEXT_MAX_CHARS]}..."


def _log_incoming_event(event_name: str, event: dict) -> None:
    logger.info(
        "Incoming Slack event=%s user=%s channel=%s channel_type=%s subtype=%s ts=%s text=%r",
        event_name,
        event.get("user"),
        event.get("channel"),
        event.get("channel_type"),
        event.get("subtype"),
        event.get("ts"),
        _preview_text(event.get("text")),
    )


def register_handlers(app: App, registry: ProjectRegistry) -> None:
    """Register all Slack event handlers on the Bolt app."""

    @app.middleware
    def log_raw_slack_request(body, next):
        event = body.get("event", {})
        logger.debug(
            (
                "Incoming Slack raw request type=%s event_type=%s subtype=%s "
                "command=%s user=%s channel=%s text=%r"
            ),
            body.get("type"),
            event.get("type"),
            event.get("subtype"),
            body.get("command"),
            body.get("user_id") or event.get("user"),
            body.get("channel_id") or event.get("channel"),
            _preview_text(body.get("text") or event.get("text")),
        )
        next()

    @app.event("app_mention")
    def handle_mention(event, say, client):
        _log_incoming_event("app_mention", event)
        # Strip the @mention prefix before parsing.
        text = re.sub(r"<@[A-Z0-9]+>", "", event.get("text", "")).strip()
        _dispatch(text, event, say, client, registry)

    @app.event("message")
    def handle_dm(event, say, client):
        _log_incoming_event("message", event)
        # Only handle direct messages; skip bot messages and subtypes.
        if event.get("channel_type") != "im":
            logger.debug("Skipping message event outside DM channel: %s", event.get("channel"))
            return
        if event.get("subtype") or event.get("bot_id"):
            logger.debug(
                "Skipping message subtype/bot event: subtype=%s bot_id=%s",
                event.get("subtype"),
                event.get("bot_id"),
            )
            return
        text = event.get("text", "").strip()
        _dispatch(text, event, say, client, registry)

    @app.command("/wsl")
    def handle_wsl_command(ack, respond, command):
        """Handle /wsl slash command with a strict allowlist."""
        ack()

        text = (command.get("text") or "").strip()
        logger.info(
            "Incoming Slack command=/wsl user=%s channel=%s text=%r",
            command.get("user_id"),
            command.get("channel_id"),
            _preview_text(text),
        )
        key = " ".join(text.split())

        if key not in ALLOWED_WSL_COMMANDS:
            respond(
                text=(
                    "Allowed commands: "
                    + ", ".join(sorted(ALLOWED_WSL_COMMANDS.keys()))
                    + "\nExamples: `/wsl ls`, `/wsl gitman list`"
                )
            )
            return

        try:
            output = _run_command(ALLOWED_WSL_COMMANDS[key])
        except subprocess.TimeoutExpired:
            respond(text=f"❌ Command timed out after {_WSL_TIMEOUT_SECONDS}s")
            return
        except Exception as e:
            respond(text=f"❌ Command failed: {e}")
            return

        respond(text=f"```{output}```")


def _run_command(argv: list[str]) -> str:
    """Run an allowlisted command and return trimmed output."""
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        timeout=_WSL_TIMEOUT_SECONDS,
        check=False,
    )
    output = (proc.stdout + proc.stderr).strip()
    if not output:
        output = "(no output)"
    return output[:_WSL_OUTPUT_MAX_CHARS]


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
