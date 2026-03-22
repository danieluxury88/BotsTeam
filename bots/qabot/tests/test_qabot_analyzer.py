from __future__ import annotations

from pathlib import Path

from qabot import analyzer


class _FakeMessage:
    def __init__(self, text: str):
        self.content = [type("TextBlock", (), {"text": text})()]


class _FakeClient:
    def __init__(self, text: str):
        self._text = text
        self.messages = self

    def create(self, **kwargs):
        return _FakeMessage(self._text)


def test_analyze_changes_for_testing_uses_read_result_commits(monkeypatch, tmp_path: Path):
    fake_commit = type("Commit", (), {"files_changed": ["app/service.py"]})()
    fake_group = type("Group", (), {"all_files": ["app/service.py"]})()

    monkeypatch.setattr(
        analyzer,
        "read_commits",
        lambda repo_path, max_commits=100: type("ReadResult", (), {"commits": [fake_commit]})(),
    )
    monkeypatch.setattr(analyzer, "group_commits_auto", lambda commits: [fake_group])
    monkeypatch.setattr(analyzer, "format_groups_for_llm", lambda groups: "- app/service.py changed")
    monkeypatch.setattr(analyzer, "create_client", lambda: _FakeClient("## Testing Summary\n\nLooks good."))

    result = analyzer.analyze_changes_for_testing(tmp_path)

    assert result.summary == "Analysis complete - see full report"
    assert "Testing Summary" in result.markdown_report
