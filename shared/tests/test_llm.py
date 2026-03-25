from __future__ import annotations

from types import SimpleNamespace

import anthropic
import httpx
import pytest

from shared import llm
from shared.providers import anthropic as anthropic_mod


class _FakeMessages:
    def __init__(self, outcomes: list[object]):
        self._outcomes = outcomes
        self.calls = 0

    def create(self, **_kwargs):
        self.calls += 1
        if not self._outcomes:
            raise AssertionError("No fake outcomes left.")
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _FakeClient:
    def __init__(self, outcomes: list[object]):
        self.messages = _FakeMessages(outcomes)


def _status_error(status_code: int, body: dict | None = None) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code=status_code, request=request, headers={"request-id": "req_test"})
    payload = body or {"type": "error", "error": {"type": "api_error", "message": "boom"}}
    return anthropic.APIStatusError(
        f"Error code: {status_code}",
        response=response,
        body=payload,
    )


def _connection_error() -> anthropic.APIConnectionError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(request=request)


def _message(text: str):
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


def _make_provider(client: _FakeClient) -> anthropic_mod.AnthropicProvider:
    """Build an AnthropicProvider with an injected fake client (bypasses API key check)."""
    provider = anthropic_mod.AnthropicProvider.__new__(anthropic_mod.AnthropicProvider)
    provider._client = client
    return provider


def test_chat_retries_on_529_overloaded_and_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    overloaded_body = {"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}}
    client = _FakeClient([_status_error(529, overloaded_body), _message("ok")])
    sleep_calls: list[float] = []

    monkeypatch.setattr(anthropic_mod, "_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(anthropic_mod.random, "uniform", lambda _a, _b: 0.0)
    monkeypatch.setattr(anthropic_mod.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(llm, "_get_provider", lambda: _make_provider(client))
    monkeypatch.setattr(llm, "get_default_model", lambda: "claude-test")

    output = llm.chat(system="sys", user="msg")

    assert output == "ok"
    assert client.messages.calls == 2
    assert sleep_calls == [1.0]


def test_chat_does_not_retry_non_retryable_status(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient([_status_error(400)])
    sleep_calls: list[float] = []

    monkeypatch.setattr(anthropic_mod, "_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(anthropic_mod.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(llm, "_get_provider", lambda: _make_provider(client))
    monkeypatch.setattr(llm, "get_default_model", lambda: "claude-test")

    with pytest.raises(anthropic.APIStatusError):
        llm.chat(system="sys", user="msg")

    assert client.messages.calls == 1
    assert sleep_calls == []


def test_chat_retries_connection_errors_until_exhausted(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient([_connection_error(), _connection_error(), _connection_error()])
    sleep_calls: list[float] = []

    monkeypatch.setattr(anthropic_mod, "_MAX_ATTEMPTS", 3)
    monkeypatch.setattr(anthropic_mod.random, "uniform", lambda _a, _b: 0.0)
    monkeypatch.setattr(anthropic_mod.time, "sleep", lambda seconds: sleep_calls.append(seconds))
    monkeypatch.setattr(llm, "_get_provider", lambda: _make_provider(client))
    monkeypatch.setattr(llm, "get_default_model", lambda: "claude-test")

    with pytest.raises(anthropic.APIConnectionError):
        llm.chat(system="sys", user="msg")

    assert client.messages.calls == 3
    assert sleep_calls == [1.0, 2.0]
