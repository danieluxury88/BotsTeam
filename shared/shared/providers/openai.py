"""OpenAI-compatible provider — works with OpenAI, Groq, Mistral, Ollama, and any OpenAI-compatible API."""

from __future__ import annotations

import logging

from shared.config import get_openai_api_key, get_openai_base_url
from shared.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """LLM provider backed by any OpenAI-compatible API."""

    def __init__(self) -> None:
        try:
            import openai
        except ImportError as exc:
            raise ImportError(
                "The openai package is required for the OpenAI provider. "
                "Install it with: uv add openai"
            ) from exc

        api_key = get_openai_api_key()
        base_url = get_openai_base_url()
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, system: str, user: str, max_tokens: int, model: str) -> str:
        response = self._client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content
