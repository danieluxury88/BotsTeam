"""Bot invoker — calls all bots programmatically."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from gitbot.analyzer import get_changeset as gitbot_get_changeset
from gitbot.analyzer import get_bot_result as gitbot_get_result
from qabot.analyzer import analyze_changeset_for_testing
from qabot.analyzer import get_bot_result as qabot_get_result
from project_manager.runner import get_bot_result as pmbot_get_result
from pagespeedbot.analyzer import get_bot_result as pagespeedbot_get_result
from journalbot.analyzer import get_bot_result as journalbot_get_result
from taskbot.analyzer import get_bot_result as taskbot_get_result
from habitbot.analyzer import get_bot_result as habitbot_get_result
from notebot.analyzer import get_bot_result as notebot_get_result
from shared.data_manager import save_report
from shared.models import BotResult, ProjectScope

if TYPE_CHECKING:
    from orchestrator.registry import Project


BotName = Literal["gitbot", "qabot", "pmbot", "pagespeedbot", "journalbot", "taskbot", "habitbot", "notebot"]
PipelineName = Literal["gitbot_qabot"]


@dataclass(frozen=True)
class PipelineSpec:
    """Metadata for a multi-bot workflow."""

    id: str
    description: str


PIPELINES: dict[str, PipelineSpec] = {
    "gitbot_qabot": PipelineSpec(
        id="gitbot_qabot",
        description="Analyze recent changes with GitBot, then suggest tests with QABot.",
    ),
}


def _call_runner(
    runner,
    /,
    *args,
    base_kwargs: dict | None = None,
    bot_params: dict | None = None,
):
    """Call a bot runner with only the kwargs it actually accepts."""
    supported = inspect.signature(runner).parameters
    merged = {**(base_kwargs or {}), **(bot_params or {})}
    filtered = {
        key: value
        for key, value in merged.items()
        if key in supported and value is not None
    }
    return runner(*args, **filtered)


def _resolve_team_repo_path(bot_name: str, project: Project | None, repo_path: Path | str | None) -> Path | None:
    """Resolve and validate a repository path for team bots and pipelines."""
    if project:
        repo_path = project.path

    if not repo_path:
        return None

    resolved = Path(repo_path).resolve()
    if not resolved.exists():
        return None
    return resolved


def invoke_pipeline(
    pipeline_name: PipelineName | str,
    *,
    project: Project | None = None,
    repo_path: Path | str | None = None,
    max_commits: int = 300,
    model: str | None = None,
    since: str | None = None,
    until: str | None = None,
    bot_params: dict | None = None,
) -> BotResult:
    """Invoke a registered multi-bot pipeline."""
    if pipeline_name not in PIPELINES:
        return BotResult(
            bot_name=str(pipeline_name),
            status="error",
            summary=f"Unknown pipeline: {pipeline_name}",
            data={"error": "unknown_pipeline"},
            markdown_report="",
        )

    resolved_repo_path = _resolve_team_repo_path(str(pipeline_name), project, repo_path)
    if resolved_repo_path is None:
        return BotResult(
            bot_name=str(pipeline_name),
            status="error",
            summary=f"{pipeline_name} requires repo_path or project",
            data={"error": "missing_repo_path"},
            markdown_report="",
        )

    if pipeline_name == "gitbot_qabot":
        changeset = gitbot_get_changeset(
            resolved_repo_path,
            branch=(bot_params or {}).get("branch", "HEAD"),
            max_commits=(bot_params or {}).get("max_commits", max_commits),
            model=model,
            since=(bot_params or {}).get("since", since),
            until=(bot_params or {}).get("until", until),
        )

        commit_count = int(changeset.raw_data.get("commit_count", 0) or 0)
        if commit_count == 0:
            markdown_report = (
                "# GitBot -> QABot Pipeline\n\n"
                "No recent commits were found for the requested range, so there is nothing new to test."
            )
            return BotResult(
                bot_name="gitbot_qabot",
                status="success",
                summary="No recent commits found for the GitBot -> QABot pipeline.",
                data={"pipeline": "gitbot_qabot", "changeset": changeset},
                markdown_report=markdown_report,
            )

        qa_result = analyze_changeset_for_testing(changeset, model=model)
        markdown_report = "\n".join(
            [
                f"# {project.name if project else resolved_repo_path.name}: GitBot -> QABot",
                "",
                "## GitBot Summary",
                "",
                changeset.summary.strip(),
                "",
                "## QABot Test Recommendations",
                "",
                qa_result.markdown_report.strip(),
            ]
        ).strip()

        result = BotResult(
            bot_name="gitbot_qabot",
            status="success",
            summary="GitBot analyzed recent changes and QABot generated test recommendations.",
            data={
                "pipeline": "gitbot_qabot",
                "changeset": changeset,
                "risk_areas": qa_result.risk_areas,
                "suggestions": qa_result.suggestions,
            },
            markdown_report=markdown_report,
        )

        if project:
            latest, timestamped = save_report(
                project.name,
                "orchestrator",
                markdown_report,
                save_latest=True,
                save_timestamped=True,
            )
            result.data["report_saved"] = {
                "latest": str(latest),
                "timestamped": str(timestamped) if timestamped else None,
            }

        return result

    return BotResult(
        bot_name=str(pipeline_name),
        status="error",
        summary=f"Pipeline not implemented: {pipeline_name}",
        data={"error": "pipeline_not_implemented"},
        markdown_report="",
    )


def invoke_bot(
    bot_name: BotName,
    project: Project | None = None,
    repo_path: Path | str | None = None,   # Legacy
    project_id: str | None = None,          # Legacy
    max_commits: int = 300,
    model: str | None = None,
    pmbot_mode: str = "analyze",
    since: str | None = None,
    until: str | None = None,
    bot_params: dict | None = None,
) -> BotResult:
    """
    Invoke a bot programmatically.

    Args:
        bot_name: Which bot to invoke
        project: Project object (preferred — contains path, scope, data sources)
        repo_path: Path to repository (legacy fallback for gitbot/qabot)
        project_id: GitLab project ID (legacy fallback for pmbot)
        max_commits: Max commits to analyze (gitbot/qabot)
        model: Optional Claude model override
        pmbot_mode: "analyze" or "plan" (pmbot only)
        since: Only commits after this date, ISO format (gitbot)
        until: Only commits before this date, ISO format (gitbot)

    Returns:
        BotResult with the bot's analysis
    """
    scope = project.scope if project else ProjectScope.TEAM

    # ── Personal bots ─────────────────────────────────────────────────────────

    if bot_name == "journalbot":
        if not project:
            return BotResult(
                bot_name="journalbot", status="error",
                summary="journalbot requires a registered project with notes_dir configured",
                data={"error": "missing_project"}, markdown_report="",
            )
        notes_path = Path(project.notes_dir) if project.notes_dir else project.path
        return journalbot_get_result(
            notes_path,
            model=model,
            project_name=project.name,
            scope=scope,
        )

    if bot_name == "taskbot":
        if not project:
            return BotResult(
                bot_name="taskbot", status="error",
                summary="taskbot requires a registered project with task_file configured",
                data={"error": "missing_project"}, markdown_report="",
            )
        task_path = Path(project.task_file) if project.task_file else project.path
        return taskbot_get_result(
            task_path,
            model=model,
            project_name=project.name,
            scope=scope,
        )

    if bot_name == "habitbot":
        if not project:
            return BotResult(
                bot_name="habitbot", status="error",
                summary="habitbot requires a registered project with habit_file configured",
                data={"error": "missing_project"}, markdown_report="",
            )
        if not project.habit_file:
            return BotResult(
                bot_name="habitbot", status="error",
                summary=f"Project '{project.name}' has no habit_file configured",
                data={"error": "missing_habit_file"}, markdown_report="",
            )
        return habitbot_get_result(
            Path(project.habit_file),
            model=model,
            project_name=project.name,
            scope=scope,
        )

    if bot_name == "notebot":
        from shared.data_manager import get_notes_dir
        notes_dir = get_notes_dir(project.name, scope) if project else Path("notes")
        return notebot_get_result(
            notes_dir,
            model=model,
            project_name=project.name if project else None,
            scope=scope,
        )

    # ── Team bots ─────────────────────────────────────────────────────────────

    if bot_name in ("gitbot", "qabot"):
        resolved_repo_path = _resolve_team_repo_path(bot_name, project, repo_path)
        if resolved_repo_path is None:
            return BotResult(
                bot_name=bot_name, status="error",
                summary=f"{bot_name} requires repo_path or project",
                data={"error": "missing_repo_path"}, markdown_report="",
            )

        if bot_name == "gitbot":
            return _call_runner(
                gitbot_get_result,
                resolved_repo_path,
                base_kwargs={
                    "max_commits": max_commits,
                    "model": model,
                    "project_name": project.name if project else None,
                    "since": since,
                    "until": until,
                },
                bot_params=bot_params,
            )
        else:
            return _call_runner(
                qabot_get_result,
                resolved_repo_path,
                base_kwargs={
                    "max_commits": max_commits,
                    "model": model,
                    "project_name": project.name if project else None,
                },
                bot_params=bot_params,
            )

    if bot_name == "pagespeedbot":
        if not project:
            return BotResult(
                bot_name=bot_name, status="error",
                summary="pagespeedbot requires a registered project with site_url configured",
                data={"error": "missing_project"}, markdown_report="",
            )
        if not project.site_url:
            return BotResult(
                bot_name=bot_name, status="error",
                summary=f"Project '{project.name}' has no site_url configured",
                data={"error": "missing_site_url"}, markdown_report="",
            )
        return _call_runner(
            pagespeedbot_get_result,
            project.site_url,
            base_kwargs={
                "audit_urls": tuple(project.audit_urls or []),
                "project_name": project.name,
                "scope": scope,
                "report_branding_profile": project.report_branding_profile,
                "report_prepared_by": project.report_prepared_by,
                "report_client_name": project.report_client_name,
                "report_footer_text": project.report_footer_text,
            },
            bot_params=bot_params,
        )

    if bot_name == "pmbot":
        if project:
            if not project.has_gitlab() and not project.has_github():
                return BotResult(
                    bot_name=bot_name, status="error",
                    summary=f"Project '{project.name}' has no GitLab or GitHub integration",
                    data={"error": "no_issue_integration"}, markdown_report="",
                )
            return _call_runner(
                pmbot_get_result,
                base_kwargs={
                    "project_name": project.name,
                    "gitlab_project_id": project.gitlab_project_id,
                    "gitlab_url": project.get_gitlab_url() if project.has_gitlab() else None,
                    "gitlab_token": project.get_gitlab_token() if project.has_gitlab() else None,
                    "github_repo": project.github_repo,
                    "github_token": project.get_github_token() if project.has_github() else None,
                    "github_base_url": project.get_github_base_url() if project.has_github() else None,
                    "mode": pmbot_mode,
                },
                bot_params=bot_params,
            )

        if not project_id:
            return BotResult(
                bot_name=bot_name, status="error",
                summary="pmbot requires project_id or Project with GitLab/GitHub integration",
                data={"error": "missing_project_id"}, markdown_report="",
            )

        return _call_runner(
            pmbot_get_result,
            base_kwargs={
                "project_name": project_id,
                "gitlab_project_id": project_id,
                "mode": pmbot_mode,
            },
            bot_params=bot_params,
        )

    return BotResult(
        bot_name=bot_name, status="error",
        summary=f"Unknown bot: {bot_name}",
        data={"error": "unknown_bot"}, markdown_report="",
    )


# ── Convenience functions ─────────────────────────────────────────────────────

def invoke_gitbot(repo_path: Path | str, max_commits: int = 300) -> BotResult:
    return invoke_bot("gitbot", repo_path=repo_path, max_commits=max_commits)


def invoke_qabot(repo_path: Path | str, max_commits: int = 50) -> BotResult:
    return invoke_bot("qabot", repo_path=repo_path, max_commits=max_commits)


def invoke_pmbot(project_id: str, mode: str = "analyze") -> BotResult:
    return invoke_bot("pmbot", project_id=project_id, pmbot_mode=mode)
