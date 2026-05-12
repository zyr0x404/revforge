"""Target descriptors for generated challenges."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TargetSpec:
    name: str
    display: str
    description: str
    source_relpath: str
    binary_name_suffix: str
    builder: str
    source_generation: bool = True


def get_target(name: str) -> TargetSpec:
    from .android import TARGET as ANDROID
    from .elf import TARGET as ELF
    from .exe import TARGET as EXE
    from .macho import TARGET as MACHO
    from .wasm import TARGET as WASM

    targets = {target.name: target for target in (ELF, EXE, MACHO, ANDROID, WASM)}
    return targets[name]


def all_targets() -> tuple[TargetSpec, ...]:
    from .android import TARGET as ANDROID
    from .elf import TARGET as ELF
    from .exe import TARGET as EXE
    from .macho import TARGET as MACHO
    from .wasm import TARGET as WASM

    return (ELF, EXE, MACHO, ANDROID, WASM)

