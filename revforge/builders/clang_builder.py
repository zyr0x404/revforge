"""Build macOS Mach-O challenges natively with clang."""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path

from ..utils import command_exists


def available() -> bool:
    return platform.system() == "Darwin" and command_exists("clang")


def status() -> str:
    if platform.system() == "Darwin" and command_exists("clang"):
        return "available: native macOS clang"
    if platform.system() != "Darwin":
        return "source only on this host: Mach-O building requires macOS or an advanced cross-compiler setup"
    return "missing: install Xcode command line tools for clang"


def build(challenge_dir: Path, metadata: dict) -> tuple[bool, str]:
    source = challenge_dir / "src" / "main.c"
    if not source.exists():
        return False, "source file src/main.c is missing; rebuild from a non-competition challenge"
    if platform.system() != "Darwin":
        return False, "Mach-O building requires macOS or an advanced cross-compiler setup; source generation is supported here"
    if not command_exists("clang"):
        return False, "missing clang. Install Xcode command line tools"
    dist = challenge_dir / "dist"
    dist.mkdir(exist_ok=True)
    output = dist / metadata["binary_name"]
    cmd = ["clang", "-std=c11", "-O2", "-Wall", "-Wextra"]
    if metadata.get("difficulty") in {"hard", "super-hard"}:
        cmd.append("-s")
    cmd.extend([str(source), "-o", str(output)])
    result = subprocess.run(cmd, cwd=challenge_dir, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, f"built {output}"
