"""Shared Claude/Anthropic client factory."""

from __future__ import annotations

import logging
import os
import random
import time

import anthropic

from shared.config import get_anthropic_api_key, get_default_model

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504, 529}
_MAX_ATTEMPTS = 4
_BASE_BACKOFF_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 8.0


def create_client() -> anthropic.Anthropic:
    """Create and return an Anthropic API client."""
    api_key = get_anthropic_api_key()
    return anthropic.Anthropic(api_key=api_key)


def _is_overloaded_error_body(body: object | None) -> bool:
    if not isinstance(body, dict):
        return False
    error = body.get("error")
    return isinstance(error, dict) and error.get("type") == "overloaded_error"


def _is_retryable_error(err: Exception) -> bool:
    if isinstance(err, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(err, anthropic.APIStatusError):
        return err.status_code in _RETRYABLE_STATUS_CODES or _is_overloaded_error_body(err.body)
    return False


def _retry_delay_seconds(attempt: int) -> float:
    backoff = min(_MAX_BACKOFF_SECONDS, _BASE_BACKOFF_SECONDS * (2**attempt))
    return backoff + random.uniform(0.0, 0.25)


def _error_label(err: Exception) -> str:
    if isinstance(err, anthropic.APIStatusError):
        request_id = f", request_id={err.request_id}" if err.request_id else ""
        return f"status={err.status_code}{request_id}"
    return err.__class__.__name__


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
    for attempt in range(_MAX_ATTEMPTS):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return message.content[0].text
        except (
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.APIStatusError,
        ) as exc:
            is_last_attempt = attempt >= _MAX_ATTEMPTS - 1
            if is_last_attempt or not _is_retryable_error(exc):
                raise

            delay = _retry_delay_seconds(attempt)
            logger.warning(
                "Anthropic request failed (%s), retrying in %.2fs (%d/%d)",
                _error_label(exc),
                delay,
                attempt + 1,
                _MAX_ATTEMPTS - 1,
            )
            time.sleep(delay)

    raise RuntimeError("Unreachable: chat retry loop exited without returning or raising.")
