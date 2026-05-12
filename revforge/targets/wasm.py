"""WebAssembly target."""

from . import TargetSpec

TARGET = TargetSpec(
    name="wasm",
    display="WebAssembly",
    description="Browser challenge compiled with emscripten when emcc is installed.",
    source_relpath="src/main.c",
    binary_name_suffix=".wasm",
    builder="wasm",
)

