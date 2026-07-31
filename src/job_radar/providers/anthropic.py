"""Anthropic (Claude) provider — optional alternative to OpenAI.

Uses the official ``anthropic`` SDK. Defaults to Claude Opus 4.8 with adaptive
thinking. Install the optional dependency with ``pip install -e '.[anthropic]'``.
"""

from __future__ import annotations

from typing import Any

from .base import LLMProvider

_JSON_GUARD = (
    "\n\nRespond with a single valid JSON object and nothing else. "
    "Do not wrap it in markdown fences or add commentary."
)


class AnthropicProvider(LLMProvider):
    """Generate structured JSON via the Anthropic Messages API."""

    def __init__(self, api_key: str, model: str = "claude-opus-4-8") -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "The 'anthropic' package is required for the Anthropic provider. "
                "Install it with: pip install -e '.[anthropic]'"
            ) from exc
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete_json(self, *, system: str, user: str, max_tokens: int = 4096) -> dict[str, Any]:
        # No `thinking` param: it's unnecessary for structured JSON extraction and
        # adaptive thinking isn't supported on Haiku (our default cheap model).
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system + _JSON_GUARD,
            messages=[{"role": "user", "content": user}],
        )
        text = next(
            (block.text for block in response.content if block.type == "text"),
            "",
        )
        return self.parse_json(text)

    def complete_text(self, *, system: str, user: str, max_tokens: int = 1024) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return next(
            (block.text for block in response.content if block.type == "text"), ""
        )
