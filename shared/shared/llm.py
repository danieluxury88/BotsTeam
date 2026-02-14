"""Shared Claude/Anthropic client factory."""

import anthropic

from shared.config import get_anthropic_api_key


def create_client() -> anthropic.Anthropic:
    """Create and return an Anthropic API client."""
    api_key = get_anthropic_api_key()
    return anthropic.Anthropic(api_key=api_key)
