"""Strict AI recipe schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from ..recipes import DIFFICULTIES, PROFILES, STYLES, TARGETS, TERMINAL_FAMILIES, QUALIFIER_FAMILIES, TEMPLATES_BY_DIFFICULTY

ALLOWED_DIFFICULTIES = set(DIFFICULTIES)
ALLOWED_TARGETS = set(TARGETS)
ALLOWED_TEMPLATE_FAMILIES = {template for templates in TEMPLATES_BY_DIFFICULTY.values() for template in templates}
ALLOWED_PROFILES = set(PROFILES)
ALLOWED_STYLES = set(STYLES)
ALLOWED_FAMILIES = set(TERMINAL_FAMILIES) | set(QUALIFIER_FAMILIES) | ALLOWED_TEMPLATE_FAMILIES

REQUIRED_FIELDS = {
    "name",
    "difficulty",
    "target",
    "template_family",
    "theme",
    "story",
    "fake_strings",
    "function_name_style",
    "variable_name_style",
    "hint_levels",
    "complexity",
    "requested_features",
}

OPTIONAL_FIELDS = {
    "profile",
    "style",
    "terminal_commands",
    "artifact_files",
    "family",
    "technique_mix",
    "complexity_budget",
}


@dataclass(frozen=True)
class AIRecipe:
    name: str
    difficulty: str
    target: str
    template_family: str
    theme: str
    story: str
    fake_strings: list[str]
    function_name_style: str
    variable_name_style: str
    hint_levels: list[str]
    complexity: int
    requested_features: list[str]
    profile: str = "standard"
    style: str = "simple"
    terminal_commands: list[str] | None = None
    artifact_files: list[str] | None = None
    family: str = ""
    technique_mix: list[str] | None = None
    complexity_budget: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
