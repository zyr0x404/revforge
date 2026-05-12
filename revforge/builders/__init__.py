"""Builder dispatch for RevForge targets."""

from __future__ import annotations

from pathlib import Path


def build_challenge(challenge_dir: Path) -> tuple[bool, str]:
    from .android_ndk_builder import build as build_android
    from .clang_builder import build as build_clang
    from .gcc_builder import build as build_gcc
    from .mingw_builder import build as build_mingw
    from .wasm_builder import build as build_wasm
    from ..generator import load_metadata

    metadata = load_metadata(challenge_dir)
    target = metadata.get("target")
    if target == "elf":
        return build_gcc(challenge_dir, metadata)
    if target == "exe":
        return build_mingw(challenge_dir, metadata)
    if target == "macho":
        return build_clang(challenge_dir, metadata)
    if target == "android":
        return build_android(challenge_dir, metadata)
    if target == "wasm":
        return build_wasm(challenge_dir, metadata)
    return False, f"unknown target in metadata: {target!r}"

