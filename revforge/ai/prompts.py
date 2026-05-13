"""Prompts for structured AI recipe and guidance generation."""

from __future__ import annotations

import json
from typing import Any

from ..recipes import QUALIFIER_FAMILIES, TERMINAL_FAMILIES, TEMPLATES_BY_DIFFICULTY


def provider_system_prompt() -> str:
    return (
        "You generate safe reverse engineering CTF challenge recipes only. "
        "Output valid JSON only. Do not output executable code. "
        "Do not include malware behavior. Do not include real-world exploitation. "
        "Do not include identity, affiliation, location, or real-world institution references."
    )


def recipe_user_prompt(*, name: str, difficulty: str, target: str, theme: str) -> str:
    schema = {
        "name": name,
        "difficulty": difficulty,
        "target": target,
        "template_family": "one allowed template for the requested difficulty",
        "theme": theme,
        "story": "short generic fictional CTF story",
        "fake_strings": ["short harmless decoy string"],
        "function_name_style": "short style description",
        "variable_name_style": "short style description",
        "hint_levels": ["progressive hint 1", "progressive hint 2", "progressive hint 3"],
        "complexity": 1,
        "requested_features": ["safe local validation feature"],
        "profile": "training, standard, qualifier, or finals",
        "style": "simple or terminal",
        "terminal_commands": ["--help", "verify"],
        "artifact_files": ["local-artifact.bin"],
        "family": "one allowed terminal family when style is terminal",
        "technique_mix": ["encoded constants"],
        "complexity_budget": 6,
    }
    return (
        "Create one safe RevForge AI recipe for the requested challenge. "
        "Use only these templates by difficulty: "
        f"{json.dumps(TEMPLATES_BY_DIFFICULTY, sort_keys=True)}. "
        "Allowed terminal families are: "
        f"{json.dumps(list(TERMINAL_FAMILIES + QUALIFIER_FAMILIES))}. "
        "Do not include code. Do not request networking, persistence, credential collection, destructive behavior, "
        "privilege escalation, evasion, exploitation, real targets, or real-world identity references. "
        "Return a JSON object with exactly this shape, filling in useful values: "
        f"{json.dumps(schema, sort_keys=True)}"
    )


def hints_prompt(context: dict[str, Any], levels: int) -> str:
    return (
        f"Generate {levels} progressive hints for this safe CTF reverse engineering challenge. "
        "Do not reveal the flag or final answer. Keep each hint concise. "
        "Return Markdown only.\n\n"
        f"Context:\n{json.dumps(context, indent=2, sort_keys=True)}"
    )


def review_prompt(context: dict[str, Any]) -> str:
    return (
        "Review this safe CTF reverse engineering challenge for realism, difficulty, flag leakage, solve path, "
        "and quality. Return Markdown with a score from 0 to 100 and concrete warnings if it is too toy-like.\n\n"
        f"Context:\n{json.dumps(context, indent=2, sort_keys=True)}"
    )


def writeup_prompt(context: dict[str, Any]) -> str:
    return (
        "Write a clean educational training writeup for this safe reverse engineering challenge. "
        "Explain the intended reversing path and solver logic. Return Markdown only.\n\n"
        f"Context:\n{json.dumps(context, indent=2, sort_keys=True)}"
    )
