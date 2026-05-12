"""macOS Mach-O target."""

from . import TargetSpec

TARGET = TargetSpec(
    name="macho",
    display="macOS Mach-O",
    description="Mach-O source is generated everywhere; native builds require macOS clang.",
    source_relpath="src/main.c",
    binary_name_suffix="",
    builder="clang",
)

