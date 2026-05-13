"""Anthropic provider implementation."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .base import AIProvider, AIProviderError, ProviderConfig, env_first
from .prompts import hints_prompt, provider_system_prompt, recipe_user_prompt, review_prompt, writeup_prompt


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def __init__(self) -> None:
        self._api_key = env_first("REVFORGE_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")
        self._model = env_first("REVFORGE_ANTHROPIC_MODEL") or "claude-sonnet-4-6"
        self._base_url = "https://api.anthropic.com/v1"

    def config(self) -> ProviderConfig:
        configured = bool(self._api_key and self._model)
        return ProviderConfig(
            name=self.name,
            model=self._model,
            base_url=self._base_url,
            api_key=self._api_key,
            configured=configured,
            detail="configured" if configured else "missing REVFORGE_ANTHROPIC_API_KEY",
        )

    def generate_recipe(self, request: dict[str, Any]) -> str:
        return self._complete(
            recipe_user_prompt(
                name=request["name"],
                difficulty=request["difficulty"],
                target=request["target"],
                theme=request["theme"],
            )
        )

    def generate_hints(self, context: dict[str, Any], levels: int) -> str:
        return self._complete(hints_prompt(context, levels))

    def generate_review(self, context: dict[str, Any]) -> str:
        return self._complete(review_prompt(context))

    def generate_writeup(self, context: dict[str, Any]) -> str:
        return self._complete(writeup_prompt(context))

    def _complete(self, user: str) -> str:
        config = self.require_configured()
        payload = {
            "model": config.model,
            "max_tokens": 1800,
            "temperature": 0.3,
            "system": provider_system_prompt(),
            "messages": [{"role": "user", "content": user}],
        }
        request = urllib.request.Request(
            f"{config.base_url}/messages",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-api-key": str(config.api_key),
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AIProviderError(f"{self.name} request failed: {exc}") from exc
        try:
            return "".join(part.get("text", "") for part in data["content"])
        except (KeyError, TypeError) as exc:
            raise AIProviderError(f"{self.name} response did not contain text content") from exc
