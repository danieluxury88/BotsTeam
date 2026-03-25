"""LLM provider dispatch — provider-agnostic entry point for all bots."""

from __future__ import annotations

import os

from shared.config import get_default_model
from shared.providers.base import LLMProvider


def _get_provider() -> LLMProvider:
    """Instantiate the configured LLM provider."""
    name = os.environ.get("DEVBOTS_PROVIDER", "anthropic").lower()
    if name == "anthropic":
        from shared.providers.anthropic import AnthropicProvider
        return AnthropicProvider()
    if name == "openai":
        from shared.providers.openai import OpenAIProvider
        return OpenAIProvider()
    if name == "gemini":
        from shared.providers.gemini import GeminiProvider
        return GeminiProvider()
    raise ValueError(
        f"Unknown LLM provider '{name}'. "
        "Set DEVBOTS_PROVIDER to 'anthropic', 'openai', or 'gemini'."
    )


def chat(
    system: str,
    user: str,
    max_tokens: int = 1024,
    bot_env_key: str | None = None,
    model: str | None = None,
) -> str:
    """
    Send a single-turn message and return the text response.

    Model resolution order (first match wins):
      1. ``model`` argument
      2. env var named by ``bot_env_key`` (e.g. ``GITBOT_MODEL``)
      3. ``DEVBOTS_MODEL`` env var
      4. Hard-coded default (claude-haiku-4-5-20251001)

    Args:
        system:      System prompt.
        user:        User message.
        max_tokens:  Maximum response tokens.
        bot_env_key: Env var name for per-bot model override (e.g. ``"GITBOT_MODEL"``).
        model:       Explicit model override — takes precedence over everything else.
    """
    resolved_model = (
        model
        or (os.environ.get(bot_env_key) if bot_env_key else None)
        or get_default_model()
    )
    provider = _get_provider()
    return provider.chat(system, user, max_tokens, resolved_model)
