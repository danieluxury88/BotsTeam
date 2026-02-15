"""Shared configuration and environment loading."""

import os
from pathlib import Path

from dotenv import load_dotenv


def load_env() -> None:
    """Load environment variables from .env file in workspace root."""
    load_dotenv()


def get_anthropic_api_key() -> str:
    """Get Anthropic API key from environment."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY is not set. "
            "Copy .env.example to .env and add your key."
        )
    return api_key


def get_default_model() -> str:
    """Get default Claude model from environment or return default."""
    return os.environ.get("GITBOT_MODEL", "claude-haiku-4-5-20251001")


class Config:
    """Configuration accessor for all bots."""

    @staticmethod
    def gitlab_token() -> str:
        """Get GitLab private token from environment."""
        token = os.environ.get("GITLAB_PRIVATE_TOKEN")
        if not token:
            raise EnvironmentError(
                "GITLAB_PRIVATE_TOKEN is not set. "
                "Add it to your .env file."
            )
        return token

    @staticmethod
    def gitlab_url() -> str:
        """Get GitLab URL from environment."""
        return os.environ.get("GITLAB_URL", "https://gitlab.com")

    @staticmethod
    def gitlab_project_id() -> str | None:
        """Get default GitLab project ID from environment."""
        return os.environ.get("GITLAB_PROJECT_ID")

    @staticmethod
    def github_token() -> str:
        """Get GitHub personal access token from environment."""
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise EnvironmentError(
                "GITHUB_TOKEN is not set. "
                "Add it to your .env file."
            )
        return token

    @staticmethod
    def github_base_url() -> str:
        """Get GitHub API base URL from environment (for GitHub Enterprise)."""
        return os.environ.get("GITHUB_API_URL", "https://api.github.com")
