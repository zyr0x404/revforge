"""Build Linux ELF challenges with gcc or clang."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..utils import command_exists


def available() -> bool:
    return command_exists("gcc") or command_exists("clang")


def status() -> str:
    if command_exists("gcc"):
        return "available: gcc"
    if command_exists("clang"):
        return "available: clang"
    return "missing: install gcc or clang"


def build(challenge_dir: Path, metadata: dict) -> tuple[bool, str]:
    source = challenge_dir / "src" / "main.c"
    if not source.exists():
        return False, "source file src/main.c is missing; rebuild from a non-competition challenge"
    compiler = "gcc" if command_exists("gcc") else "clang" if command_exists("clang") else None
    if compiler is None:
        return False, "missing compiler: install gcc or clang"
    dist = challenge_dir / "dist"
    dist.mkdir(exist_ok=True)
    output = dist / metadata["binary_name"]
    cmd = [compiler, "-std=c11", "-O2", "-Wall", "-Wextra"]
    if metadata.get("difficulty") in {"hard", "super-hard"}:
        cmd.append("-s")
    cmd.extend([str(source), "-o", str(output)])
    result = subprocess.run(cmd, cwd=challenge_dir, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, f"built {output}"
