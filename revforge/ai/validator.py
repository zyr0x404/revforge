"""Validation and safety checks for AI-produced recipes."""

from __future__ import annotations

import json
import re
from typing import Any

from ..recipes import TEMPLATES_BY_DIFFICULTY, template_difficulty
from ..utils import slugify_name
from .schema import (
    AIRecipe,
    ALLOWED_DIFFICULTIES,
    ALLOWED_FAMILIES,
    ALLOWED_PROFILES,
    ALLOWED_STYLES,
    ALLOWED_TARGETS,
    ALLOWED_TEMPLATE_FAMILIES,
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
)


class AIRecipeValidationError(ValueError):
    """Raised when provider output is not a safe RevForge AI recipe."""


IDENTITY_TERMS = [
    "Koso" + "vo",
    "S" + "HC",
    "KO" + "SCTF",
    "scho" + "ol",
    "te" + "am",
    "coun" + "try",
    "person" + "al identifier",
]

UNSAFE_TERMS = [
    "networking",
    "network callback",
    "socket",
    "reverse shell",
    "persistence",
    "credential theft",
    "credential collection",
    "browser cookies",
    "tokens",
    "password stealing",
    "privilege escalation",
    "destructive file",
    "ransomware",
    "malware",
    "antivirus evasion",
    "real exploitation",
    "real target",
    "real targets",
    "exploit chain",
    "exfiltration",
    "keylogger",
    "stealth",
    "institution",
    "university",
    "agency",
    "bank",
    *IDENTITY_TERMS,
]


def validate_ai_recipe_json(
    raw: str | dict[str, Any],
    *,
    expected_name: str | None = None,
    expected_difficulty: str | None = None,
    expected_target: str | None = None,
) -> AIRecipe:
    data = raw if isinstance(raw, dict) else _parse_json_object(raw)
    if not isinstance(data, dict):
        raise AIRecipeValidationError("AI output must be a JSON object")

    extra = set(data) - (REQUIRED_FIELDS | OPTIONAL_FIELDS)
    missing = REQUIRED_FIELDS - set(data)
    if extra:
        raise AIRecipeValidationError(f"unexpected AI recipe fields: {', '.join(sorted(extra))}")
    if missing:
        raise AIRecipeValidationError(f"missing AI recipe fields: {', '.join(sorted(missing))}")

    _reject_unsafe(data)

    name = _string(data["name"], "name", 64)
    safe_name = slugify_name(name)
    difficulty = _string(data["difficulty"], "difficulty", 32).replace("_", "-")
    if difficulty == "superhard":
        difficulty = "super-hard"
    target = _string(data["target"], "target", 32).lower()
    template_family = _string(data["template_family"], "template_family", 64)
    theme = _string(data["theme"], "theme", 120)
    story = _string(data["story"], "story", 500)
    fake_strings = _string_list(data["fake_strings"], "fake_strings", 8, 80)
    function_name_style = _string(data["function_name_style"], "function_name_style", 80)
    variable_name_style = _string(data["variable_name_style"], "variable_name_style", 80)
    hint_levels = _string_list(data["hint_levels"], "hint_levels", 6, 240)
    complexity = _int(data["complexity"], "complexity", 1, 10)
    requested_features = _string_list(data["requested_features"], "requested_features", 12, 120)
    profile = _string(data.get("profile", "standard"), "profile", 32).replace("_", "-")
    style = _string(data.get("style", "simple"), "style", 32).replace("_", "-")
    terminal_commands = _string_list(data.get("terminal_commands", []), "terminal_commands", 12, 40)
    artifact_files = _string_list(data.get("artifact_files", []), "artifact_files", 4, 80)
    family = _string(data.get("family", template_family), "family", 80)
    technique_mix = _string_list(data.get("technique_mix", []), "technique_mix", 8, 80)
    complexity_budget = _int(data.get("complexity_budget", complexity), "complexity_budget", 1, 10)

    if difficulty not in ALLOWED_DIFFICULTIES:
        raise AIRecipeValidationError(f"unsupported difficulty: {difficulty}")
    if target not in ALLOWED_TARGETS:
        raise AIRecipeValidationError(f"unsupported target: {target}")
    if template_family not in ALLOWED_TEMPLATE_FAMILIES:
        raise AIRecipeValidationError(f"unsupported template family: {template_family}")
    if profile not in ALLOWED_PROFILES:
        raise AIRecipeValidationError(f"unsupported profile: {profile}")
    if style not in ALLOWED_STYLES:
        raise AIRecipeValidationError(f"unsupported style: {style}")
    if family not in ALLOWED_FAMILIES:
        raise AIRecipeValidationError(f"unsupported family: {family}")
    owner = template_difficulty(template_family)
    if owner != difficulty and template_family not in TEMPLATES_BY_DIFFICULTY[difficulty]:
        raise AIRecipeValidationError(f"template {template_family} belongs to {owner}, not {difficulty}")

    if expected_name is not None and safe_name != slugify_name(expected_name):
        raise AIRecipeValidationError("AI recipe name does not match requested challenge name")
    if expected_difficulty is not None and difficulty != expected_difficulty:
        raise AIRecipeValidationError("AI recipe difficulty does not match request")
    if expected_target is not None and target != expected_target:
        raise AIRecipeValidationError("AI recipe target does not match request")

    return AIRecipe(
        name=safe_name,
        difficulty=difficulty,
        target=target,
        template_family=template_family,
        theme=theme,
        story=story,
        fake_strings=fake_strings,
        function_name_style=function_name_style,
        variable_name_style=variable_name_style,
        hint_levels=hint_levels,
        complexity=complexity,
        requested_features=requested_features,
        profile=profile,
        style=style,
        terminal_commands=terminal_commands,
        artifact_files=artifact_files,
        family=family,
        technique_mix=technique_mix,
        complexity_budget=complexity_budget,
    )


def _parse_json_object(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AIRecipeValidationError("AI output must be valid JSON only") from exc
    if not isinstance(value, dict):
        raise AIRecipeValidationError("AI output must be a JSON object")
    return value


def _reject_unsafe(data: Any) -> None:
    text = json.dumps(data, sort_keys=True).lower()
    for term in UNSAFE_TERMS:
        if term.lower() in text:
            raise AIRecipeValidationError(f"unsafe or disallowed recipe content: {term}")
    if re.search(r"\b(api[_ -]?key|secret[_ -]?key|access[_ -]?token)\b", text):
        raise AIRecipeValidationError("AI recipe must not contain keys or secrets")


def _string(value: Any, field: str, max_len: int) -> str:
    if not isinstance(value, str):
        raise AIRecipeValidationError(f"{field} must be a string")
    cleaned = value.strip()
    if not cleaned:
        raise AIRecipeValidationError(f"{field} cannot be empty")
    if len(cleaned) > max_len:
        raise AIRecipeValidationError(f"{field} is too long")
    return cleaned


def _string_list(value: Any, field: str, max_items: int, max_item_len: int) -> list[str]:
    if not isinstance(value, list):
        raise AIRecipeValidationError(f"{field} must be a list")
    if len(value) > max_items:
        raise AIRecipeValidationError(f"{field} has too many items")
    return [_string(item, f"{field} item", max_item_len) for item in value]


def _int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int):
        raise AIRecipeValidationError(f"{field} must be an integer")
    if value < minimum or value > maximum:
        raise AIRecipeValidationError(f"{field} must be between {minimum} and {maximum}")
    return value
