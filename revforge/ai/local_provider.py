"""Local provider placeholder."""

from __future__ import annotations

from .base import AIProvider, AIProviderNotConfigured, ProviderConfig, env_first
from .openai_provider import OpenAICompatibleProvider


class LocalProvider(AIProvider):
    name = "local"

    def __init__(self) -> None:
        self._base_url = env_first("REVFORGE_LOCAL_BASE_URL")
        self._model = env_first("REVFORGE_LOCAL_MODEL") or "local-model"
        self._delegate = (
            OpenAICompatibleProvider(
                name="local",
                api_key="local",
                model=self._model,
                base_url=self._base_url,
                detail_when_missing="set REVFORGE_LOCAL_BASE_URL for local OpenAI-compatible servers",
            )
            if self._base_url
            else None
        )

    def config(self) -> ProviderConfig:
        if self._delegate:
            return self._delegate.config()
        return ProviderConfig(
            name=self.name,
            model=self._model,
            base_url=None,
            api_key=None,
            configured=False,
            detail="local provider placeholder; set REVFORGE_LOCAL_BASE_URL for compatible local servers",
        )

    def generate_recipe(self, request):
        if not self._delegate:
            raise AIProviderNotConfigured(self.config().detail)
        return self._delegate.generate_recipe(request)

    def generate_hints(self, context, levels: int):
        if not self._delegate:
            raise AIProviderNotConfigured(self.config().detail)
        return self._delegate.generate_hints(context, levels)

    def generate_review(self, context):
        if not self._delegate:
            raise AIProviderNotConfigured(self.config().detail)
        return self._delegate.generate_review(context)

    def generate_writeup(self, context):
        if not self._delegate:
            raise AIProviderNotConfigured(self.config().detail)
        return self._delegate.generate_writeup(context)

