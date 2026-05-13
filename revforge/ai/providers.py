"""Provider registry and configuration reporting."""

from __future__ import annotations

import os

from .anthropic_provider import AnthropicProvider
from .base import AIProvider, ProviderConfig
from .gemini_provider import GeminiProvider
from .local_provider import LocalProvider
from .openai_provider import CustomOpenAIProvider, OpenAIProvider

PROVIDER_NAMES = ("openai", "anthropic", "gemini", "custom", "local")


def get_provider(name: str | None = None) -> AIProvider:
    selected = (name or os.environ.get("REVFORGE_AI_PROVIDER") or "openai").strip().lower()
    if selected == "openai":
        return OpenAIProvider()
    if selected in {"anthropic", "claude"}:
        return AnthropicProvider()
    if selected == "gemini":
        return GeminiProvider()
    if selected in {"custom", "openai-compatible"}:
        return CustomOpenAIProvider()
    if selected == "local":
        return LocalProvider()
    raise ValueError(f"unknown AI provider: {selected}")


def provider_configs() -> list[ProviderConfig]:
    return [get_provider(name).config() for name in PROVIDER_NAMES]

