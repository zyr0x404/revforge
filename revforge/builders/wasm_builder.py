"""Build WebAssembly challenges with emscripten."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from ..utils import command_exists


def available() -> bool:
    return command_exists("emcc")


def status() -> str:
    if available():
        return "available: emcc"
    return "missing: install and activate emscripten so emcc is on PATH"


def build(challenge_dir: Path, metadata: dict) -> tuple[bool, str]:
    source = challenge_dir / "src" / "main.c"
    if not source.exists():
        return False, "source file src/main.c is missing; rebuild from a non-competition challenge"
    if not available():
        return False, "missing emscripten compiler: emcc"
    dist = challenge_dir / "dist"
    dist.mkdir(exist_ok=True)
    cmd = [
        "emcc",
        str(source),
        "-O2",
        "-s",
        "WASM=1",
        "-s",
        "INVOKE_RUN=0",
        "-s",
        'EXPORTED_RUNTIME_METHODS=["callMain"]',
        "-o",
        str(dist / "challenge.js"),
    ]
    result = subprocess.run(cmd, cwd=challenge_dir, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    index = challenge_dir / "index.html"
    if index.exists():
        shutil.copy2(index, dist / "index.html")
    return True, f"built {dist / 'challenge.wasm'}"
