from __future__ import annotations

from pathlib import Path

from qabot import generator


class _FakeMessage:
    def __init__(self, text: str):
        self.content = [type("TextBlock", (), {"text": text})()]


class _FakeClient:
    def __init__(self, text: str):
        self._text = text
        self.messages = self

    def create(self, **kwargs):
        return _FakeMessage(self._text)


def test_extract_json_block_accepts_fenced_json():
    payload = generator._extract_json_block(
        '```json\n{"summary": "ok", "stubs": []}\n```'
    )

    assert payload["summary"] == "ok"


def test_write_test_stubs_skips_existing_and_unsafe_paths(tmp_path: Path):
    existing = tmp_path / "tests" / "test_existing.py"
    existing.parent.mkdir(parents=True)
    existing.write_text("original\n", encoding="utf-8")

    written, skipped = generator.write_test_stubs(
        tmp_path,
        [
            generator.GeneratedTestStub(
                path="tests/test_existing.py",
                rationale="Existing",
                content="updated\n",
            ),
            generator.GeneratedTestStub(
                path="../outside.py",
                rationale="Unsafe",
                content="bad\n",
            ),
            generator.GeneratedTestStub(
                path="tests/test_new.py",
                rationale="New",
                content="def test_new():\n    assert True\n",
            ),
        ],
    )

    assert [path.relative_to(tmp_path).as_posix() for path in written] == ["tests/test_new.py"]
    assert "Skipped existing file: tests/test_existing.py" in skipped
    assert "Skipped unsafe path outside repository: ../outside.py" in skipped
    assert existing.read_text(encoding="utf-8") == "original\n"


def test_generate_test_stubs_parses_llm_json(monkeypatch, tmp_path: Path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "service.py").write_text("def handle():\n    return 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_existing.py").write_text(
        "def test_existing():\n    assert True\n",
        encoding="utf-8",
    )

    fake_commit = type("Commit", (), {"files_changed": ["app/service.py"]})()
    fake_group = type("Group", (), {"all_files": ["app/service.py"]})()
    monkeypatch.setattr(
        generator,
        "read_commits",
        lambda repo_path, max_commits=100: type("ReadResult", (), {"commits": [fake_commit]})(),
    )
    monkeypatch.setattr(
        generator,
        "filter_commits",
        lambda commits: type("FilterResult", (), {"commits": commits})(),
    )
    monkeypatch.setattr(generator, "group_commits_auto", lambda commits: [fake_group])
    monkeypatch.setattr(generator, "format_groups_for_llm", lambda groups: "- app/service.py changed")
    monkeypatch.setattr(generator, "create_client", lambda: _FakeClient(
        """
        ```json
        {
          "summary": "Generated a pytest stub for the recent service change.",
          "stubs": [
            {
              "path": "tests/test_service.py",
              "rationale": "Validate the service behavior entrypoint.",
              "source_files": ["app/service.py"],
              "content": "def test_handle():\\n    assert True\\n"
            }
          ]
        }
        ```
        """
    ))

    result = generator.generate_test_stubs(tmp_path, max_stubs=1)

    assert result.summary == "Generated a pytest stub for the recent service change."
    assert len(result.stubs) == 1
    assert result.stubs[0].path == "tests/test_service.py"
    assert result.stubs[0].source_files == ["app/service.py"]
    assert "tests/test_service.py" in result.markdown_report
