"""Test runner — detects and executes test suites."""

import subprocess
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


def run_tests(repo_path: Path, framework_info: TestFrameworkInfo | None = None) -> TestRunResult:
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
            summary="No test framework or test files detected"
        )

    # Run the tests
    try:
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
            summary=summary
        )

    except subprocess.TimeoutExpired:
        return TestRunResult(
            framework=framework_info.name,
            exit_code=-1,
            stdout="",
            stderr="Test execution timed out after 5 minutes",
            passed=False,
            summary="Tests timed out"
        )
    except FileNotFoundError:
        return TestRunResult(
            framework=framework_info.name,
            exit_code=-1,
            stdout="",
            stderr=f"Test command not found: {framework_info.command[0]}",
            passed=False,
            summary=f"{framework_info.name} not installed"
        )
    except Exception as e:
        return TestRunResult(
            framework=framework_info.name,
            exit_code=-1,
            stdout="",
            stderr=str(e),
            passed=False,
            summary=f"Error running tests: {e}"
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
