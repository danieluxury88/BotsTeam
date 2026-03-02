"""SlackBot entry point — Bolt app setup and Socket Mode listener."""

from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from orchestrator.registry import ProjectRegistry
from slackbot.handler import register_handlers

logger = logging.getLogger(__name__)


def require_env(name: str) -> str:
    """Return the value of an environment variable or raise RuntimeError."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "Set it in your shell or .env file."
        )
    return value


def create_app() -> tuple[App, str]:
    """Create and configure the Bolt app with all handlers registered."""
    load_dotenv()
    bot_token = require_env("SLACK_BOT_TOKEN")
    app_token = require_env("SLACK_APP_TOKEN")

    app = App(token=bot_token)
    registry = ProjectRegistry()
    register_handlers(app, registry)

    return app, app_token


def configure_logging() -> None:
    """Configure standard logging for the Slack bot process."""
    level_name = os.getenv("SLACKBOT_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )
    logging.getLogger("slack_bolt").setLevel(logging.WARNING)
    logging.getLogger("slack_sdk").setLevel(logging.WARNING)


def main() -> None:
    """Start the SlackBot using Socket Mode."""
    configure_logging()
    app, app_token = create_app()
    logger.info("Starting DevBots Slack bot (Socket Mode)")
    handler = SocketModeHandler(app, app_token)
    handler.start()
