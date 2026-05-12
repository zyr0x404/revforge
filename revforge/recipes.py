"""Recipe model and template catalog."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .utils import CREATED_BY

DIFFICULTIES = ("baby", "easy", "medium", "hard", "super-hard")
TARGETS = ("elf", "exe", "macho", "android", "wasm")

TEMPLATES_BY_DIFFICULTY: dict[str, tuple[str, ...]] = {
    "baby": ("baby_plain", "baby_reverse", "baby_caesar"),
    "easy": ("easy_xor", "easy_split", "easy_math"),
    "medium": ("medium_xor_chain", "medium_chunked_flag", "medium_arithmetic_validator"),
    "hard": ("hard_state_machine", "hard_multistage"),
    "super-hard": ("superhard_toy_vm",),
}

TEMPLATE_ALIASES: dict[str, dict[str, str]] = {
    "baby": {
        "plain": "baby_plain",
        "reverse": "baby_reverse",
        "caesar": "baby_caesar",
        "strings": "baby_plain",
    },
    "easy": {
        "xor": "easy_xor",
        "split": "easy_split",
        "math": "easy_math",
        "checksum": "easy_math",
    },
    "medium": {
        "xor": "medium_xor_chain",
        "chunked": "medium_chunked_flag",
        "arithmetic": "medium_arithmetic_validator",
        "lookup": "medium_chunked_flag",
        "fibonacci": "medium_arithmetic_validator",
    },
    "hard": {
        "state": "hard_state_machine",
        "state-machine": "hard_state_machine",
        "multistage": "hard_multistage",
        "encoded": "hard_multistage",
        "control-flow": "hard_state_machine",
    },
    "super-hard": {
        "vm": "superhard_toy_vm",
        "toy-vm": "superhard_toy_vm",
        "bytecode": "superhard_toy_vm",
        "constraints": "superhard_toy_vm",
    },
}


@dataclass
class ChallengeRecipe:
    name: str
    difficulty: str
    target: str
    template_family: str
    seed: int
    flag: str
    flag_format: str
    encoding_chain: list[str] = field(default_factory=list)
    checker_type: str = ""
    constants: dict[str, Any] = field(default_factory=dict)
    fake_flags: list[str] = field(default_factory=list)
    fake_strings: list[str] = field(default_factory=list)
    success_message: str = "Correct."
    failure_message: str = "Nope."
    function_names: dict[str, str] = field(default_factory=dict)
    variable_names: dict[str, str] = field(default_factory=dict)
    stages: list[dict[str, Any]] = field(default_factory=list)
    compiler_flags: list[str] = field(default_factory=list)
    created_by: str = CREATED_BY
    transformations: list[str] = field(default_factory=list)
    operations: list[str] = field(default_factory=list)
    story: str = ""
    checker_logic: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def hash_material(self) -> dict[str, Any]:
        data = self.to_dict()
        data.pop("name", None)
        data.pop("created_by", None)
        return data

    def recipe_hash(self) -> str:
        payload = json.dumps(self.hash_material(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_difficulty(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    if normalized == "superhard":
        normalized = "super-hard"
    if normalized not in DIFFICULTIES:
        raise ValueError(f"unknown difficulty {value!r}; choose one of {', '.join(DIFFICULTIES)}")
    return normalized


def normalize_target(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"linux", "linux-elf"}:
        normalized = "elf"
    if normalized in {"windows", "pe"}:
        normalized = "exe"
    if normalized in {"mac", "macos"}:
        normalized = "macho"
    if normalized not in TARGETS:
        raise ValueError(f"unknown target {value!r}; choose one of {', '.join(TARGETS)}")
    return normalized


def template_difficulty(template_name: str) -> str | None:
    for difficulty, names in TEMPLATES_BY_DIFFICULTY.items():
        if template_name in names:
            return difficulty
    return None


def resolve_template(difficulty: str, template: str | None, rng) -> str:
    difficulty = normalize_difficulty(difficulty)
    if not template:
        choices = TEMPLATES_BY_DIFFICULTY[difficulty]
        return rng.choice(choices)

    normalized = template.strip().lower().replace("-", "_")
    exact = template_difficulty(normalized)
    if exact:
        if exact != difficulty:
            raise ValueError(f"template {template!r} belongs to {exact}, not {difficulty}")
        return normalized

    alias = template.strip().lower().replace("_", "-")
    if alias in TEMPLATE_ALIASES[difficulty]:
        return TEMPLATE_ALIASES[difficulty][alias]

    choices = ", ".join(TEMPLATES_BY_DIFFICULTY[difficulty])
    raise ValueError(f"unknown template {template!r} for {difficulty}; choose one of {choices}")
