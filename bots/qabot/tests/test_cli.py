from __future__ import annotations

from typer.testing import CliRunner

from qabot import cli
from qabot import runner as qa_runner


runner = CliRunner()


def test_run_command_supports_coverage(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "detect_test_framework", lambda repo_path: qa_runner.TestFrameworkInfo(
        name="pytest",
        test_dir=repo_path / "tests",
        test_files_count=2,
        command=["pytest", "-v"],
    ))
    monkeypatch.setattr(cli, "run_tests", lambda repo_path, framework_info, **kwargs: qa_runner.TestRunResult(
        framework=framework_info.name,
        exit_code=0,
        stdout="================== 3 passed in 0.10s ==================\n",
        stderr="",
        passed=True,
        summary="3 passed in 0.10s",
        coverage=qa_runner.CoverageReport(
            generated=True,
            summary="Coverage 78.0% across 2 file(s); 1 file(s) below 80.0%",
            total_percent=78.0,
            covered_lines=39,
            total_statements=50,
            measured_files=2,
            low_coverage_files=[
                qa_runner.CoverageFileResult(
                    path="pkg/service.py",
                    percent_covered=62.0,
                    covered_lines=31,
                    total_statements=50,
                    missing_lines=19,
                )
            ],
        ),
    ))

    result = runner.invoke(
        cli.app,
        ["run", str(tmp_path), "--coverage"],
    )

    assert result.exit_code == 0
    assert "coverage" in result.output.lower()
    assert "pkg/service.py" in result.output
