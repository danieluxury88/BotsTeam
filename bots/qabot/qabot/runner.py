"""Test runner — detects and executes test suites."""

import importlib.util
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass
class TestFrameworkInfo:
    """Information about detected test framework."""
    name: Literal["pytest", "unittest", "none"]
    test_dir: Path | None
    test_files_count: int
    command: list[str]  # Command to run tests


@dataclass
class TestRunResult:
    """Result of running tests."""
    framework: str
    exit_code: int
    stdout: str
    stderr: str
    passed: bool
    summary: str
    coverage: "CoverageReport | None" = None


@dataclass
class CoverageFileResult:
    """Coverage summary for a single measured file."""

    path: str
    percent_covered: float
    covered_lines: int
    total_statements: int
    missing_lines: int


@dataclass
class CoverageReport:
    """Coverage results for a test run."""

    generated: bool
    summary: str
    total_percent: float = 0.0
    covered_lines: int = 0
    total_statements: int = 0
    measured_files: int = 0
    low_coverage_files: list[CoverageFileResult] = None
    raw_output: str = ""

    def __post_init__(self) -> None:
        if self.low_coverage_files is None:
            self.low_coverage_files = []


def detect_test_framework(repo_path: Path) -> TestFrameworkInfo:
    """
    Detect which test framework is used in the repository.

    Checks for:
    - pytest: pyproject.toml with [tool.pytest], pytest.ini, or test files with pytest
    - unittest: test files with unittest imports
    """
    repo_path = Path(repo_path).resolve()

    # Check for pytest indicators
    has_pytest_config = any([
        (repo_path / "pytest.ini").exists(),
        (repo_path / "pyproject.toml").exists(),  # Could have [tool.pytest]
        (repo_path / "setup.cfg").exists(),
    ])

    # Find test directories
    test_dirs = []
    for pattern in ["test", "tests", "test_*", "*_test"]:
        test_dirs.extend(repo_path.glob(f"**/{pattern}"))

    # Find test files
    test_files = []
    for pattern in ["test_*.py", "*_test.py"]:
        test_files.extend(repo_path.rglob(pattern))

    test_files = [f for f in test_files if not any(p in f.parts for p in ['.venv', 'venv', '__pycache__', '.git'])]

    if not test_files:
        return TestFrameworkInfo(
            name="none",
            test_dir=None,
            test_files_count=0,
            command=[]
        )

    # Default to pytest if config exists or if test files found
    if has_pytest_config or test_files:
        test_dir = test_dirs[0] if test_dirs else repo_path
        return TestFrameworkInfo(
            name="pytest",
            test_dir=test_dir,
            test_files_count=len(test_files),
            command=["pytest", "-v"]
        )

    # Fallback to unittest
    return TestFrameworkInfo(
        name="unittest",
        test_dir=test_dirs[0] if test_dirs else repo_path,
        test_files_count=len(test_files),
        command=["python", "-m", "unittest", "discover"]
    )


def _has_coverage_module() -> bool:
    """Return whether coverage.py is available in the current environment."""
    return importlib.util.find_spec("coverage") is not None


def _build_coverage_run_command(data_file: Path, framework: str) -> list[str]:
    """Build a portable coverage.py command for the detected test framework."""
    command = [
        sys.executable,
        "-m",
        "coverage",
        "run",
        f"--data-file={data_file}",
        "-m",
    ]

    if framework == "pytest":
        return command + ["pytest", "-v"]
    if framework == "unittest":
        return command + ["unittest", "discover"]

    raise ValueError(f"Coverage is not supported for test framework '{framework}'.")


def _parse_coverage_report(
    repo_path: Path,
    json_path: Path,
    min_coverage: float,
    raw_output: str = "",
) -> CoverageReport:
    """Parse coverage.py JSON output into a compact report."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    totals = data.get("totals", {})
    files = data.get("files", {})

    low_coverage_files: list[CoverageFileResult] = []
    for file_path, entry in files.items():
        summary = entry.get("summary", {})
        total_statements = int(summary.get("num_statements", 0) or 0)
        if total_statements <= 0:
            continue

        path_obj = Path(file_path)
        try:
            display_path = str(path_obj.resolve().relative_to(repo_path.resolve()))
        except ValueError:
            display_path = file_path

        coverage_file = CoverageFileResult(
            path=display_path,
            percent_covered=round(float(summary.get("percent_covered", 0.0) or 0.0), 1),
            covered_lines=int(summary.get("covered_lines", 0) or 0),
            total_statements=total_statements,
            missing_lines=int(summary.get("missing_lines", 0) or 0),
        )
        if coverage_file.percent_covered < min_coverage:
            low_coverage_files.append(coverage_file)

    low_coverage_files.sort(key=lambda item: (item.percent_covered, item.path))

    total_percent = round(float(totals.get("percent_covered", 0.0) or 0.0), 1)
    measured_files = sum(
        1
        for entry in files.values()
        if int(entry.get("summary", {}).get("num_statements", 0) or 0) > 0
    )

    summary = (
        f"Coverage {total_percent:.1f}% across {measured_files} file(s)"
        if measured_files
        else "Coverage report generated, but no measured files were found"
    )
    if low_coverage_files:
        summary += f"; {len(low_coverage_files)} file(s) below {min_coverage:.1f}%"

    return CoverageReport(
        generated=True,
        summary=summary,
        total_percent=total_percent,
        covered_lines=int(totals.get("covered_lines", 0) or 0),
        total_statements=int(totals.get("num_statements", 0) or 0),
        measured_files=measured_files,
        low_coverage_files=low_coverage_files,
        raw_output=raw_output,
    )


def _generate_coverage_report(
    repo_path: Path,
    framework_info: TestFrameworkInfo,
    min_coverage: float,
) -> tuple[list[str], CoverageReport]:
    """Run tests under coverage.py and parse the resulting report."""
    if framework_info.name not in {"pytest", "unittest"}:
        raise ValueError(f"Coverage is not supported for test framework '{framework_info.name}'.")

    with tempfile.TemporaryDirectory(prefix="qabot-coverage-") as temp_dir:
        temp_dir_path = Path(temp_dir)
        data_file = temp_dir_path / ".coverage"
        json_path = temp_dir_path / "coverage.json"

        run_command = _build_coverage_run_command(data_file, framework_info.name)
        run_result = subprocess.run(
            run_command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=300,
        )

        coverage_report = CoverageReport(
            generated=False,
            summary="Coverage data was not generated.",
        )

        json_command = [
            sys.executable,
            "-m",
            "coverage",
            "json",
            f"--data-file={data_file}",
            "-o",
            str(json_path),
        ]
        json_result = subprocess.run(
            json_command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=120,
        )

        raw_coverage_output = "\n".join(
            part.strip()
            for part in [json_result.stdout, json_result.stderr]
            if part and part.strip()
        )

        if json_result.returncode == 0 and json_path.exists():
            coverage_report = _parse_coverage_report(
                repo_path,
                json_path,
                min_coverage,
                raw_output=raw_coverage_output,
            )
        else:
            message = raw_coverage_output or "coverage.py could not generate a JSON report."
            coverage_report = CoverageReport(
                generated=False,
                summary=message,
                raw_output=raw_coverage_output,
            )

        return run_command, run_result, coverage_report


def run_tests(
    repo_path: Path,
    framework_info: TestFrameworkInfo | None = None,
    *,
    with_coverage: bool = False,
    min_coverage: float = 80.0,
) -> TestRunResult:
    """
    Run tests in the repository.

    If framework_info is not provided, will detect it automatically.
    """
    repo_path = Path(repo_path).resolve()

    if framework_info is None:
        framework_info = detect_test_framework(repo_path)

    if framework_info.name == "none":
        return TestRunResult(
            framework="none",
            exit_code=-1,
            stdout="",
            stderr="No tests found in repository",
            passed=False,
            summary="No test framework or test files detected",
        )

    if with_coverage and not _has_coverage_module():
        return TestRunResult(
            framework=framework_info.name,
            exit_code=-1,
            stdout="",
            stderr="coverage.py is not installed in the current environment",
            passed=False,
            summary="coverage.py not installed",
            coverage=CoverageReport(
                generated=False,
                summary="coverage.py is not installed in the current environment",
            ),
        )

    # Run the tests
    try:
        coverage_report: CoverageReport | None = None
        if with_coverage:
            _, result, coverage_report = _generate_coverage_report(
                repo_path,
                framework_info,
                min_coverage,
            )
        else:
            result = subprocess.run(
                framework_info.command,
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

        passed = result.returncode == 0

        # Extract summary from output
        summary = _extract_test_summary(result.stdout, framework_info.name)

        return TestRunResult(
            framework=framework_info.name,
            exit_code=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            passed=passed,
            summary=summary,
            coverage=coverage_report,
        )

    except subprocess.TimeoutExpired:
        return TestRunResult(
            framework=framework_info.name,
            exit_code=-1,
            stdout="",
            stderr="Test execution timed out after 5 minutes",
            passed=False,
            summary="Tests timed out",
        )
    except FileNotFoundError:
        return TestRunResult(
            framework=framework_info.name,
            exit_code=-1,
            stdout="",
            stderr=f"Test command not found: {framework_info.command[0]}",
            passed=False,
            summary=f"{framework_info.name} not installed",
        )
    except Exception as e:
        return TestRunResult(
            framework=framework_info.name,
            exit_code=-1,
            stdout="",
            stderr=str(e),
            passed=False,
            summary=f"Error running tests: {e}",
        )


def _extract_test_summary(output: str, framework: str) -> str:
    """Extract a brief summary from test output."""
    if not output:
        return "No output"

    lines = output.strip().split("\n")

    # For pytest, look for the summary line
    if framework == "pytest":
        for line in reversed(lines):
            if "passed" in line or "failed" in line or "error" in line:
                return line.strip()

    # For unittest, look for the final OK or FAILED line
    if framework == "unittest":
        for line in reversed(lines):
            if "OK" in line or "FAILED" in line:
                return line.strip()

    # Fallback: return last non-empty line
    for line in reversed(lines):
        if line.strip():
            return line.strip()

    return "Tests completed"
