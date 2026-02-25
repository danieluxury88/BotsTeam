"""Shared utilities for devbots monorepo."""

__version__ = "0.1.0"

# Bot registry — single source of truth for bot metadata
from shared.bot_registry import BOTS as BOT_REGISTRY, BotMeta, BotScope, all_bots, personal_bots, team_bots

# Export data management utilities
from shared.data_manager import (
    ensure_project_structure,
    get_cache_dir,
    get_cached_file,
    get_data_root,
    get_personal_registry_path,
    get_personal_root,
    get_project_data_dir,
    get_registry_path,
    get_report_path,
    get_reports_dir,
    list_reports,
    save_report,
)

__all__ = [
    # bot_registry
    "BOT_REGISTRY",
    "BotMeta",
    "BotScope",
    "all_bots",
    "personal_bots",
    "team_bots",
    # data_manager
    "ensure_project_structure",
    "get_cache_dir",
    "get_cached_file",
    "get_data_root",
    "get_personal_registry_path",
    "get_personal_root",
    "get_project_data_dir",
    "get_registry_path",
    "get_report_path",
    "get_reports_dir",
    "list_reports",
    "save_report",
]
