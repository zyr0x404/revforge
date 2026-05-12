"""Windows PE target."""

from . import TargetSpec

TARGET = TargetSpec(
    name="exe",
    display="Windows EXE",
    description="Windows PE crackme built from Linux with mingw-w64 when available.",
    source_relpath="src/main.c",
    binary_name_suffix=".exe",
    builder="mingw",
)

