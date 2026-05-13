"""Serious-generation selftest workflow."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .builders import build_challenge
from .generator import generate_challenge
from .quality import audit_challenge


@dataclass(frozen=True)
class SelftestCase:
    difficulty: str
    template: str
    name: str
    profile: str = "standard"
    style: str | None = None
    family: str | None = None
    minimum_score: int = 0


@dataclass(frozen=True)
class SelftestCaseResult:
    case: SelftestCase
    path: Path
    solved: bool
    accepted: bool
    leaked: bool
    audit_score: int


@dataclass(frozen=True)
class FakeFlagSelftestResult:
    name: str
    fake_flags_enabled: bool
    expected_fake_count: int
    observed_flag_like_count: int
    real_flag_leaked: bool
    private_files_leaked: bool
    audit_score: int


SELFTEST_CASES = (
    SelftestCase("baby", "baby_strings", "self_baby"),
    SelftestCase("easy", "easy_xor_chunks", "self_easy"),
    SelftestCase("medium", "medium_multi_stage", "self_medium"),
    SelftestCase("hard", "hard_state_machine", "self_hard"),
    SelftestCase("super-hard", "superhard_toy_vm_real", "self_super"),
)

QUALIFIER_SELFTEST_CASES = (
    SelftestCase("medium", "terminal_signal_pipeline", "qualifier_medium", profile="qualifier", style="terminal", family="terminal_signal_pipeline"),
    SelftestCase("hard", "terminal_firmware_blob", "qualifier_hard", profile="qualifier", style="terminal", family="terminal_firmware_blob", minimum_score=80),
    SelftestCase("super-hard", "terminal_license_vm", "qualifier_super", profile="qualifier", style="terminal", family="terminal_license_vm", minimum_score=90),
)

FINALS_SELFTEST_CASES = (
    SelftestCase("super-hard", "terminal_hybrid_finals", "finals_super", profile="finals", style="terminal", family="terminal_hybrid_finals", minimum_score=95),
)


def run_selftest_serious() -> list[SelftestCaseResult]:
    return _run_cases(SELFTEST_CASES)


def run_selftest_qualifier() -> list[SelftestCaseResult]:
    return _run_cases(QUALIFIER_SELFTEST_CASES)


def run_selftest_finals() -> list[SelftestCaseResult]:
    return _run_cases(FINALS_SELFTEST_CASES)


def run_selftest_fake_flags() -> list[FakeFlagSelftestResult]:
    results: list[FakeFlagSelftestResult] = []
    old_home = os.environ.get("REVFORGE_HOME")
    with tempfile.TemporaryDirectory(prefix="revforge-fakeflags-") as work, tempfile.TemporaryDirectory(prefix="revforge-history-") as home:
        os.environ["REVFORGE_HOME"] = home
        root = Path(work)
        try:
            clean = generate_challenge(
                name="fakeflag_clean",
                difficulty="super-hard",
                profile="finals",
                style="terminal",
                family="terminal_hybrid_finals",
                target="elf",
                competition_mode=True,
                out_dir=root,
                seed=0x5A10,
                allow_repeat=True,
            )
            results.append(_fake_flag_result(clean.challenge_dir, clean.recipe.flag, expected=0))

            decoy = generate_challenge(
                name="fakeflag_decoy",
                difficulty="super-hard",
                profile="finals",
                style="terminal",
                family="terminal_hybrid_finals",
                target="elf",
                competition_mode=True,
                fake_flags=True,
                fake_flag_count=8,
                fake_flag_style="mixed",
                out_dir=root,
                seed=0x5A11,
                allow_repeat=True,
            )
            results.append(_fake_flag_result(decoy.challenge_dir, decoy.recipe.flag, expected=8))
        finally:
            if old_home is None:
                os.environ.pop("REVFORGE_HOME", None)
            else:
                os.environ["REVFORGE_HOME"] = old_home
    return results


def _fake_flag_result(path: Path, real_flag: str, *, expected: int) -> FakeFlagSelftestResult:
    audit = audit_challenge(path)
    binary = path / "dist" / audit.path.name
    strings = "\n".join(_extract_strings(binary.read_bytes())) if binary.exists() else ""
    observed = len([line for line in strings.splitlines() if ("flag{" in line or "CTF{" in line)])
    real_leaked = real_flag in strings
    if expected == 0 and observed:
        raise RuntimeError("fake flag decoys appeared without --fake-flags")
    if expected and observed < 1:
        raise RuntimeError("fake flag decoys were not present with --fake-flags")
    if audit.fake_flag_count != expected:
        raise RuntimeError(f"fake flag metadata count {audit.fake_flag_count} did not match {expected}")
    if expected and not audit.fake_flags_enabled:
        raise RuntimeError("fake flag metadata did not mark decoys as enabled")
    if real_leaked:
        raise RuntimeError("real flag leaked in fake flag selftest binary strings")
    if audit.private_files_leaked:
        raise RuntimeError("competition-mode private files leaked in fake flag selftest")
    return FakeFlagSelftestResult(
        name=path.name,
        fake_flags_enabled=audit.fake_flags_enabled,
        expected_fake_count=expected,
        observed_flag_like_count=observed,
        real_flag_leaked=real_leaked,
        private_files_leaked=audit.private_files_leaked,
        audit_score=audit.quality_score,
    )


def _run_cases(cases: tuple[SelftestCase, ...]) -> list[SelftestCaseResult]:
    results: list[SelftestCaseResult] = []
    old_home = os.environ.get("REVFORGE_HOME")
    with tempfile.TemporaryDirectory(prefix="revforge-selftest-") as work, tempfile.TemporaryDirectory(prefix="revforge-history-") as home:
        os.environ["REVFORGE_HOME"] = home
        root = Path(work)
        try:
            for index, case in enumerate(cases):
                generated = generate_challenge(
                    name=case.name,
                    difficulty=case.difficulty,
                    template=None if case.family else case.template,
                    family=case.family,
                    profile=case.profile,
                    style=case.style,
                    target="elf",
                    out_dir=root,
                    seed=0x5200 + index,
                    allow_repeat=True,
                )
                ok, message = build_challenge(generated.challenge_dir)
                if not ok:
                    raise RuntimeError(f"build failed for {case.template}: {message}")
                solution = subprocess.run(
                    [sys.executable, str(generated.challenge_dir / "solution" / "solve.py")],
                    text=True,
                    capture_output=True,
                    check=True,
                ).stdout.strip()
                binary = generated.challenge_dir / "dist" / generated.metadata["binary_name"]
                if generated.metadata.get("style") == "terminal":
                    run = subprocess.run([str(binary), "verify", solution], cwd=generated.challenge_dir, text=True, capture_output=True, check=False)
                else:
                    run = subprocess.run([str(binary), solution], text=True, capture_output=True, check=False)
                binary_data = binary.read_bytes()
                binary_strings = "\n".join(_extract_strings(binary_data))
                leaked = generated.metadata["flag"] in binary_strings or generated.metadata["flag"].encode("utf-8") in binary_data
                if case.difficulty in {"medium", "hard", "super-hard"} and leaked:
                    raise RuntimeError(f"{case.template} leaked the full flag in binary strings")
                audit = audit_challenge(generated.challenge_dir)
                results.append(
                    SelftestCaseResult(
                        case=case,
                        path=generated.challenge_dir,
                        solved=solution == generated.metadata["flag"],
                        accepted=run.returncode == 0,
                        leaked=leaked,
                        audit_score=audit.quality_score,
                    )
                )
                if solution != generated.metadata["flag"]:
                    raise RuntimeError(f"solver mismatch for {case.template}")
                if run.returncode != 0:
                    raise RuntimeError(f"binary rejected solver output for {case.template}")
                if case.minimum_score and audit.quality_score < case.minimum_score:
                    raise RuntimeError(f"{case.template} audit score {audit.quality_score} is below {case.minimum_score}")
        finally:
            if old_home is None:
                os.environ.pop("REVFORGE_HOME", None)
            else:
                os.environ["REVFORGE_HOME"] = old_home
    return results


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
