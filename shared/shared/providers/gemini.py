"""Google Gemini provider — uses the google-genai SDK."""

from __future__ import annotations

import logging

from shared.config import get_gemini_api_key
from shared.providers.base import LLMProvider

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """LLM provider backed by Google Gemini."""

    def __init__(self) -> None:
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as exc:
            raise ImportError(
                "The google-genai package is required for the Gemini provider. "
                "Install it with: uv add google-genai"
            ) from exc

        self._genai = genai
        self._types = genai_types
        self._client = genai.Client(api_key=get_gemini_api_key())

    def chat(self, system: str, user: str, max_tokens: int, model: str) -> str:
        response = self._client.models.generate_content(
            model=model,
            contents=user,
            config=self._types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=max_tokens,
            ),
        )
        return response.text
