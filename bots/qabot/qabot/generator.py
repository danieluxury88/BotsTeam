"""Test stub generator for QABot."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from qabot.runner import detect_test_framework
from shared.config import load_env
from shared.git_reader import filter_commits, format_groups_for_llm, group_commits_auto, read_commits
from shared.llm import chat

load_env()

GENERATOR_SYSTEM_PROMPT = """\
You are QABot, an expert software testing engineer.

Your job is to generate minimal, practical test stub files for the repository changes you receive.

Rules:
- Return JSON only.
- Prefer the repository's existing test style, naming, and directory conventions.
- Generate compilable or near-compilable stubs with TODO markers when implementation details are unknown.
- Do not invent business logic assertions you cannot justify from the provided context.
- Keep each stub focused and small.
- If the project appears to use Drupal, prefer PHPUnit/Drupal test patterns when appropriate.
"""


@dataclass
class GeneratedTestStub:
    """A proposed or written test stub file."""

    path: str
    rationale: str
    source_files: list[str] = field(default_factory=list)
    content: str = ""


@dataclass
class TestGenerationResult:
    """Result of generating test stubs."""

    summary: str
    stubs: list[GeneratedTestStub] = field(default_factory=list)
    markdown_report: str = ""
    raw_response: str = ""


@dataclass
class RepoTestProfile:
    """Lightweight test-generation context inferred from a repository."""

    primary_language: str
    frameworks: list[str] = field(default_factory=list)
    test_framework: str = "none"
    style_hint: str = ""


def _extract_json_block(text: str) -> dict:
    """Parse a JSON object from a raw LLM response."""
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3:
            candidate = "\n".join(lines[1:-1]).strip()

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("QABot could not find JSON in the model response.")
        return json.loads(candidate[start:end + 1])


def _infer_repo_profile(repo_path: Path, changed_files: list[str]) -> RepoTestProfile:
    """Infer basic test-generation hints from changed files and repository markers."""
    suffixes = {Path(path).suffix.lower() for path in changed_files}
    composer = (repo_path / "composer.json").exists()
    drupal_markers = any([
        (repo_path / "web" / "core" / "lib" / "Drupal.php").exists(),
        (repo_path / "core" / "lib" / "Drupal.php").exists(),
        (repo_path / "web" / "modules" / "custom").exists(),
        (repo_path / "modules" / "custom").exists(),
    ])

    frameworks: list[str] = []
    if drupal_markers:
        frameworks.append("Drupal")
    if composer or ".php" in suffixes:
        frameworks.append("PHPUnit")

    primary_language = "python"
    if composer or ".php" in suffixes:
        primary_language = "php"
    elif ".js" in suffixes:
        primary_language = "javascript"
    elif ".ts" in suffixes or ".tsx" in suffixes:
        primary_language = "typescript"

    detected_framework = detect_test_framework(repo_path).name
    style_hint = "Use repository test conventions."
    if "Drupal" in frameworks:
        style_hint = (
            "Prefer Drupal/PHPUnit conventions such as Unit, Kernel, or Functional test classes "
            "when the changed files suggest module/service behavior."
        )
    elif primary_language == "php":
        style_hint = "Prefer PHPUnit-style class-based test stubs."
    elif detected_framework == "pytest":
        style_hint = "Prefer pytest test functions or small test classes."

    return RepoTestProfile(
        primary_language=primary_language,
        frameworks=frameworks,
        test_framework=detected_framework,
        style_hint=style_hint,
    )


def _sample_existing_tests(repo_path: Path, max_files: int = 3, max_chars: int = 2400) -> str:
    """Return a few short existing test snippets to anchor generation style."""
    patterns = ("test_*.py", "*_test.py", "*Test.php")
    samples: list[str] = []
    remaining = max_chars

    for pattern in patterns:
        for path in sorted(repo_path.rglob(pattern)):
            if any(part in {".git", ".venv", "venv", "__pycache__"} for part in path.parts):
                continue
            try:
                snippet = path.read_text(encoding="utf-8")[:700].strip()
            except OSError:
                continue
            if not snippet:
                continue
            rel_path = path.resolve().relative_to(repo_path.resolve())
            block = f"## {rel_path}\n{snippet}\n"
            if len(block) > remaining:
                continue
            samples.append(block)
            remaining -= len(block)
            if len(samples) >= max_files:
                return "\n".join(samples)
    return "\n".join(samples)


def _build_generation_report(result: TestGenerationResult) -> str:
    """Render generated stubs as markdown."""
    lines = [
        "# QABot Test Stub Generation",
        "",
        result.summary,
        "",
    ]
    if not result.stubs:
        lines.append("_No stubs generated._")
        return "\n".join(lines)

    for stub in result.stubs:
        lines.extend([
            f"## `{stub.path}`",
            "",
            f"- Rationale: {stub.rationale}",
            f"- Source files: {', '.join(stub.source_files) if stub.source_files else 'not specified'}",
            "",
            "```",
            stub.content.rstrip(),
            "```",
            "",
        ])
    return "\n".join(lines).strip()


def generate_test_stubs(
    repo_path: Path,
    max_commits: int = 100,
    model: str | None = None,
    max_stubs: int = 3,
) -> TestGenerationResult:
    """Generate test stubs for recent repository changes."""
    read_result = read_commits(repo_path, max_commits=max_commits)
    commits = filter_commits(read_result.commits).commits
    if not commits:
        return TestGenerationResult(
            summary="No recent commits found to generate tests from.",
            markdown_report="# QABot Test Stub Generation\n\nNo recent commits found to generate tests from.",
        )

    groups = group_commits_auto(commits)
    formatted_history = format_groups_for_llm(groups)

    changed_files: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for file_path in group.all_files:
            if file_path not in seen:
                seen.add(file_path)
                changed_files.append(file_path)

    profile = _infer_repo_profile(repo_path, changed_files)
    test_samples = _sample_existing_tests(repo_path)

    user_message = f"""\
Generate up to {max_stubs} practical test stub files for the recent changes in the repository **{repo_path.name}**.

Repository test profile:
- Primary language: {profile.primary_language}
- Frameworks: {', '.join(profile.frameworks) or 'none detected'}
- Existing test framework: {profile.test_framework}
- Style hint: {profile.style_hint}

Recent change history:
{formatted_history}

Changed files:
{chr(10).join(f"- {path}" for path in changed_files[:25])}

Existing test examples (if any):
{test_samples or "No existing tests found."}

Return JSON with this shape:
{{
  "summary": "one short paragraph",
  "stubs": [
    {{
      "path": "relative/path/to/test/file",
      "rationale": "why this file matters",
      "source_files": ["relative/source/file.php"],
      "content": "full test stub file content"
    }}
  ]
}}

Choose file paths that fit the repository conventions. Keep the stubs minimal but useful.
"""

    raw_response = chat(system=GENERATOR_SYSTEM_PROMPT, user=user_message, max_tokens=4096, model=model)
    payload = _extract_json_block(raw_response)
    stub_payloads = payload.get("stubs", []) or []
    stubs = [
        GeneratedTestStub(
            path=str(item.get("path", "")).strip(),
            rationale=str(item.get("rationale", "")).strip(),
            source_files=[str(value).strip() for value in item.get("source_files", []) if str(value).strip()],
            content=str(item.get("content", "")).rstrip() + "\n",
        )
        for item in stub_payloads
        if str(item.get("path", "")).strip() and str(item.get("content", "")).strip()
    ]

    result = TestGenerationResult(
        summary=str(payload.get("summary", "Generated test stubs from recent changes.")).strip(),
        stubs=stubs,
        raw_response=raw_response,
    )
    result.markdown_report = _build_generation_report(result)
    return result


def write_test_stubs(
    repo_path: Path,
    stubs: list[GeneratedTestStub],
    *,
    overwrite: bool = False,
) -> tuple[list[Path], list[str]]:
    """Write generated test stubs into the repository."""
    written: list[Path] = []
    skipped: list[str] = []

    for stub in stubs:
        target = (repo_path / stub.path).resolve()
        try:
            target.relative_to(repo_path.resolve())
        except ValueError:
            skipped.append(f"Skipped unsafe path outside repository: {stub.path}")
            continue

        if target.exists() and not overwrite:
            skipped.append(f"Skipped existing file: {stub.path}")
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(stub.content, encoding="utf-8")
        written.append(target)

    return written, skipped
