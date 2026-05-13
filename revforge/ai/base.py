"""Provider base classes and configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


class AIProviderError(RuntimeError):
    """Base provider error."""


class AIProviderNotConfigured(AIProviderError):
    """Raised when a provider is selected without required configuration."""


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    configured: bool = False
    detail: str = ""

    @property
    def masked_key(self) -> str:
        return mask_secret(self.api_key)


def env_first(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def mask_secret(value: str | None) -> str:
    if not value:
        return "missing"
    if len(value) <= 8:
        return value[:2] + "..." + value[-2:]
    return value[:3] + "..." + value[-4:]


class AIProvider:
    name = "base"

    def config(self) -> ProviderConfig:
        raise NotImplementedError

    def require_configured(self) -> ProviderConfig:
        config = self.config()
        if not config.configured:
            raise AIProviderNotConfigured(f"{config.name} provider is not configured: {config.detail}")
        return config

    def generate_recipe(self, request: dict[str, Any]) -> str:
        raise NotImplementedError

    def generate_hints(self, context: dict[str, Any], levels: int) -> str:
        raise NotImplementedError

    def generate_review(self, context: dict[str, Any]) -> str:
        raise NotImplementedError

    def generate_writeup(self, context: dict[str, Any]) -> str:
        raise NotImplementedError

