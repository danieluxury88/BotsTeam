"""Anthropic provider — wraps the Anthropic SDK with retry logic."""

from __future__ import annotations

import logging
import random
import time

import anthropic

from shared.config import get_anthropic_api_key
from shared.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504, 529}
_MAX_ATTEMPTS = 4
_BASE_BACKOFF_SECONDS = 1.0
_MAX_BACKOFF_SECONDS = 8.0


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


class AnthropicProvider(LLMProvider):
    """LLM provider backed by the Anthropic API."""

    def __init__(self) -> None:
        api_key = get_anthropic_api_key()
        self._client = anthropic.Anthropic(api_key=api_key)

    def chat(self, system: str, user: str, max_tokens: int, model: str) -> str:
        for attempt in range(_MAX_ATTEMPTS):
            try:
                message = self._client.messages.create(
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
