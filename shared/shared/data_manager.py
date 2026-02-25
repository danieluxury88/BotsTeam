"""Data management utilities for DevBots projects.

Provides centralized utilities for managing project data storage including
reports, cache, and metadata. Supports both team and personal project scopes.
"""

from datetime import datetime
from pathlib import Path
from typing import Literal

from shared.models import ProjectScope

BotType = Literal["gitbot", "qabot", "pmbot", "journalbot", "taskbot", "habitbot", "orchestrator"]


def get_workspace_root() -> Path:
    """Get the DevBots workspace root directory."""
    # This file is in shared/shared/, so go up 2 levels
    return Path(__file__).parent.parent.parent


def get_data_root() -> Path:
    """Get the root data directory for all projects."""
    return get_workspace_root() / "data"


def get_personal_root() -> Path:
    """Get the root data directory for personal projects (data/personal/)."""
    return get_data_root() / "personal"


def get_registry_path() -> Path:
    """Get the path to the team project registry (data/projects.json)."""
    return get_data_root() / "projects.json"


def get_personal_registry_path() -> Path:
    """Get the path to the personal project registry (data/personal/projects.json)."""
    return get_personal_root() / "projects.json"


def get_project_data_dir(
    project_name: str,
    scope: ProjectScope = ProjectScope.TEAM,
) -> Path:
    """
    Get the data directory for a specific project.

    Team:     data/{project_name}/
    Personal: data/personal/{project_name}/
    """
    if scope == ProjectScope.PERSONAL:
        return get_personal_root() / project_name
    return get_data_root() / project_name


def get_reports_dir(
    project_name: str,
    bot: BotType | None = None,
    scope: ProjectScope = ProjectScope.TEAM,
) -> Path:
    """
    Get the reports directory for a project.

    Args:
        project_name: Name of the project
        bot: Optional bot name to get the bot-specific subdirectory
        scope: Team or personal context
    """
    reports_dir = get_project_data_dir(project_name, scope) / "reports"
    if bot:
        return reports_dir / bot
    return reports_dir


def get_cache_dir(
    project_name: str,
    scope: ProjectScope = ProjectScope.TEAM,
) -> Path:
    """Get the cache directory for a project."""
    return get_project_data_dir(project_name, scope) / "cache"


def get_report_path(
    project_name: str,
    bot: BotType,
    variant: Literal["latest", "timestamped"] = "latest",
    scope: ProjectScope = ProjectScope.TEAM,
) -> Path:
    """
    Get the path for a bot report.

    Args:
        project_name: Name of the project
        bot: Bot name
        variant: "latest" for latest.md or "timestamped" for dated file
        scope: Team or personal context
    """
    bot_reports_dir = get_reports_dir(project_name, bot, scope)

    if variant == "latest":
        return bot_reports_dir / "latest.md"
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        return bot_reports_dir / f"{timestamp}.md"


def ensure_project_structure(
    project_name: str,
    scope: ProjectScope = ProjectScope.TEAM,
    bots: list[str] | None = None,
) -> None:
    """
    Ensure the complete data directory structure exists for a project.

    Args:
        project_name: Name of the project
        scope: Team or personal context (determines data root)
        bots: Bot names to create report directories for (defaults to all known bots)
    """
    project_dir = get_project_data_dir(project_name, scope)
    project_dir.mkdir(parents=True, exist_ok=True)
    get_cache_dir(project_name, scope).mkdir(parents=True, exist_ok=True)

    default_bots = bots or ["gitbot", "qabot", "pmbot", "journalbot", "taskbot", "habitbot", "orchestrator"]
    for bot in default_bots:
        get_reports_dir(project_name, bot, scope).mkdir(parents=True, exist_ok=True)  # type: ignore


def save_report(
    project_name: str,
    bot: BotType,
    content: str,
    scope: ProjectScope = ProjectScope.TEAM,
    save_latest: bool = True,
    save_timestamped: bool = True,
) -> tuple[Path, Path | None]:
    """
    Save a bot report to the appropriate location(s).

    Args:
        project_name: Name of the project
        bot: Bot name
        content: Markdown content of the report
        scope: Team or personal context
        save_latest: Whether to save as latest.md
        save_timestamped: Whether to save timestamped version

    Returns:
        Tuple of (latest_path, timestamped_path)
    """
    ensure_project_structure(project_name, scope, bots=[bot])

    latest_path = None
    timestamped_path = None

    if save_latest:
        latest_path = get_report_path(project_name, bot, "latest", scope)
        latest_path.write_text(content, encoding="utf-8")

    if save_timestamped:
        timestamped_path = get_report_path(project_name, bot, "timestamped", scope)
        timestamped_path.write_text(content, encoding="utf-8")

    return (latest_path or Path(), timestamped_path)


def get_cached_file(
    project_name: str,
    filename: str,
    scope: ProjectScope = ProjectScope.TEAM,
) -> Path:
    """Get path to a cached file for a project."""
    return get_cache_dir(project_name, scope) / filename


def list_reports(
    project_name: str,
    bot: BotType | None = None,
    scope: ProjectScope = ProjectScope.TEAM,
) -> list[Path]:
    """
    List all report files for a project.

    Args:
        project_name: Name of the project
        bot: Optional bot name to filter reports
        scope: Team or personal context

    Returns:
        List of report file paths sorted newest first
    """
    reports_dir = get_reports_dir(project_name, bot, scope)

    if not reports_dir.exists():
        return []

    if bot:
        return sorted(reports_dir.glob("*.md"), reverse=True)
    else:
        all_reports = []
        for bot_dir in reports_dir.iterdir():
            if bot_dir.is_dir():
                all_reports.extend(bot_dir.glob("*.md"))
        return sorted(all_reports, reverse=True)
