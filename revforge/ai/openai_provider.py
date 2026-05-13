"""OpenAI and OpenAI-compatible provider implementations."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from .base import AIProvider, AIProviderError, ProviderConfig, env_first
from .prompts import hints_prompt, provider_system_prompt, recipe_user_prompt, review_prompt, writeup_prompt


class OpenAICompatibleProvider(AIProvider):
    name = "custom"

    def __init__(
        self,
        *,
        name: str,
        api_key: str | None,
        model: str | None,
        base_url: str | None,
        detail_when_missing: str,
    ) -> None:
        self.name = name
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/") if base_url else None
        self._detail_when_missing = detail_when_missing

    def config(self) -> ProviderConfig:
        configured = bool(self._api_key and self._model and self._base_url)
        return ProviderConfig(
            name=self.name,
            model=self._model,
            base_url=self._base_url,
            api_key=self._api_key,
            configured=configured,
            detail="configured" if configured else self._detail_when_missing,
        )

    def generate_recipe(self, request: dict[str, Any]) -> str:
        return self._complete(
            provider_system_prompt(),
            recipe_user_prompt(
                name=request["name"],
                difficulty=request["difficulty"],
                target=request["target"],
                theme=request["theme"],
            ),
            json_mode=True,
        )

    def generate_hints(self, context: dict[str, Any], levels: int) -> str:
        return self._complete(provider_system_prompt(), hints_prompt(context, levels), json_mode=False)

    def generate_review(self, context: dict[str, Any]) -> str:
        return self._complete(provider_system_prompt(), review_prompt(context), json_mode=False)

    def generate_writeup(self, context: dict[str, Any]) -> str:
        return self._complete(provider_system_prompt(), writeup_prompt(context), json_mode=False)

    def _complete(self, system: str, user: str, *, json_mode: bool) -> str:
        config = self.require_configured()
        payload: dict[str, Any] = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.3,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            f"{config.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {config.api_key}",
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
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"{self.name} response did not contain message content") from exc


class OpenAIProvider(OpenAICompatibleProvider):
    name = "openai"

    def __init__(self) -> None:
        super().__init__(
            name="openai",
            api_key=env_first("REVFORGE_OPENAI_API_KEY", "OPENAI_API_KEY"),
            model=env_first("REVFORGE_OPENAI_MODEL") or "gpt-5.1",
            base_url=env_first("REVFORGE_OPENAI_BASE_URL") or "https://api.openai.com/v1",
            detail_when_missing="missing REVFORGE_OPENAI_API_KEY",
        )


class CustomOpenAIProvider(OpenAICompatibleProvider):
    name = "custom"

    def __init__(self) -> None:
        super().__init__(
            name="custom",
            api_key=env_first("REVFORGE_AI_API_KEY"),
            model=env_first("REVFORGE_AI_MODEL"),
            base_url=env_first("REVFORGE_AI_BASE_URL"),
            detail_when_missing="requires REVFORGE_AI_BASE_URL, REVFORGE_AI_API_KEY, and REVFORGE_AI_MODEL",
        )
