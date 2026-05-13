"""Audit and anti-toy quality checks."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .utils import CREATED_BY


SERIOUS_DIFFICULTIES = {"medium", "hard", "super-hard"}


@dataclass(frozen=True)
class AuditReport:
    path: Path
    metadata_valid: bool
    difficulty: str
    template: str
    profile: str
    style: str
    family: str
    competition_mode: bool
    source_exists: bool
    binary_exists: bool
    solution_exists: bool
    full_flag_in_source: bool | None
    full_flag_in_binary: bool | None
    full_flag_in_strings: bool | None
    binary_stripped: bool | None
    private_files_leaked: bool
    direct_full_input_compare: bool
    solve_py_literal_print: bool
    generated_function_count: int
    encoded_constant_count: int
    bytecode_length: int
    constraint_count: int
    local_artifact_count: int
    terminal_commands_detected: list[str]
    fake_flags_enabled: bool
    fake_flag_count: int
    fake_flag_style: str
    quality_score: int
    final_grade: str
    findings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "metadata_valid": self.metadata_valid,
            "difficulty": self.difficulty,
            "template": self.template,
            "profile": self.profile,
            "style": self.style,
            "family": self.family,
            "competition_mode": self.competition_mode,
            "source_exists": self.source_exists,
            "binary_exists": self.binary_exists,
            "solution_exists": self.solution_exists,
            "full_flag_in_source": self.full_flag_in_source,
            "full_flag_in_binary": self.full_flag_in_binary,
            "full_flag_in_strings": self.full_flag_in_strings,
            "binary_stripped": self.binary_stripped,
            "private_files_leaked": self.private_files_leaked,
            "direct_full_input_compare": self.direct_full_input_compare,
            "solve_py_literal_print": self.solve_py_literal_print,
            "generated_function_count": self.generated_function_count,
            "encoded_constant_count": self.encoded_constant_count,
            "bytecode_length": self.bytecode_length,
            "constraint_count": self.constraint_count,
            "local_artifact_count": self.local_artifact_count,
            "terminal_commands_detected": self.terminal_commands_detected,
            "fake_flags_enabled": self.fake_flags_enabled,
            "fake_flag_count": self.fake_flag_count,
            "fake_flag_style": self.fake_flag_style,
            "quality_score": self.quality_score,
            "final_grade": self.final_grade,
            "findings": self.findings,
        }


def audit_challenge(challenge_dir: Path | str) -> AuditReport:
    path = _challenge_root(Path(challenge_dir))
    metadata, metadata_valid = _load_metadata(path)
    difficulty = metadata.get("difficulty", "unknown")
    template = metadata.get("template", "unknown")
    profile = metadata.get("profile", "standard")
    style = metadata.get("style", "simple")
    family = metadata.get("family", template)
    competition_mode = bool(metadata.get("competition_mode", False))
    binary_name = metadata.get("binary_name", metadata.get("name", ""))
    binary_path = path / "dist" / binary_name if binary_name else path / "dist"
    source_path = path / "src" / "main.c"
    solution_path = path / "solution" / "solve.py"
    recipe = _load_recipe(path)

    flag = metadata.get("flag")
    if flag is None and recipe:
        flag = recipe.get("flag")
    flag_bytes = flag.encode("utf-8") if isinstance(flag, str) else None

    source_text = source_path.read_text(encoding="utf-8", errors="ignore") if source_path.exists() else ""
    binary_data = binary_path.read_bytes() if binary_path.exists() and binary_path.is_file() else b""

    full_flag_in_source = None if flag is None else flag in source_text
    full_flag_in_binary = None if flag_bytes is None else flag_bytes in binary_data
    binary_strings = "\n".join(_extract_strings(binary_data))
    full_flag_in_strings = None if flag is None else flag in binary_strings
    stripped = _is_stripped(binary_path) if binary_data else None
    function_count = _function_count(source_text)
    bytecode_length = _bytecode_length(metadata, recipe)
    constraint_count = _constraint_count(metadata, recipe)
    encoded_constant_count = _encoded_constant_count(metadata, recipe, source_text)
    local_artifact_count = _local_artifact_count(path, metadata)
    terminal_commands = [str(item) for item in metadata.get("terminal_commands", [])]
    fake_flags_enabled = bool(metadata.get("fake_flags_enabled", False))
    fake_flag_count = int(metadata.get("fake_flag_count", 0))
    fake_flag_style = str(metadata.get("fake_flag_style", "default"))
    private_files_leaked = _private_files_leaked(path) if competition_mode and (path / "metadata_public.json").exists() else False
    direct_compare = _direct_full_input_compare(source_text)
    solution_text = solution_path.read_text(encoding="utf-8", errors="ignore") if solution_path.exists() else ""
    literal_print = _literal_solver_print(solution_text)
    findings = _findings(
        difficulty=difficulty,
        profile=profile,
        style=style,
        family=family,
        competition_mode=competition_mode,
        metadata_valid=metadata_valid,
        source_exists=source_path.exists(),
        binary_exists=bool(binary_data),
        solution_exists=solution_path.exists(),
        full_flag_in_source=full_flag_in_source,
        full_flag_in_binary=full_flag_in_binary,
        full_flag_in_strings=full_flag_in_strings,
        stripped=stripped,
        private_files_leaked=private_files_leaked,
        direct_compare=direct_compare,
        function_count=function_count,
        encoded_constant_count=encoded_constant_count,
        bytecode_length=bytecode_length,
        constraint_count=constraint_count,
        local_artifact_count=local_artifact_count,
        terminal_commands=terminal_commands,
        solution_text=solution_text,
        literal_print=literal_print,
        flag=flag if isinstance(flag, str) else None,
    )
    score = _score(difficulty, profile, style, findings)
    return AuditReport(
        path=path,
        metadata_valid=metadata_valid,
        difficulty=difficulty,
        template=template,
        profile=profile,
        style=style,
        family=family,
        competition_mode=competition_mode,
        source_exists=source_path.exists(),
        binary_exists=bool(binary_data),
        solution_exists=solution_path.exists(),
        full_flag_in_source=full_flag_in_source,
        full_flag_in_binary=full_flag_in_binary,
        full_flag_in_strings=full_flag_in_strings,
        binary_stripped=stripped,
        private_files_leaked=private_files_leaked,
        direct_full_input_compare=direct_compare,
        solve_py_literal_print=literal_print,
        generated_function_count=function_count,
        encoded_constant_count=encoded_constant_count,
        bytecode_length=bytecode_length,
        constraint_count=constraint_count,
        local_artifact_count=local_artifact_count,
        terminal_commands_detected=terminal_commands,
        fake_flags_enabled=fake_flags_enabled,
        fake_flag_count=fake_flag_count,
        fake_flag_style=fake_flag_style,
        quality_score=score,
        final_grade=_grade(score),
        findings=findings,
    )


def quality_gate(challenge_dir: Path | str, recipe) -> None:
    report = audit_challenge(challenge_dir)
    serious = recipe.difficulty in SERIOUS_DIFFICULTIES
    failures: list[str] = []
    if serious and report.full_flag_in_source:
        failures.append("full flag appears in src/main.c")
    if serious and report.full_flag_in_strings:
        failures.append("full flag appears in compiled binary")
    if serious and report.solve_py_literal_print:
        failures.append("solve.py appears to print a string literal directly")
    if recipe.style == "terminal" and not report.terminal_commands_detected:
        failures.append("terminal challenge has no declared commands")
    if recipe.profile == "qualifier":
        if recipe.difficulty == "hard" and report.quality_score < 80:
            failures.append("hard qualifier audit score is below 80")
        if recipe.difficulty == "super-hard" and report.quality_score < 90:
            failures.append("super-hard qualifier audit score is below 90")
    if recipe.profile == "finals" and report.quality_score < 95:
        failures.append("finals audit score is below 95")
    if recipe.difficulty == "hard" and report.generated_function_count < 5:
        failures.append("hard source has fewer than 5 generated functions")
    if recipe.style != "terminal" and recipe.difficulty == "super-hard" and report.generated_function_count < 10:
        failures.append("super-hard source has fewer than 10 generated functions")
    if recipe.difficulty == "super-hard" and recipe.template_family == "superhard_toy_vm_real" and report.bytecode_length < 80:
        failures.append("super-hard VM bytecode is shorter than 80 bytes")
    if recipe.template_family in {"terminal_license_vm", "qualifier_vm"}:
        threshold = 350 if recipe.profile == "finals" else 180
        if report.bytecode_length < threshold:
            failures.append(f"terminal VM bytecode is shorter than {threshold} bytes")
    if recipe.template_family in {"terminal_constraints_pack", "qualifier_constraints"}:
        threshold = 80 if recipe.profile == "finals" or recipe.difficulty == "super-hard" else 40
        if report.constraint_count < threshold:
            failures.append(f"terminal constraint count is below {threshold}")
    if recipe.template_family == "terminal_hybrid_finals" and len(recipe.technique_mix) < 3:
        failures.append("finals hybrid has fewer than 3 techniques")
    solution = Path(challenge_dir) / "solution" / "solve.py"
    if serious and solution.exists():
        text = solution.read_text(encoding="utf-8", errors="ignore")
        if recipe.flag in text:
            failures.append("solve.py contains the full flag literal")
        if re.search(r"print\(\s*(['\"])[^'\"]+\1\s*\)", text):
            failures.append("solve.py appears to print a string literal directly")
    if failures:
        raise ValueError("quality gate failed: " + "; ".join(failures))


def _load_metadata(path: Path) -> tuple[dict[str, Any], bool]:
    for name in ("metadata.json", "metadata_public.json"):
        candidate = path / name
        if candidate.exists():
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                return {}, False
            required = {"name", "difficulty", "target", "template", "recipe_hash", "created_by"}
            return data, required.issubset(data.keys()) and data.get("created_by") == CREATED_BY
    return {}, False


def _load_recipe(path: Path) -> dict[str, Any] | None:
    recipe_path = path / "recipe.json"
    if not recipe_path.exists():
        return None
    try:
        return json.loads(recipe_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _function_count(source_text: str) -> int:
    return len(re.findall(r"static\s+(?:int|unsigned\s+int|uint32_t|void)\s+rf_[A-Za-z0-9_]+\s*\(", source_text))


def _bytecode_length(metadata: dict[str, Any], recipe: dict[str, Any] | None) -> int:
    if "bytecode_length" in metadata:
        return int(metadata["bytecode_length"])
    if recipe:
        constants = recipe.get("constants", {})
        if "bytecode_length" in constants:
            return int(constants["bytecode_length"])
    return 0


def _constraint_count(metadata: dict[str, Any], recipe: dict[str, Any] | None) -> int:
    if "constraint_count" in metadata:
        return int(metadata["constraint_count"])
    if recipe:
        constants = recipe.get("constants", {})
        if "constraint_count" in constants:
            return int(constants["constraint_count"])
    return 0


def _encoded_constant_count(metadata: dict[str, Any], recipe: dict[str, Any] | None, source_text: str) -> int:
    if "encoded_constant_count" in metadata:
        return int(metadata["encoded_constant_count"])
    if recipe:
        constants = recipe.get("constants", {})
        if "encoded_constant_count" in constants:
            return int(constants["encoded_constant_count"])
        return _count_numeric_constants(constants)
    return len(re.findall(r"\b(?:0x[0-9A-Fa-f]+|\d+)u?\b", source_text))


def _count_numeric_constants(value: Any) -> int:
    if isinstance(value, int):
        return 1
    if isinstance(value, list):
        return sum(_count_numeric_constants(item) for item in value)
    if isinstance(value, dict):
        return sum(_count_numeric_constants(item) for item in value.values())
    return 0


def _local_artifact_count(path: Path, metadata: dict[str, Any]) -> int:
    artifacts = metadata.get("artifact_files")
    if isinstance(artifacts, list):
        return sum(1 for item in artifacts if (path / str(item)).exists())
    ignored = {"README.md", "metadata.json", "metadata_public.json", "recipe.json", "Makefile", "build.sh", "writeup.md"}
    return sum(1 for item in path.iterdir() if item.is_file() and item.name not in ignored)


def _private_files_leaked(path: Path) -> bool:
    private_names = ["metadata.json", "recipe.json", "build.sh", "Makefile", "writeup.md", "src", "solution", "app", "ai_recipe.json"]
    return any((path / name).exists() for name in private_names)


def _direct_full_input_compare(source_text: str) -> bool:
    patterns = [
        r"\bstrcmp\s*\(\s*candidate\s*,",
        r"\bstrcmp\s*\([^,]+,\s*candidate\s*\)",
        r"\bmemcmp\s*\(\s*candidate\s*,",
        r"\bmemcmp\s*\([^,]+,\s*candidate\s*,",
    ]
    return any(re.search(pattern, source_text) for pattern in patterns)


def _literal_solver_print(solution_text: str) -> bool:
    return bool(re.search(r"print\(\s*(['\"])[^'\"]+\1\s*\)", solution_text))


def _extract_strings(data: bytes, min_length: int = 4) -> list[str]:
    strings: list[str] = []
    current = bytearray()
    for byte in data:
        if 32 <= byte <= 126:
            current.append(byte)
        else:
            if len(current) >= min_length:
                strings.append(current.decode("ascii", errors="ignore"))
            current.clear()
    if len(current) >= min_length:
        strings.append(current.decode("ascii", errors="ignore"))
    return strings


def _challenge_root(path: Path) -> Path:
    if path.is_file() and path.parent.name == "dist":
        return path.parent.parent
    return path


def _is_stripped(binary_path: Path) -> bool | None:
    if not binary_path.exists() or not binary_path.is_file():
        return None
    try:
        result = subprocess.run(["file", str(binary_path)], text=True, capture_output=True, check=False)
    except OSError:
        return None
    output = result.stdout.lower()
    if "not stripped" in output:
        return False
    if "stripped" in output:
        return True
    return None


def _findings(
    *,
    difficulty: str,
    profile: str,
    style: str,
    family: str,
    competition_mode: bool,
    metadata_valid: bool,
    source_exists: bool,
    binary_exists: bool,
    solution_exists: bool,
    full_flag_in_source: bool | None,
    full_flag_in_binary: bool | None,
    full_flag_in_strings: bool | None,
    stripped: bool | None,
    private_files_leaked: bool,
    direct_compare: bool,
    function_count: int,
    encoded_constant_count: int,
    bytecode_length: int,
    constraint_count: int,
    local_artifact_count: int,
    terminal_commands: list[str],
    solution_text: str,
    literal_print: bool,
    flag: str | None,
) -> list[str]:
    findings: list[str] = []
    if not metadata_valid:
        findings.append("metadata is missing or invalid")
    if not binary_exists:
        findings.append("dist binary is missing")
    if competition_mode:
        if private_files_leaked:
            findings.append("competition mode includes private files")
    elif not solution_exists:
        findings.append("training mode solution is missing")
    if difficulty in SERIOUS_DIFFICULTIES:
        if full_flag_in_source:
            findings.append("full flag appears in source")
        if full_flag_in_binary or full_flag_in_strings:
            findings.append("full flag appears in binary strings")
        if flag is None and not competition_mode:
            findings.append("full-flag leak scan skipped because private flag is unavailable")
        if solution_text and flag and flag in solution_text:
            findings.append("solution contains full flag literal")
        if literal_print:
            findings.append("solution appears to print a literal")
        if direct_compare:
            findings.append("source appears to use direct full-input compare")
    if difficulty in {"hard", "super-hard"}:
        if stripped is False:
            findings.append("hard release binary is not stripped")
        if difficulty == "hard" and function_count < 5 and source_exists:
            findings.append("hard source has fewer than 5 generated functions")
        if style != "terminal" and difficulty == "super-hard" and function_count < 10 and source_exists:
            findings.append("super-hard source has fewer than 10 generated functions")
    if difficulty == "super-hard" and bytecode_length and bytecode_length < 80:
        findings.append("super-hard bytecode length is below 80 bytes")
    if style == "terminal":
        if local_artifact_count < 1:
            findings.append("terminal challenge has no local artifact")
        if not terminal_commands:
            findings.append("terminal commands are missing")
        if encoded_constant_count < 20:
            findings.append("encoded constant count is low")
        if family in {"terminal_license_vm", "qualifier_vm"}:
            threshold = 350 if profile == "finals" else 180
            if bytecode_length < threshold:
                findings.append(f"terminal VM bytecode length is below {threshold} bytes")
        if family in {"terminal_constraints_pack", "qualifier_constraints"}:
            threshold = 80 if profile == "finals" or difficulty == "super-hard" else 40
            if constraint_count < threshold:
                findings.append(f"terminal constraint count is below {threshold}")
        if family == "terminal_hybrid_finals":
            if bytecode_length < 350:
                findings.append("finals hybrid bytecode length is below 350 bytes")
            if constraint_count < 80:
                findings.append("finals hybrid constraint count is below 80")
    return findings


def _score(difficulty: str, profile: str, style: str, findings: list[str]) -> int:
    base = {"baby": 70, "easy": 78, "medium": 86, "hard": 93, "super-hard": 97}.get(difficulty, 60)
    if style == "terminal":
        base += 3
    if profile == "qualifier":
        base += 2
    if profile == "finals":
        base = 100
    penalty = 0
    for finding in findings:
        if "full flag appears" in finding:
            penalty += 40
        elif "missing" in finding or "invalid" in finding:
            penalty += 18
        elif "not stripped" in finding or "direct full-input" in finding:
            penalty += 12
        elif "fewer" in finding or "below" in finding:
            penalty += 10
        elif "skipped" in finding:
            penalty += 3
        else:
            penalty += 6
    return max(0, min(100, base - penalty))


def _grade(score: int) -> str:
    if score >= 95:
        return "A"
    if score >= 90:
        return "B"
    if score >= 80:
        return "C"
    if score >= 70:
        return "D"
    return "F"
