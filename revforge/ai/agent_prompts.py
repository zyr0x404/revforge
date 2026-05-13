"""Offline prompts for coding-agent handoff."""

from __future__ import annotations

from ..recipes import QUALIFIER_FAMILIES, TERMINAL_FAMILIES, TEMPLATES_BY_DIFFICULTY


def build_agent_prompt(*, agent: str, name: str, difficulty: str, theme: str, profile: str = "standard") -> str:
    return f"""You are helping maintain RevForge, a safe reverse engineering CTF challenge generator.

Target agent: {agent}
Challenge idea: {name}
Difficulty: {difficulty}
Profile: {profile}
Theme: {theme}

Modify RevForge safely:
- AI must produce structured JSON recipes only.
- Do not generate arbitrary executable C, C++, Java, Android, shell, or build-system code from AI output.
- Validate every recipe before using it.
- Use RevForge's internal safe templates and builders for generated source and binaries.
- Preserve deterministic seeds and local recipe history.
- Generated challenge binaries may only read local challenge artifacts and user-provided input.
- No malware, persistence, credential collection, network callbacks, destructive behavior, privilege escalation, evasion, or real exploitation.
- No identity, affiliation, location, or real-world institution references.

Allowed template families:
{TEMPLATES_BY_DIFFICULTY}

Allowed terminal families:
{TERMINAL_FAMILIES + QUALIFIER_FAMILIES}

Expected output from AI providers must be JSON with:
name, difficulty, target, template_family, theme, story, fake_strings, function_name_style,
variable_name_style, hint_levels, complexity, requested_features, profile, style,
terminal_commands, artifact_files, family, technique_mix, complexity_budget.
"""
