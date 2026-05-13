"""Shared helpers for RevForge."""

from __future__ import annotations

import json
import os
import re
import shutil
import string
from pathlib import Path
from random import Random

CREATED_BY = "RevForge"
BANNER = "RevForge challenge"

_C_KEYWORDS = {
    "auto",
    "break",
    "case",
    "char",
    "const",
    "continue",
    "default",
    "do",
    "double",
    "else",
    "enum",
    "extern",
    "float",
    "for",
    "goto",
    "if",
    "inline",
    "int",
    "long",
    "register",
    "restrict",
    "return",
    "short",
    "signed",
    "sizeof",
    "static",
    "struct",
    "switch",
    "typedef",
    "union",
    "unsigned",
    "void",
    "volatile",
    "while",
}


def c_string(value: str) -> str:
    """Return a JSON-compatible escaped C string literal."""

    return json.dumps(value)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def json_dump(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def random_identifier(rng: Random, prefix: str = "rf") -> str:
    alphabet = string.ascii_lowercase
    body = "".join(rng.choice(alphabet) for _ in range(rng.randint(7, 12)))
    ident = f"{prefix}_{body}"
    if ident in _C_KEYWORDS:
        ident = f"{ident}_v"
    return ident


def random_identifiers(rng: Random, keys: list[str], prefix: str = "rf") -> dict[str, str]:
    used: set[str] = set()
    names: dict[str, str] = {}
    for key in keys:
        ident = random_identifier(rng, prefix)
        while ident in used:
            ident = random_identifier(rng, prefix)
        used.add(ident)
        names[key] = ident
    return names


def slugify_name(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", name.strip()).strip("-")
    if not slug:
        raise ValueError("challenge name must contain at least one safe character")
    return slug


def c_array(values: list[int], width: int = 12) -> str:
    chunks: list[str] = []
    for index in range(0, len(values), width):
        chunk = ", ".join(str(v) for v in values[index : index + width])
        chunks.append(f"    {chunk}")
    return ",\n".join(chunks)


def shell_quote_path(path: str) -> str:
    return "'" + path.replace("'", "'\"'\"'") + "'"


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
