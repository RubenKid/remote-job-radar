"""OpenAI provider (default)."""

from __future__ import annotations

from typing import Any

from openai import OpenAI

from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    """Generate structured JSON via the OpenAI Chat Completions API."""

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def complete_json(self, *, system: str, user: str, max_tokens: int = 4096) -> dict[str, Any]:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content or ""
        return self.parse_json(content)
