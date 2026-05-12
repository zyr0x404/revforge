"""Linux ELF target."""

from . import TargetSpec

TARGET = TargetSpec(
    name="elf",
    display="Linux ELF",
    description="Linux ELF binaries built with gcc or clang on Kali, Ubuntu, Debian, and WSL.",
    source_relpath="src/main.c",
    binary_name_suffix="",
    builder="gcc",
)

