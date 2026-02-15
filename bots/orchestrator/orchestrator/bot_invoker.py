"""Bot invoker — calls gitbot, qabot, and pmbot programmatically."""

from pathlib import Path
from typing import Literal

from gitbot.analyzer import get_bot_result as gitbot_get_result
from qabot.analyzer import get_bot_result as qabot_get_result
from project_manager.analyzer import get_bot_result as pmbot_get_result
from shared.models import BotResult, IssueSet
from shared.gitlab_client import fetch_issues as gitlab_fetch_issues
from shared.github_client import fetch_issues as github_fetch_issues


BotName = Literal["gitbot", "qabot", "pmbot"]


def invoke_bot(
    bot_name: BotName,
    project: "Project | None" = None,
    repo_path: Path | str | None = None,  # Legacy
    project_id: str | None = None,  # Legacy
    max_commits: int = 100,
    model: str | None = None,
    pmbot_mode: str = "analyze",
) -> BotResult:
    """
    Invoke a bot programmatically.

    Args:
        bot_name: Which bot to invoke ("gitbot", "qabot", or "pmbot")
        project: Project object (preferred - contains all metadata)
        repo_path: Path to repository (legacy - for gitbot/qabot)
        project_id: GitLab project ID (legacy - for pmbot)
        max_commits: Max commits to analyze (gitbot/qabot)
        model: Optional Claude model override
        pmbot_mode: Mode for pmbot - "analyze" or "plan"

    Returns:
        BotResult with the bot's analysis
    """
    from orchestrator.registry import Project

    if bot_name in ["gitbot", "qabot"]:
        # Extract repo_path from project or use legacy parameter
        if project:
            repo_path = project.path

        if not repo_path:
            return BotResult(
                bot_name=bot_name, status="error",
                summary=f"{bot_name} requires repo_path or project",
                data={"error": "missing_repo_path"}, markdown_report="",
            )

        repo_path = Path(repo_path).resolve()
        if not repo_path.exists():
            return BotResult(
                bot_name=bot_name, status="error",
                summary=f"Repository path does not exist: {repo_path}",
                data={"error": "path_not_found"}, markdown_report="",
            )

        if bot_name == "gitbot":
            return gitbot_get_result(
                repo_path,
                max_commits=max_commits,
                model=model,
                project_name=project.name if project else None,
            )
        elif bot_name == "qabot":
            return qabot_get_result(
                repo_path,
                max_commits=max_commits,
                model=model,
                project_name=project.name if project else None,
            )

    elif bot_name == "pmbot":
        # Determine issue source: GitLab or GitHub
        issue_set: IssueSet | None = None

        if project:
            if project.has_gitlab():
                # GitLab path
                gitlab_token = project.get_gitlab_token()
                if not gitlab_token:
                    return BotResult(
                        bot_name=bot_name, status="error",
                        summary="GitLab token not found (check .env or project credentials)",
                        data={"error": "missing_gitlab_token"}, markdown_report="",
                    )
                try:
                    issue_set = gitlab_fetch_issues(
                        project_id=project.gitlab_project_id,
                        token=gitlab_token,
                        url=project.get_gitlab_url(),
                    )
                except Exception as e:
                    return BotResult(
                        bot_name=bot_name, status="error",
                        summary=f"Failed to fetch GitLab issues: {e}",
                        data={"error": "gitlab_fetch_failed"}, markdown_report="",
                    )

            elif project.has_github():
                # GitHub path
                github_token = project.get_github_token()
                if not github_token:
                    return BotResult(
                        bot_name=bot_name, status="error",
                        summary="GitHub token not found (check .env or project credentials)",
                        data={"error": "missing_github_token"}, markdown_report="",
                    )
                try:
                    issue_set = github_fetch_issues(
                        repo=project.github_repo,
                        token=github_token,
                        base_url=project.get_github_base_url(),
                    )
                except Exception as e:
                    return BotResult(
                        bot_name=bot_name, status="error",
                        summary=f"Failed to fetch GitHub issues: {e}",
                        data={"error": "github_fetch_failed"}, markdown_report="",
                    )

            else:
                return BotResult(
                    bot_name=bot_name, status="error",
                    summary=f"Project '{project.name}' has no GitLab or GitHub integration",
                    data={"error": "no_issue_integration"}, markdown_report="",
                )

        else:
            # Legacy mode — GitLab only via project_id parameter
            if not project_id:
                return BotResult(
                    bot_name=bot_name, status="error",
                    summary="pmbot requires project_id or Project with GitLab/GitHub integration",
                    data={"error": "missing_project_id"}, markdown_report="",
                )
            try:
                issue_set = gitlab_fetch_issues(project_id=project_id)
            except Exception as e:
                return BotResult(
                    bot_name=bot_name, status="error",
                    summary=f"Failed to fetch issues: {e}",
                    data={"error": "fetch_failed"}, markdown_report="",
                )

        return pmbot_get_result(
            issue_set,
            mode=pmbot_mode,
            project_name=project.name if project else None,
        )

    else:
        return BotResult(
            bot_name=bot_name, status="error",
            summary=f"Unknown bot: {bot_name}",
            data={"error": "unknown_bot"}, markdown_report="",
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
