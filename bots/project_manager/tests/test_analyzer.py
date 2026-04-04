from __future__ import annotations

from datetime import datetime, timezone

from project_manager import analyzer
from shared.models import Issue, IssueSet, IssueState


def _issue(
    iid: int,
    title: str,
    *,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
) -> Issue:
    now = datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc)
    return Issue(
        iid=iid,
        title=title,
        state=IssueState.OPEN,
        author="alice",
        created_at=now,
        updated_at=now,
        labels=labels or [],
        assignees=assignees or [],
        description="Detailed tracker description",
        web_url=f"https://tracker.example/issues/{iid}",
    )


def test_plan_prompt_includes_label_context(monkeypatch):
    issue_set = IssueSet(
        project_id="acme/repo",
        project_name="Acme",
        fetched_at=datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc),
        issues=[
            _issue(12, "Fix import timeout", labels=["bug", "feeds", "urgent"], assignees=["alice"]),
            _issue(13, "Clean up translated content", labels=["content", "translations"]),
        ],
    )

    captured: dict[str, str] = {}

    def fake_chat(*, system: str, user: str, max_tokens: int, bot_env_key: str | None = None, model: str | None = None) -> str:
        captured["system"] = system
        captured["user"] = user
        return """
        {
          "summary": "Plan uses tracker labels.",
          "warnings": [],
          "issues": [
            {"iid": 12, "priority": "critical", "effort": "M", "rationale": "Urgent feeds bug.", "week": 1},
            {"iid": 13, "priority": "normal", "effort": "S", "rationale": "Content cleanup.", "week": 2}
          ]
        }
        """

    monkeypatch.setattr(analyzer.llm, "chat", fake_chat)

    plan_obj, result = analyzer.plan(issue_set)

    assert result.status == "success"
    assert plan_obj.total_open == 2
    assert "Label usage rules" in captured["system"]
    assert "Open issue label coverage: 2/2 issues have labels" in captured["user"]
    assert "Open issue labels by frequency: bug (1), content (1), feeds (1), translations (1), urgent (1)" in captured["user"]
    assert "#12 Fix import timeout | labels: bug, feeds, urgent" in captured["user"]


def test_analyze_report_appends_open_tasks_by_assignee(monkeypatch):
    issue_set = IssueSet(
        project_id="Proton.Systems/uni.li",
        project_name="UniLi",
        fetched_at=datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc),
        issues=[
            _issue(49, "Investigate feed import failure", labels=["bug", "feeds"], assignees=["danieluxury"]),
            _issue(20, "Header storer decision", labels=["design"], assignees=["grattazzi"]),
            _issue(44, "GDPR deletion flow", labels=["users"]),
        ],
    )

    monkeypatch.setattr(
        analyzer.llm,
        "chat",
        lambda **kwargs: "# UniLi Analysis\n\nSummary from the model.",
    )

    result = analyzer.analyze(issue_set)

    assert result.status == "success"
    assert "## Open Tasks By Assignee" in result.report_md
    assert "### @danieluxury (1)" in result.report_md
    assert "- [#49](https://tracker.example/issues/49) **Investigate feed import failure** — labels: bug, feeds — 0d old" in result.report_md
    assert "### @grattazzi (1)" in result.report_md
    assert "### Unassigned (1)" in result.report_md


def test_render_plan_markdown_shows_labels():
    issue_set = IssueSet(
        project_id="Proton.Systems/uni.li",
        project_name="UniLi",
        fetched_at=datetime(2026, 4, 2, 12, 0, 0, tzinfo=timezone.utc),
        issues=[
            _issue(49, "Investigate feed import failure", labels=["bug", "feeds", "urgent"], assignees=["danieluxury"]),
        ],
    )

    def fake_chat(*, system: str, user: str, max_tokens: int, bot_env_key: str | None = None, model: str | None = None) -> str:
        return """
        {
          "summary": "Feed labels push this to the front.",
          "warnings": ["High-risk subsystem cluster."],
          "issues": [
            {"iid": 49, "priority": "critical", "effort": "L", "rationale": "Feeds and urgent labels indicate production risk.", "week": 1}
          ]
        }
        """

    from project_manager import analyzer as analyzer_module

    original_chat = analyzer_module.llm.chat
    analyzer_module.llm.chat = fake_chat
    try:
        _plan_obj, result = analyzer_module.plan(issue_set)
    finally:
        analyzer_module.llm.chat = original_chat

    assert "| # | Issue | Labels | Priority | Effort | Rationale |" in result.report_md
    assert "| [#49](https://tracker.example/issues/49) | Investigate feed import failure | bug, feeds, urgent | 🔴 critical | `L` |" in result.report_md
    assert "- 🔴 [#49](https://tracker.example/issues/49) **Investigate feed import failure** `L` — @danieluxury — labels: bug, feeds, urgent" in result.report_md
    assert "## Open Tasks By Assignee" in result.report_md
    assert "### @danieluxury (1)" in result.report_md
