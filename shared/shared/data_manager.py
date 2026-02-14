"""Data management utilities for DevBots projects.

Provides centralized utilities for managing project data storage including
reports, cache, and metadata.
"""

from datetime import datetime
from pathlib import Path
from typing import Literal

BotType = Literal["gitbot", "qabot", "pmbot"]


def get_workspace_root() -> Path:
    """Get the DevBots workspace root directory."""
    # This file is in shared/shared/, so go up 2 levels
    return Path(__file__).parent.parent.parent


def get_data_root() -> Path:
    """Get the root data directory for all projects."""
    return get_workspace_root() / "data"


def get_project_data_dir(project_name: str) -> Path:
    """Get the data directory for a specific project."""
    return get_data_root() / project_name


def get_reports_dir(project_name: str, bot: BotType | None = None) -> Path:
    """
    Get the reports directory for a project.

    Args:
        project_name: Name of the project
        bot: Optional bot type to get specific bot's report directory

    Returns:
        Path to reports directory (or bot-specific subdirectory)
    """
    reports_dir = get_project_data_dir(project_name) / "reports"
    if bot:
        return reports_dir / bot
    return reports_dir


def get_cache_dir(project_name: str) -> Path:
    """Get the cache directory for a project."""
    return get_project_data_dir(project_name) / "cache"


def get_report_path(
    project_name: str,
    bot: BotType,
    variant: Literal["latest", "timestamped"] = "latest",
) -> Path:
    """
    Get the path for a bot report.

    Args:
        project_name: Name of the project
        bot: Bot type (gitbot, qabot, pmbot)
        variant: "latest" for latest.md or "timestamped" for dated file

    Returns:
        Path to the report file
    """
    bot_reports_dir = get_reports_dir(project_name, bot)

    if variant == "latest":
        return bot_reports_dir / "latest.md"
    else:
        # timestamped: 2024-02-14-103045.md
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        return bot_reports_dir / f"{timestamp}.md"


def ensure_project_structure(project_name: str) -> None:
    """
    Ensure the complete data directory structure exists for a project.

    Creates:
    - data/{project_name}/
    - data/{project_name}/reports/{gitbot,qabot,pmbot}/
    - data/{project_name}/cache/
    """
    project_dir = get_project_data_dir(project_name)

    # Create main directories
    project_dir.mkdir(parents=True, exist_ok=True)
    get_cache_dir(project_name).mkdir(parents=True, exist_ok=True)

    # Create bot report directories
    for bot in ["gitbot", "qabot", "pmbot"]:
        get_reports_dir(project_name, bot).mkdir(parents=True, exist_ok=True)  # type: ignore


def save_report(
    project_name: str,
    bot: BotType,
    content: str,
    save_latest: bool = True,
    save_timestamped: bool = True,
) -> tuple[Path, Path | None]:
    """
    Save a bot report to the appropriate location(s).

    Args:
        project_name: Name of the project
        bot: Bot type
        content: Markdown content of the report
        save_latest: Whether to save as latest.md
        save_timestamped: Whether to save timestamped version

    Returns:
        Tuple of (latest_path, timestamped_path)
    """
    ensure_project_structure(project_name)

    latest_path = None
    timestamped_path = None

    if save_latest:
        latest_path = get_report_path(project_name, bot, "latest")
        latest_path.write_text(content, encoding="utf-8")

    if save_timestamped:
        timestamped_path = get_report_path(project_name, bot, "timestamped")
        timestamped_path.write_text(content, encoding="utf-8")

    return (latest_path or Path(), timestamped_path)


def get_cached_file(project_name: str, filename: str) -> Path:
    """
    Get path to a cached file for a project.

    Args:
        project_name: Name of the project
        filename: Name of the cache file

    Returns:
        Path to the cache file
    """
    return get_cache_dir(project_name) / filename


def list_reports(project_name: str, bot: BotType | None = None) -> list[Path]:
    """
    List all report files for a project.

    Args:
        project_name: Name of the project
        bot: Optional bot type to filter reports

    Returns:
        List of report file paths
    """
    reports_dir = get_reports_dir(project_name, bot)

    if not reports_dir.exists():
        return []

    if bot:
        # Return all .md files in bot-specific directory
        return sorted(reports_dir.glob("*.md"), reverse=True)
    else:
        # Return all .md files from all bot directories
        all_reports = []
        for bot_dir in reports_dir.iterdir():
            if bot_dir.is_dir():
                all_reports.extend(bot_dir.glob("*.md"))
        return sorted(all_reports, reverse=True)
