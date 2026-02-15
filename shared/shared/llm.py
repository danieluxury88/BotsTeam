"""Shared Claude/Anthropic client factory."""

import os

import anthropic

from shared.config import get_anthropic_api_key, get_default_model


def create_client() -> anthropic.Anthropic:
    """Create and return an Anthropic API client."""
    api_key = get_anthropic_api_key()
    return anthropic.Anthropic(api_key=api_key)


def chat(
    system: str,
    user: str,
    max_tokens: int = 1024,
    bot_env_key: str | None = None,
) -> str:
    """
    Convenience wrapper — send a single user message and return the text response.

    Args:
        system:      System prompt.
        user:        User message.
        max_tokens:  Max response tokens.
        bot_env_key: Env var name for per-bot model override (e.g. "ISSUEBOT_MODEL").
    """
    model = get_default_model()
    if bot_env_key:
        model = os.environ.get(bot_env_key, model)

    client = create_client()
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text
