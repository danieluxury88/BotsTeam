"""QA Analyzer — asks Claude what to test based on recent code changes."""

from dataclasses import dataclass, field
from pathlib import Path

from shared.config import get_default_model, load_env
from shared.git_reader import CommitGroup, read_commits, group_commits_auto, format_groups_for_llm
from shared.llm import create_client
from shared.models import ChangeSet, BotResult

load_env()

SYSTEM_PROMPT = """\
You are QABot, an expert software testing engineer and QA analyst.

Your job is to analyze recent code changes in a repository and suggest:
- What should be tested based on the changes
- Which areas are most at risk
- What types of tests are needed (unit, integration, e2e)
- Specific test scenarios to consider

Guidelines:
- Be specific and actionable — suggest concrete test cases, not generic advice
- Prioritize high-risk areas (core logic, user-facing features, data handling)
- Consider edge cases and failure scenarios
- Format your response in clean Markdown with sections
- If you detect a test framework or existing tests, reference them
"""


@dataclass
class TestSuggestion:
    """A suggested test based on code changes."""
    area: str                   # What to test (e.g., "Authentication module")
    priority: str               # "high" | "medium" | "low"
    test_type: str              # "unit" | "integration" | "e2e"
    description: str            # What to test
    rationale: str              # Why this test matters


@dataclass
class QAAnalysisResult:
    """Result of analyzing what to test."""
    summary: str                                    # High-level summary
    suggestions: list[TestSuggestion] = field(default_factory=list)
    risk_areas: list[str] = field(default_factory=list)
    markdown_report: str = ""


def analyze_changes_for_testing(
    repo_path: Path,
    max_commits: int = 100,
    model: str | None = None,
) -> QAAnalysisResult:
    """
    Analyze recent changes and suggest what to test.

    Returns structured test suggestions with priorities.
    """
    # Read recent commits
    commits = read_commits(repo_path, max_commits=max_commits)
    if not commits:
        return QAAnalysisResult(
            summary="No commits found to analyze.",
            markdown_report="## No Changes\n\nNo commits found in repository."
        )

    # Group commits for context
    groups = group_commits_auto(commits)
    formatted_history = format_groups_for_llm(groups)

    # Ask Claude what to test
    effective_model = model or get_default_model()
    client = create_client()

    repo_name = repo_path.name

    user_message = f"""\
Analyze the following recent changes in the **{repo_name}** repository and suggest what should be tested.

{formatted_history}

Provide a structured QA analysis with:

1. **Testing Summary** — one paragraph overview of what changed and testing implications
2. **Priority Test Areas** — the 3-5 most important things to test, with:
   - Area/Component name
   - Priority (High/Medium/Low)
   - Test type (Unit/Integration/E2E)
   - What to test specifically
   - Why it matters (risk/impact)
3. **Risk Areas** — parts of the codebase at highest risk from these changes
4. **Recommended Test Strategy** — approach to validating these changes

Be specific and actionable.
"""

    message = client.messages.create(
        model=effective_model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    report = message.content[0].text

    # TODO: Parse structured suggestions from Claude's response
    # For now, return the full markdown report
    return QAAnalysisResult(
        summary="Analysis complete - see full report",
        markdown_report=report,
    )


def analyze_changeset_for_testing(
    changeset: ChangeSet,
    model: str | None = None,
) -> QAAnalysisResult:
    """
    Analyze a ChangeSet (from gitbot) and suggest what to test.

    This enables gitbot → qabot pipeline.
    """
    # Format changeset for Claude
    files_summary = "\n".join(f"  - {f}" for f in changeset.files_touched[:20])
    if len(changeset.files_touched) > 20:
        files_summary += f"\n  ... and {len(changeset.files_touched) - 20} more files"

    effective_model = model or get_default_model()
    client = create_client()

    user_message = f"""\
Analyze these recent code changes and suggest what should be tested.

**Change Summary:**
{changeset.summary}

**Files Modified:**
{files_summary}

**Additional Context:**
{changeset.raw_data.get('commit_count', 'N/A')} commits analyzed

Provide a structured QA analysis with:

1. **Testing Summary** — one paragraph overview
2. **Priority Test Areas** — the 3-5 most important things to test (with priorities)
3. **Risk Areas** — parts of the codebase at highest risk
4. **Recommended Test Strategy** — approach to validation

Be specific and actionable with concrete test scenarios.
"""

    message = client.messages.create(
        model=effective_model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    report = message.content[0].text

    return QAAnalysisResult(
        summary="Analysis complete - see full report",
        markdown_report=report,
    )


def get_bot_result(
    repo_path: Path | str,
    max_commits: int = 100,
    model: str | None = None,
    project_name: str | None = None,
) -> BotResult:
    """
    Return qabot analysis as a BotResult for orchestrator integration.

    Args:
        repo_path: Path to the git repository
        max_commits: Maximum number of commits to analyze
        model: Optional Claude model override
        project_name: Optional project name for auto-saving reports

    Returns:
        BotResult with QA analysis and markdown report
    """
    try:
        repo_path = Path(repo_path).resolve()
        result = analyze_changes_for_testing(repo_path, max_commits, model)

        bot_result = BotResult(
            bot_name="qabot",
            status="success",
            summary=result.summary,
            data={
                "suggestions": result.suggestions,
                "risk_areas": result.risk_areas,
            },
            markdown_report=result.markdown_report,
        )

        # Auto-save report if project_name is provided
        if project_name:
            from shared.data_manager import save_report
            latest, timestamped = save_report(
                project_name,
                "qabot",
                result.markdown_report,
                save_latest=True,
                save_timestamped=True,
            )
            bot_result.data["report_saved"] = {
                "latest": str(latest),
                "timestamped": str(timestamped) if timestamped else None,
            }

        return bot_result
    except Exception as e:
        return BotResult(
            bot_name="qabot",
            status="error",
            summary=f"Failed to analyze repository: {str(e)}",
            data={"error": str(e)},
            markdown_report="",
        )
