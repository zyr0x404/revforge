"""Recipe model and template catalog."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .utils import CREATED_BY

DIFFICULTIES = ("baby", "easy", "medium", "hard", "super-hard")
TARGETS = ("elf", "exe", "macho", "android", "wasm")
PROFILES = ("training", "standard", "qualifier", "finals")
STYLES = ("simple", "terminal")
FAKE_FLAG_STYLES = ("default", "generic", "ctf", "mixed")

TERMINAL_FAMILIES = (
    "terminal_firmware_blob",
    "terminal_license_vm",
    "terminal_signal_pipeline",
    "terminal_constraints_pack",
    "terminal_hybrid_finals",
)

QUALIFIER_FAMILIES = (
    "qualifier_vm",
    "qualifier_constraints",
    "qualifier_state_machine",
    "qualifier_transform_pipeline",
)

TERMINAL_ALIASES = {
    "firmware": "terminal_firmware_blob",
    "firmware-blob": "terminal_firmware_blob",
    "blob": "terminal_firmware_blob",
    "license": "terminal_license_vm",
    "license-vm": "terminal_license_vm",
    "vm-license": "terminal_license_vm",
    "signal": "terminal_signal_pipeline",
    "signal-pipeline": "terminal_signal_pipeline",
    "constraints-pack": "terminal_constraints_pack",
    "constraints": "terminal_constraints_pack",
    "hybrid": "terminal_hybrid_finals",
    "hybrid-finals": "terminal_hybrid_finals",
    "qualifier-vm": "qualifier_vm",
    "qualifier-constraints": "qualifier_constraints",
    "qualifier-state-machine": "qualifier_state_machine",
    "qualifier-transform-pipeline": "qualifier_transform_pipeline",
}

TEMPLATES_BY_DIFFICULTY: dict[str, tuple[str, ...]] = {
    "baby": ("baby_strings", "baby_reverse", "baby_caesar"),
    "easy": ("easy_xor_chunks", "easy_arithmetic_check", "easy_permutation"),
    "medium": (
        "medium_multi_stage",
        "medium_crc_gate",
        "medium_table_vm_lite",
        "terminal_signal_pipeline",
        "terminal_constraints_pack",
        "qualifier_constraints",
        "qualifier_transform_pipeline",
    ),
    "hard": (
        "hard_state_machine",
        "hard_mixed_constraints",
        "hard_encoded_table",
        "terminal_firmware_blob",
        "terminal_license_vm",
        "terminal_signal_pipeline",
        "terminal_constraints_pack",
        "qualifier_vm",
        "qualifier_constraints",
        "qualifier_state_machine",
        "qualifier_transform_pipeline",
    ),
    "super-hard": (
        "superhard_toy_vm_real",
        "superhard_symbolic_constraints",
        "superhard_state_vm_combo",
        "terminal_firmware_blob",
        "terminal_license_vm",
        "terminal_signal_pipeline",
        "terminal_constraints_pack",
        "terminal_hybrid_finals",
        "qualifier_vm",
        "qualifier_constraints",
        "qualifier_state_machine",
        "qualifier_transform_pipeline",
    ),
}

TEMPLATE_ALIASES: dict[str, dict[str, str]] = {
    "baby": {
        "plain": "baby_strings",
        "strings": "baby_strings",
        "reverse": "baby_reverse",
        "caesar": "baby_caesar",
    },
    "easy": {
        "xor": "easy_xor_chunks",
        "chunks": "easy_xor_chunks",
        "xor-chunks": "easy_xor_chunks",
        "math": "easy_arithmetic_check",
        "arithmetic": "easy_arithmetic_check",
        "permutation": "easy_permutation",
        "perm": "easy_permutation",
    },
    "medium": {
        "multi-stage": "medium_multi_stage",
        "multistage": "medium_multi_stage",
        "crc": "medium_crc_gate",
        "checksum": "medium_crc_gate",
        "vm": "medium_table_vm_lite",
        "table-vm": "medium_table_vm_lite",
        **TERMINAL_ALIASES,
    },
    "hard": {
        "state": "hard_state_machine",
        "state-machine": "hard_state_machine",
        "constraints": "hard_mixed_constraints",
        "mixed": "hard_mixed_constraints",
        "encoded": "hard_encoded_table",
        "table": "hard_encoded_table",
        **TERMINAL_ALIASES,
    },
    "super-hard": {
        "vm": "superhard_toy_vm_real",
        "toy-vm": "superhard_toy_vm_real",
        "bytecode": "superhard_toy_vm_real",
        "constraints": "superhard_symbolic_constraints",
        "symbolic": "superhard_symbolic_constraints",
        "combo": "superhard_state_vm_combo",
        "state-vm": "superhard_state_vm_combo",
        **TERMINAL_ALIASES,
    },
}

SIMPLE_TEMPLATES_BY_DIFFICULTY: dict[str, tuple[str, ...]] = {
    "baby": TEMPLATES_BY_DIFFICULTY["baby"],
    "easy": TEMPLATES_BY_DIFFICULTY["easy"],
    "medium": ("medium_multi_stage", "medium_crc_gate", "medium_table_vm_lite"),
    "hard": ("hard_state_machine", "hard_mixed_constraints", "hard_encoded_table"),
    "super-hard": ("superhard_toy_vm_real", "superhard_symbolic_constraints", "superhard_state_vm_combo"),
}

TERMINAL_TEMPLATES_BY_DIFFICULTY: dict[str, tuple[str, ...]] = {
    "baby": (),
    "easy": (),
    "medium": ("terminal_signal_pipeline", "terminal_constraints_pack", "qualifier_constraints", "qualifier_transform_pipeline"),
    "hard": (
        "terminal_firmware_blob",
        "terminal_license_vm",
        "terminal_signal_pipeline",
        "terminal_constraints_pack",
        "qualifier_vm",
        "qualifier_constraints",
        "qualifier_state_machine",
        "qualifier_transform_pipeline",
    ),
    "super-hard": (
        "terminal_firmware_blob",
        "terminal_license_vm",
        "terminal_signal_pipeline",
        "terminal_constraints_pack",
        "terminal_hybrid_finals",
        "qualifier_vm",
        "qualifier_constraints",
        "qualifier_state_machine",
        "qualifier_transform_pipeline",
    ),
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
    profile: str = "standard"
    style: str = "simple"
    family: str = ""
    terminal_commands: list[str] = field(default_factory=list)
    artifact_files: list[str] = field(default_factory=list)
    technique_mix: list[str] = field(default_factory=list)
    complexity_budget: int = 0
    fake_flags_enabled: bool = False
    fake_flag_count: int = 0
    fake_flag_style: str = "default"

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


def normalize_profile(value: str | None) -> str:
    normalized = (value or "standard").strip().lower().replace("_", "-")
    if normalized not in PROFILES:
        raise ValueError(f"unknown profile {value!r}; choose one of {', '.join(PROFILES)}")
    return normalized


def normalize_style(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower().replace("_", "-")
    if normalized not in STYLES:
        raise ValueError(f"unknown style {value!r}; choose one of {', '.join(STYLES)}")
    return normalized


def default_style(difficulty: str, profile: str) -> str:
    difficulty = normalize_difficulty(difficulty)
    profile = normalize_profile(profile)
    if difficulty in {"medium", "hard", "super-hard"} and profile in {"qualifier", "finals"}:
        return "terminal"
    return "simple"


def template_difficulty(template_name: str) -> str | None:
    for difficulty, names in TEMPLATES_BY_DIFFICULTY.items():
        if template_name in names:
            return difficulty
    return None


def resolve_template(difficulty: str, template: str | None, rng, *, style: str = "simple", profile: str = "standard") -> str:
    difficulty = normalize_difficulty(difficulty)
    style = normalize_style(style) or default_style(difficulty, profile)
    if not template:
        if style == "terminal":
            choices = TERMINAL_TEMPLATES_BY_DIFFICULTY[difficulty]
            if not choices:
                choices = SIMPLE_TEMPLATES_BY_DIFFICULTY[difficulty]
            if profile == "finals" and difficulty == "super-hard":
                return "terminal_hybrid_finals"
            if profile != "finals":
                choices = tuple(choice for choice in choices if choice != "terminal_hybrid_finals")
        else:
            choices = SIMPLE_TEMPLATES_BY_DIFFICULTY[difficulty]
        return rng.choice(choices)

    normalized = template.strip().lower().replace("-", "_")
    if normalized in TEMPLATES_BY_DIFFICULTY[difficulty]:
        return normalized
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
