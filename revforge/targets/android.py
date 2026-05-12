"""Android NDK target."""

from . import TargetSpec

TARGET = TargetSpec(
    name="android",
    display="Android NDK",
    description="Harmless local Android NDK project with JNI native validation.",
    source_relpath="app/src/main/cpp/native-lib.cpp",
    binary_name_suffix=".apk",
    builder="android_ndk",
)

