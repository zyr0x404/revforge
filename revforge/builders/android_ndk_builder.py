"""Build Android NDK generated projects."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ..utils import command_exists


def available() -> bool:
    return command_exists("gradle") and bool(os.environ.get("ANDROID_NDK_HOME") or os.environ.get("ANDROID_NDK_ROOT"))


def status() -> str:
    gradle = "gradle" if command_exists("gradle") else "missing gradle"
    ndk = "Android NDK" if os.environ.get("ANDROID_NDK_HOME") or os.environ.get("ANDROID_NDK_ROOT") else "missing ANDROID_NDK_HOME"
    return f"{gradle}; {ndk}"


def build(challenge_dir: Path, metadata: dict) -> tuple[bool, str]:
    if not (challenge_dir / "app" / "src" / "main" / "cpp" / "native-lib.cpp").exists():
        return False, "Android native source is missing; rebuild with source included"
    if not command_exists("gradle"):
        return False, "missing gradle. Build with Android Studio or install Gradle"
    if not (os.environ.get("ANDROID_NDK_HOME") or os.environ.get("ANDROID_NDK_ROOT")):
        return False, "missing Android NDK. Set ANDROID_NDK_HOME or build with Android Studio"
    result = subprocess.run(["gradle", "assembleDebug"], cwd=challenge_dir, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip()
    apk = challenge_dir / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    dist = challenge_dir / "dist"
    dist.mkdir(exist_ok=True)
    if apk.exists():
        output = dist / metadata["binary_name"]
        output.write_bytes(apk.read_bytes())
        return True, f"built {output}"
    return True, "gradle completed; APK path was not found in the expected debug output directory"

