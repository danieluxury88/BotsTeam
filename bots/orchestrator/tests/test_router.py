from __future__ import annotations

from types import SimpleNamespace

from orchestrator.router import process_user_request
from shared.models import BotResult, ProjectScope


def test_process_user_request_passes_params_through_to_invoke_bot(monkeypatch):
    project = SimpleNamespace(
        name="BotsTeam",
        scope=ProjectScope.TEAM,
        has_gitlab=lambda: False,
        has_github=lambda: True,
    )

    class FakeRegistry:
        def list_projects(self):
            return [project]

        def get_project(self, name):
            return project if name == "BotsTeam" else None

    monkeypatch.setattr(
        "orchestrator.router.parse_user_request",
        lambda user_message, available_projects: {
            "action": "invoke_bot",
            "bot": "pmbot",
            "project": "BotsTeam",
            "scope": "team",
            "params": {
                "mode": "create",
                "title": "Dashboard header navigation problem",
                "description": "Investigate and fix the broken navigation state.",
            },
            "explanation": "Creating an issue via PMBot.",
        },
    )

    captured = {}

    def fake_invoke_bot(bot_name, project=None, bot_params=None, **kwargs):
        captured["bot_name"] = bot_name
        captured["project"] = project
        captured["bot_params"] = bot_params
        return BotResult(
            bot_name="issuebot",
            status="success",
            summary="ok",
            markdown_report="ok",
        )

    monkeypatch.setattr("orchestrator.router.invoke_bot", fake_invoke_bot)

    outcome = process_user_request("create issue", FakeRegistry())

    assert outcome.error is None
    assert outcome.bot_result is not None
    assert captured["bot_name"] == "pmbot"
    assert captured["project"] is project
    assert captured["bot_params"]["mode"] == "create"
    assert captured["bot_params"]["title"] == "Dashboard header navigation problem"
