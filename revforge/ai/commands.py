"""High-level AI command helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..generator import generate_challenge, load_metadata
from ..quality import audit_challenge
from ..utils import json_dump
from . import providers
from .agent_prompts import build_agent_prompt
from .schema import AIRecipe
from .validator import validate_ai_recipe_json


def ai_new(
    *,
    provider_name: str,
    name: str,
    difficulty: str,
    target: str,
    theme: str,
    out_dir: str,
    seed: str | None,
    competition_mode: bool,
    allow_repeat: bool,
) -> tuple[Path, AIRecipe]:
    provider = providers.get_provider(provider_name)
    raw = provider.generate_recipe({"name": name, "difficulty": difficulty, "target": target, "theme": theme})
    recipe = validate_ai_recipe_json(raw, expected_name=name, expected_difficulty=difficulty, expected_target=target)
    terminal_family = recipe.family if recipe.style == "terminal" and (recipe.family.startswith("terminal_") or recipe.family.startswith("qualifier_")) else None
    result = generate_challenge(
        name=recipe.name,
        difficulty=recipe.difficulty,
        target=recipe.target,
        template=None if terminal_family else recipe.template_family,
        family=terminal_family,
        out_dir=out_dir,
        seed=seed,
        competition_mode=competition_mode,
        allow_repeat=allow_repeat,
        profile=recipe.profile,
        style=recipe.style,
        ai_recipe=recipe.to_dict(),
    )
    if not competition_mode:
        json_dump(result.challenge_dir / "ai_recipe.json", recipe.to_dict())
    return result.challenge_dir, recipe


def ai_hints(challenge_dir: str | Path, *, provider_name: str, levels: int) -> Path:
    path = Path(challenge_dir)
    metadata = load_metadata(path)
    context = _safe_context(path)
    text = providers.get_provider(provider_name).generate_hints(context, levels)
    text = _redact_flag(text, metadata.get("flag"))
    out = path / "hints.md"
    out.write_text(text.rstrip() + "\n", encoding="utf-8")
    return out


def ai_review(challenge_dir: str | Path, *, provider_name: str) -> str:
    path = Path(challenge_dir)
    context = _safe_context(path)
    audit = audit_challenge(path)
    context["audit"] = audit.to_dict()
    text = providers.get_provider(provider_name).generate_review(context)
    if not re.search(r"\bscore\b", text, flags=re.IGNORECASE):
        text = f"Score: {audit.quality_score}/100\n\n{text}"
    return text.rstrip()


def ai_writeup(challenge_dir: str | Path, *, provider_name: str, force: bool = False) -> Path:
    path = Path(challenge_dir)
    metadata = load_metadata(path)
    if metadata.get("competition_mode") and not force:
        raise ValueError("ai-writeup is training-mode only unless --force is used")
    context = _training_context(path)
    text = providers.get_provider(provider_name).generate_writeup(context)
    out = path / "ai_writeup.md"
    out.write_text(text.rstrip() + "\n", encoding="utf-8")
    return out


def agent_prompt(*, agent: str, name: str, difficulty: str, theme: str, profile: str = "standard") -> str:
    return build_agent_prompt(agent=agent, name=name, difficulty=difficulty, profile=profile, theme=theme)


def _safe_context(path: Path) -> dict[str, Any]:
    metadata = load_metadata(path)
    metadata = {key: value for key, value in metadata.items() if key != "flag"}
    context: dict[str, Any] = {"metadata": metadata}
    recipe_path = path / "recipe.json"
    if recipe_path.exists():
        recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
        context["recipe"] = {
            "difficulty": recipe.get("difficulty"),
            "target": recipe.get("target"),
            "template_family": recipe.get("template_family"),
            "encoding_chain": recipe.get("encoding_chain", []),
            "checker_type": recipe.get("checker_type"),
            "fake_strings": recipe.get("fake_strings", []),
            "transformations": recipe.get("transformations", []),
            "operations": recipe.get("operations", []),
            "story": recipe.get("story", ""),
            "checker_logic": recipe.get("checker_logic", ""),
        }
    return context


def _training_context(path: Path) -> dict[str, Any]:
    context = _safe_context(path)
    solve_path = path / "solution" / "solve.py"
    if solve_path.exists():
        context["solve_py"] = solve_path.read_text(encoding="utf-8", errors="ignore")
    return context


def _redact_flag(text: str, flag: Any) -> str:
    if isinstance(flag, str) and flag:
        return text.replace(flag, "[redacted]")
    return text
