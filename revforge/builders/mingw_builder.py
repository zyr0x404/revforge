"""Build Windows PE challenges with mingw-w64."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..utils import command_exists

INSTALL_HINT = "sudo apt update && sudo apt install -y mingw-w64"


def available() -> bool:
    return command_exists("x86_64-w64-mingw32-gcc")


def status() -> str:
    if available():
        return "available: x86_64-w64-mingw32-gcc"
    return f"missing: {INSTALL_HINT}"


def build(challenge_dir: Path, metadata: dict) -> tuple[bool, str]:
    source = challenge_dir / "src" / "main.c"
    if not source.exists():
        return False, "source file src/main.c is missing; rebuild from a non-competition challenge"
    if not available():
        return False, f"missing mingw-w64 compiler. Install with: {INSTALL_HINT}"
    dist = challenge_dir / "dist"
    dist.mkdir(exist_ok=True)
    output = dist / metadata["binary_name"]
    cmd = ["x86_64-w64-mingw32-gcc", "-O2", "-Wall", "-Wextra", str(source), "-o", str(output)]
    result = subprocess.run(cmd, cwd=challenge_dir, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    return True, f"built {output}"

