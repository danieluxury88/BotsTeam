from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

from qabot import runner


def _framework() -> runner.TestFrameworkInfo:
    return runner.TestFrameworkInfo(
        name="pytest",
        test_dir=Path("tests"),
        test_files_count=3,
        command=["pytest", "-v"],
    )


def test_run_tests_with_coverage_parses_low_coverage_files(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "_has_coverage_module", lambda: True)

    def fake_run(command, cwd, capture_output, text, timeout):
        if command[:4] == [sys.executable, "-m", "coverage", "run"]:
            return SimpleNamespace(
                returncode=0,
                stdout="================== 5 passed in 0.12s ==================\n",
                stderr="",
            )

        if command[:4] == [sys.executable, "-m", "coverage", "json"]:
            output_path = Path(command[command.index("-o") + 1])
            output_path.write_text(json.dumps({
                "totals": {
                    "covered_lines": 15,
                    "num_statements": 20,
                    "percent_covered": 75.0,
                },
                "files": {
                    str(tmp_path / "pkg" / "service.py"): {
                        "summary": {
                            "covered_lines": 6,
                            "num_statements": 10,
                            "percent_covered": 60.0,
                            "missing_lines": 4,
                        }
                    },
                    str(tmp_path / "pkg" / "helpers.py"): {
                        "summary": {
                            "covered_lines": 9,
                            "num_statements": 10,
                            "percent_covered": 90.0,
                            "missing_lines": 1,
                        }
                    },
                },
            }), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)

    result = runner.run_tests(
        tmp_path,
        _framework(),
        with_coverage=True,
        min_coverage=80.0,
    )

    assert result.passed is True
    assert result.coverage is not None
    assert result.coverage.generated is True
    assert result.coverage.total_percent == 75.0
    assert result.coverage.measured_files == 2
    assert [item.path for item in result.coverage.low_coverage_files] == ["pkg/service.py"]


def test_run_tests_with_coverage_reports_missing_tool(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "_has_coverage_module", lambda: False)

    result = runner.run_tests(
        tmp_path,
        _framework(),
        with_coverage=True,
    )

    assert result.passed is False
    assert result.summary == "coverage.py not installed"
    assert result.coverage is not None
    assert result.coverage.generated is False

