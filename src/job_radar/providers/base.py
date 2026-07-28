"""Provider abstraction for LLM calls.

No OpenAI- or Anthropic-specific code lives outside the ``providers`` package.
Every provider exposes a single method: turn a system + user prompt into a
parsed JSON object.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any


class LLMProvider(ABC):
    """Base class for all LLM providers."""

    @abstractmethod
    def complete_json(self, *, system: str, user: str, max_tokens: int = 4096) -> dict[str, Any]:
        """Send a prompt and return the parsed JSON object the model produced."""

    @staticmethod
    def parse_json(text: str) -> dict[str, Any]:
        """Best-effort JSON extraction from a model response.

        Handles bare JSON, fenced ```json blocks, and leading/trailing prose.
        """
        text = text.strip()
        if not text:
            raise ValueError("empty model response")

        fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Fall back to the first balanced {...} span.
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(text[start : end + 1])
            raise
