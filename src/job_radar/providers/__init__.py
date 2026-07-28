"""LLM provider abstraction and factory."""

from __future__ import annotations

from ..common.config import Config
from .base import LLMProvider


def get_provider(config: Config) -> LLMProvider:
    """Instantiate the configured LLM provider."""
    provider = config.provider.lower()
    if provider == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider(api_key=config.openai_api_key, model=config.openai_model)
    if provider == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(
            api_key=config.anthropic_api_key, model=config.anthropic_model
        )
    raise ValueError(
        f"Unknown provider '{config.provider}'. Use 'openai' or 'anthropic'."
    )


__all__ = ["LLMProvider", "get_provider"]
