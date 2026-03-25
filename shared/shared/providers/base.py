"""Abstract base class for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Common interface for all LLM providers."""

    @abstractmethod
    def chat(self, system: str, user: str, max_tokens: int, model: str) -> str:
        """Send a single-turn message and return the text response."""
        ...
