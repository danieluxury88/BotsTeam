"""Bot invoker — calls gitbot, qabot, and pmbot programmatically."""

from pathlib import Path
from typing import Literal

from gitbot.analyzer import get_bot_result as gitbot_get_result
from qabot.analyzer import get_bot_result as qabot_get_result
from project_manager.analyzer import get_bot_result as pmbot_get_result
from shared.models import BotResult, IssueSet
from shared.gitlab_client import fetch_issues


BotName = Literal["gitbot", "qabot", "pmbot"]


def invoke_bot(
    bot_name: BotName,
    repo_path: Path | str | None = None,
    project_id: str | None = None,
    max_commits: int = 100,
    model: str | None = None,
    pmbot_mode: str = "analyze",
) -> BotResult:
    """
    Invoke a bot programmatically.

    Args:
        bot_name: Which bot to invoke ("gitbot", "qabot", or "pmbot")
        repo_path: Path to the repository (for gitbot/qabot)
        project_id: GitLab project ID (for pmbot)
        max_commits: Maximum number of commits to analyze (gitbot/qabot)
        model: Optional Claude model override
        pmbot_mode: Mode for pmbot - "analyze" or "plan"

    Returns:
        BotResult with the bot's analysis
    """
    if bot_name in ["gitbot", "qabot"]:
        if not repo_path:
            return BotResult(
                bot_name=bot_name,
                status="error",
                summary=f"{bot_name} requires repo_path",
                data={"error": "missing_repo_path"},
                markdown_report="",
            )

        repo_path = Path(repo_path).resolve()

        if not repo_path.exists():
            return BotResult(
                bot_name=bot_name,
                status="error",
                summary=f"Repository path does not exist: {repo_path}",
                data={"error": "path_not_found"},
                markdown_report="",
            )

        if bot_name == "gitbot":
            return gitbot_get_result(repo_path, max_commits=max_commits, model=model)
        elif bot_name == "qabot":
            return qabot_get_result(repo_path, max_commits=max_commits, model=model)

    elif bot_name == "pmbot":
        if not project_id:
            return BotResult(
                bot_name=bot_name,
                status="error",
                summary="pmbot requires project_id",
                data={"error": "missing_project_id"},
                markdown_report="",
            )

        try:
            issue_set = fetch_issues(project_id=project_id)
            return pmbot_get_result(issue_set, mode=pmbot_mode)
        except Exception as e:
            return BotResult(
                bot_name=bot_name,
                status="error",
                summary=f"Failed to fetch issues: {e}",
                data={"error": "gitlab_fetch_failed"},
                markdown_report="",
            )

    else:
        return BotResult(
            bot_name=bot_name,
            status="error",
            summary=f"Unknown bot: {bot_name}",
            data={"error": "unknown_bot"},
            markdown_report="",
        )



def invoke_gitbot(repo_path: Path | str, max_commits: int = 100) -> BotResult:
    """Convenience function to invoke gitbot."""
    return invoke_bot("gitbot", repo_path=repo_path, max_commits=max_commits)


def invoke_qabot(repo_path: Path | str, max_commits: int = 50) -> BotResult:
    """Convenience function to invoke qabot."""
    return invoke_bot("qabot", repo_path=repo_path, max_commits=max_commits)


def invoke_pmbot(project_id: str, mode: str = "analyze") -> BotResult:
    """Convenience function to invoke pmbot."""
    return invoke_bot("pmbot", project_id=project_id, pmbot_mode=mode)
