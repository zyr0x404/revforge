"""Local recipe history and uniqueness checks."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


class DuplicateRecipeError(RuntimeError):
    """Raised when a deterministic recipe already exists in the local registry."""


@dataclass(frozen=True)
class RegistryEntry:
    recipe_hash: str
    name: str
    difficulty: str
    target: str
    template: str
    seed: int


def history_path() -> Path:
    explicit = os.environ.get("REVFORGE_HISTORY")
    if explicit:
        return Path(explicit).expanduser()
    home = Path(os.environ.get("REVFORGE_HOME", "~/.revforge")).expanduser()
    return home / "history.json"


def load_history(path: Path | None = None) -> dict:
    selected = path or history_path()
    if not selected.exists():
        return {"version": 1, "recipes": []}
    try:
        data = json.loads(selected.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "recipes": []}
    if not isinstance(data, dict) or "recipes" not in data:
        return {"version": 1, "recipes": []}
    return data


def is_known(recipe_hash: str, path: Path | None = None) -> bool:
    data = load_history(path)
    return any(item.get("recipe_hash") == recipe_hash for item in data.get("recipes", []))


def add_recipe(entry: RegistryEntry, path: Path | None = None) -> None:
    selected = path or history_path()
    selected.parent.mkdir(parents=True, exist_ok=True)
    data = load_history(selected)
    if not any(item.get("recipe_hash") == entry.recipe_hash for item in data["recipes"]):
        data["recipes"].append(
            {
                "recipe_hash": entry.recipe_hash,
                "name": entry.name,
                "difficulty": entry.difficulty,
                "target": entry.target,
                "template": entry.template,
                "seed": entry.seed,
            }
        )
    selected.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

