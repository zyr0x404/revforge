"""Challenge generation orchestration."""

from __future__ import annotations

import hashlib
import json
import secrets
import shutil
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Any

from .flags import DEFAULT_FLAG_FORMAT, resolve_flag
from .builders import build_challenge
from .quality import quality_gate
from .recipes import (
    ChallengeRecipe,
    default_style,
    normalize_difficulty,
    normalize_profile,
    normalize_style,
    normalize_target,
    resolve_template,
)
from .targets import get_target
from .templates.registry import prepare_recipe, render
from .uniqueness import DuplicateRecipeError, RegistryEntry, add_recipe, is_known
from .utils import BANNER, CREATED_BY, c_string, ensure_dir, json_dump, random_identifiers, slugify_name


@dataclass(frozen=True)
class GenerationResult:
    challenge_dir: Path
    recipe: ChallengeRecipe
    recipe_hash: str
    metadata: dict[str, Any]


def generate_challenge(
    *,
    name: str,
    difficulty: str,
    target: str = "elf",
    template: str | None = None,
    out_dir: Path | str = ".",
    seed: int | str | None = None,
    flag: str | None = None,
    random_flag: bool = False,
    flag_format: str | None = None,
    allow_repeat: bool = False,
    competition_mode: bool = False,
    include_source: bool | None = None,
    include_solution: bool | None = None,
    profile: str = "standard",
    style: str | None = None,
    family: str | None = None,
    fake_flags: bool = False,
    fake_flag_count: int = 3,
    fake_flag_style: str = "default",
    ai_recipe: dict[str, Any] | None = None,
) -> GenerationResult:
    """Generate a challenge folder and register its recipe hash."""

    safe_name = slugify_name(name)
    difficulty = normalize_difficulty(difficulty)
    target = normalize_target(target)
    profile = normalize_profile(profile)
    style = normalize_style(style) or default_style(difficulty, profile)
    if template and family:
        raise ValueError("use either --template or --family, not both")
    output_root = Path(out_dir).expanduser().resolve()
    challenge_dir = output_root / safe_name
    if challenge_dir.exists() and any(challenge_dir.iterdir()):
        raise FileExistsError(f"output folder already exists and is not empty: {challenge_dir}")

    explicit_seed = seed is not None
    attempts = 0
    recipe: ChallengeRecipe | None = None
    recipe_hash = ""
    while attempts < 32:
        attempts += 1
        candidate_seed = _seed_value(seed if explicit_seed else None)
        candidate = _create_recipe(
            name=safe_name,
            difficulty=difficulty,
            target=target,
            template=template,
            family=family,
            seed=candidate_seed,
            flag=flag,
            random_flag=random_flag,
            flag_format=flag_format,
            profile=profile,
            style=style,
            fake_flags=fake_flags,
            fake_flag_count=fake_flag_count,
            fake_flag_style=fake_flag_style,
        )
        if ai_recipe:
            _apply_ai_overrides(candidate, ai_recipe)
        candidate_hash = candidate.recipe_hash()
        if allow_repeat or not is_known(candidate_hash):
            recipe = candidate
            recipe_hash = candidate_hash
            break
        if explicit_seed:
            raise DuplicateRecipeError(
                "that seed/template/flag combination was already generated; use --allow-repeat or change --seed"
            )
    if recipe is None:
        raise DuplicateRecipeError("could not generate a unique recipe after 32 attempts")

    include_source_final = True if competition_mode else ((not competition_mode) if include_source is None else include_source)
    include_solution_final = False if competition_mode else ((not competition_mode) if include_solution is None else include_solution)

    ensure_dir(challenge_dir)
    _write_challenge_files(
        challenge_dir=challenge_dir,
        recipe=recipe,
        recipe_hash=recipe_hash,
        competition_mode=competition_mode,
        include_source=include_source_final,
        include_solution=include_solution_final,
    )

    if include_source_final and (target in {"elf", "exe", "macho"} or competition_mode):
        ok, message = build_challenge(challenge_dir)
        if not ok and competition_mode:
            raise RuntimeError(f"competition-mode build failed: {message}")
    if competition_mode:
        binary_name = _binary_name(recipe.name, recipe.target)
        if not (challenge_dir / "dist" / binary_name).exists():
            raise RuntimeError("competition-mode export requires a built binary in dist/")

    quality_gate(challenge_dir, recipe)

    if competition_mode:
        _finalize_competition_export(challenge_dir)

    metadata = load_metadata(challenge_dir)
    add_recipe(
        RegistryEntry(
            recipe_hash=recipe_hash,
            name=recipe.name,
            difficulty=recipe.difficulty,
            target=recipe.target,
            template=recipe.template_family,
            seed=recipe.seed,
        )
    )
    return GenerationResult(challenge_dir=challenge_dir, recipe=recipe, recipe_hash=recipe_hash, metadata=metadata)


def load_metadata(challenge_dir: Path | str) -> dict[str, Any]:
    path = Path(challenge_dir)
    metadata_path = path / "metadata.json"
    if not metadata_path.exists():
        metadata_path = path / "metadata_public.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"no metadata.json or metadata_public.json found in {path}")
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def _seed_value(seed: int | str | None) -> int:
    if seed is None:
        return secrets.randbits(64)
    if isinstance(seed, int):
        return seed
    raw = str(seed).strip()
    try:
        return int(raw, 0)
    except ValueError:
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return int(digest[:16], 16)


def _create_recipe(
    *,
    name: str,
    difficulty: str,
    target: str,
    template: str | None,
    family: str | None,
    seed: int,
    flag: str | None,
    random_flag: bool,
    flag_format: str | None,
    profile: str,
    style: str,
    fake_flags: bool,
    fake_flag_count: int,
    fake_flag_style: str,
) -> ChallengeRecipe:
    rng = Random(seed)
    selected_template = resolve_template(difficulty, family or template, rng, style=style, profile=profile)
    if selected_template == "terminal_hybrid_finals" and (difficulty != "super-hard" or profile != "finals"):
        raise ValueError("terminal_hybrid_finals requires --difficulty super-hard --profile finals")
    selected_flag, selected_format = resolve_flag(
        rng,
        flag=flag,
        random_flag=random_flag,
        flag_format=flag_format or DEFAULT_FLAG_FORMAT,
    )
    function_names = random_identifiers(
        rng,
        [
            "check",
            "stage",
            "mix",
            "decode",
            "guard",
            "noise",
            "vm",
            "step",
            "accept",
            "hash",
            "table",
            "gate",
            "fold",
            "branch",
            "constraint",
            "recover",
            "dispatch",
            "scramble",
            "oracle",
            "mask",
        ],
        prefix="rf",
    )
    variable_names = random_identifiers(
        rng,
        ["candidate", "index", "state", "accumulator", "cursor", "value"],
        prefix="rv",
    )
    recipe = ChallengeRecipe(
        name=name,
        difficulty=difficulty,
        target=target,
        template_family=selected_template,
        seed=seed,
        flag=selected_flag,
        flag_format=selected_format,
        function_names=function_names,
        variable_names=variable_names,
        created_by=CREATED_BY,
        profile=profile,
        style=style,
        family=family or selected_template,
        fake_flags_enabled=fake_flags,
        fake_flag_count=_normalize_fake_flag_count(fake_flag_count if fake_flags else 0),
        fake_flag_style=_normalize_fake_flag_style(fake_flag_style),
    )
    return prepare_recipe(recipe, rng)


def _normalize_fake_flag_count(value: int) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("--fake-flag-count must be an integer") from exc
    if count < 0 or count > 32:
        raise ValueError("--fake-flag-count must be between 0 and 32")
    return count


def _normalize_fake_flag_style(value: str | None) -> str:
    selected = (value or "default").strip().lower().replace("_", "-")
    if selected not in {"default", "generic", "ctf", "mixed"}:
        raise ValueError("--fake-flag-style must be one of default, generic, ctf, mixed")
    return selected


def _apply_ai_overrides(recipe: ChallengeRecipe, ai_recipe: dict[str, Any]) -> None:
    story = ai_recipe.get("story")
    if isinstance(story, str) and story.strip():
        recipe.story = story.strip()
    fake_strings = ai_recipe.get("fake_strings")
    if isinstance(fake_strings, list):
        clean = [str(item).strip() for item in fake_strings if str(item).strip()]
        if clean:
            recipe.fake_strings = clean[:8]
    theme = ai_recipe.get("theme")
    requested_features = ai_recipe.get("requested_features")
    for key in ("profile", "style", "family", "terminal_commands", "artifact_files", "technique_mix", "complexity_budget"):
        if key in ai_recipe:
            recipe.constants[f"ai_{key}"] = ai_recipe[key]
    recipe.constants["ai_theme"] = theme if isinstance(theme, str) else ""
    recipe.constants["ai_requested_features"] = requested_features if isinstance(requested_features, list) else []
    recipe.constants["ai_function_name_style"] = ai_recipe.get("function_name_style", "")
    recipe.constants["ai_variable_name_style"] = ai_recipe.get("variable_name_style", "")


def _write_challenge_files(
    *,
    challenge_dir: Path,
    recipe: ChallengeRecipe,
    recipe_hash: str,
    competition_mode: bool,
    include_source: bool,
    include_solution: bool,
) -> None:
    target = get_target(recipe.target)
    rendered = render(recipe)
    binary_name = _binary_name(recipe.name, recipe.target)
    metadata = _metadata(recipe, recipe_hash, binary_name, include_source, include_solution, competition_mode)

    ensure_dir(challenge_dir / "dist")
    _write_readme(challenge_dir / "README.md", recipe, metadata, competition_mode)

    for relpath, payload in (rendered.artifacts or {}).items():
        artifact_path = challenge_dir / Path(relpath).name
        artifact_path.write_bytes(payload)

    if competition_mode:
        json_dump(challenge_dir / "metadata.json", metadata)
        json_dump(challenge_dir / "recipe.json", {**recipe.to_dict(), "recipe_hash": recipe_hash})
    else:
        json_dump(challenge_dir / "metadata.json", metadata)
        json_dump(challenge_dir / "recipe.json", {**recipe.to_dict(), "recipe_hash": recipe_hash})

    if include_source:
        if recipe.target == "android":
            _write_android_project(challenge_dir, recipe, rendered.android_source)
        else:
            source_path = challenge_dir / target.source_relpath
            ensure_dir(source_path.parent)
            source_path.write_text(rendered.cli_source, encoding="utf-8")
            if recipe.target == "wasm":
                _write_wasm_index(challenge_dir, recipe)
        _write_build_files(challenge_dir, recipe, binary_name)

    if include_solution:
        ensure_dir(challenge_dir / "solution")
        solve_path = challenge_dir / "solution" / "solve.py"
        solve_path.write_text(rendered.solution, encoding="utf-8")
        solve_path.chmod(0o755)
        (challenge_dir / "writeup.md").write_text(rendered.writeup, encoding="utf-8")


def _metadata(
    recipe: ChallengeRecipe,
    recipe_hash: str,
    binary_name: str,
    include_source: bool,
    include_solution: bool,
    competition_mode: bool,
) -> dict[str, Any]:
    return {
        "name": recipe.name,
        "difficulty": recipe.difficulty,
        "target": recipe.target,
        "template": recipe.template_family,
        "profile": recipe.profile,
        "style": recipe.style,
        "family": recipe.family or recipe.template_family,
        "seed": recipe.seed,
        "flag": recipe.flag,
        "flag_format": recipe.flag_format,
        "recipe_hash": recipe_hash,
        "binary_name": binary_name,
        "created_by": CREATED_BY,
        "banner": BANNER,
        "has_source": include_source,
        "has_solution": include_solution,
        "competition_mode": competition_mode,
        "bytecode_length": int(recipe.constants.get("bytecode_length", 0)),
        "constraint_count": int(recipe.constants.get("constraint_count", 0)),
        "encoded_constant_count": int(recipe.constants.get("encoded_constant_count", 0)),
        "local_artifact_count": int(recipe.constants.get("artifact_count", len(recipe.artifact_files))),
        "terminal_commands": recipe.terminal_commands,
        "artifact_files": recipe.artifact_files,
        "technique_mix": recipe.technique_mix,
        "complexity_budget": recipe.complexity_budget,
        "fake_flags_enabled": recipe.fake_flags_enabled,
        "fake_flag_count": len(recipe.fake_flags),
        "fake_flag_style": recipe.fake_flag_style,
        "validation_family": recipe.checker_type,
        "safety": "Generated program is harmless and local-only. It only reads its local challenge artifacts and user-provided input.",
    }


def _public_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    public = dict(metadata)
    public.pop("flag", None)
    public["has_solution"] = False
    public["has_source"] = False
    return public


def _finalize_competition_export(challenge_dir: Path) -> None:
    metadata = load_metadata(challenge_dir)
    public = _public_metadata(metadata)
    json_dump(challenge_dir / "metadata_public.json", public)
    for relpath in ("metadata.json", "recipe.json", "build.sh", "Makefile", "writeup.md", "index.html"):
        path = challenge_dir / relpath
        if path.exists():
            path.unlink()
    for relpath in ("src", "solution", "app"):
        path = challenge_dir / relpath
        if path.exists():
            shutil.rmtree(path)


def _binary_name(name: str, target: str) -> str:
    if target == "exe":
        return f"{name}.exe"
    if target == "android":
        return f"{name}.apk"
    if target == "wasm":
        return "challenge.wasm"
    return name


def _write_readme(path: Path, recipe: ChallengeRecipe, metadata: dict[str, Any], competition_mode: bool) -> None:
    mode_note = (
        "This is a competition-mode export. Source, recipe, and solution files are intentionally omitted."
        if competition_mode
        else "This educational bundle includes source, recipe metadata, and a solver for local training."
    )
    if recipe.style == "terminal":
        binary = metadata["binary_name"]
        artifacts = "\n".join(f"- ./{name}" for name in recipe.artifact_files)
        commands = "\n".join(_usage_lines(recipe, binary))
        text = f"""# {recipe.name}

## Files

- ./dist/{binary}
{artifacts}
{"- ./metadata_public.json" if competition_mode else "- ./metadata.json"}

## Usage

```bash
{commands}
```

## Challenge

- Difficulty: `{recipe.difficulty}`
- Profile: `{recipe.profile}`
- Style: `{recipe.style}`
- Family: `{recipe.family or recipe.template_family}`
- Target: `{recipe.target}`

{recipe.story}

{mode_note}

## Safety

This challenge is harmless and local only. The generated program reads only its local challenge artifact files and user-provided input. It does not use networking, persistence, credential collection, privilege escalation, destructive behavior, evasion, or real exploitation.
"""
        path.write_text(text, encoding="utf-8")
        return

    text = f"""# {recipe.name}

Created by {CREATED_BY}

{BANNER}

## Challenge

- Difficulty: `{recipe.difficulty}`
- Profile: `{recipe.profile}`
- Style: `{recipe.style}`
- Target: `{recipe.target}`
- Template: `{recipe.template_family}`
- Recipe hash: `{metadata["recipe_hash"]}`

{recipe.story}

{mode_note}

## Safety

This challenge is harmless and local only. The generated program reads user-provided input, checks it in memory, and prints success or failure. It does not use networking, persistence, credential collection, privilege escalation, destructive behavior, evasion, or real exploitation.

## Build

Run:

```bash
revforge build .
```

Or use the generated `build.sh` when source files are included.
"""
    path.write_text(text, encoding="utf-8")


def _usage_lines(recipe: ChallengeRecipe, binary: str) -> list[str]:
    exe = f"./dist/{binary}"
    artifact = recipe.artifact_files[0] if recipe.artifact_files else "artifact.bin"
    family = recipe.family or recipe.template_family
    if family in {"terminal_firmware_blob", "qualifier_state_machine"}:
        return [f"{exe} --help", f"{exe} verify <candidate>", f"{exe} check {artifact}"]
    if family in {"terminal_license_vm", "qualifier_vm"}:
        return [f"{exe} --help", f"{exe} info", f"{exe} verify <key>", f"{exe} check {artifact}"]
    if family in {"terminal_signal_pipeline", "qualifier_transform_pipeline"}:
        return [f"{exe} --help", f"{exe} scan {artifact}", f"{exe} verify <candidate>"]
    if family in {"terminal_constraints_pack", "qualifier_constraints"}:
        return [f"{exe} --help", f"{exe} verify <candidate>", f"{exe} check {artifact}"]
    return [f"{exe} --help", f"{exe} info", f"{exe} verify <candidate>", f"{exe} check {artifact}"]


def _write_build_files(challenge_dir: Path, recipe: ChallengeRecipe, binary_name: str) -> None:
    build_sh = _build_script(recipe, binary_name)
    build_path = challenge_dir / "build.sh"
    build_path.write_text(build_sh, encoding="utf-8")
    build_path.chmod(0o755)
    (challenge_dir / "Makefile").write_text(_makefile(recipe, binary_name), encoding="utf-8")


def _build_script(recipe: ChallengeRecipe, binary_name: str) -> str:
    if recipe.target == "elf":
        strip_flag = " -s" if recipe.difficulty in {"hard", "super-hard"} else ""
        return f"""#!/usr/bin/env bash
# Created by {CREATED_BY}
set -euo pipefail
mkdir -p dist
CC="${{CC:-gcc}}"
"$CC" -std=c11 -O2 -Wall -Wextra{strip_flag} src/main.c -o dist/{binary_name}
echo "built dist/{binary_name}"
"""
    if recipe.target == "exe":
        return f"""#!/usr/bin/env bash
# Created by {CREATED_BY}
set -euo pipefail
if ! command -v x86_64-w64-mingw32-gcc >/dev/null 2>&1; then
  echo "missing mingw-w64 compiler. Install with:"
  echo "sudo apt update && sudo apt install -y mingw-w64"
  exit 1
fi
mkdir -p dist
x86_64-w64-mingw32-gcc -O2 -Wall -Wextra{" -s" if recipe.difficulty in {"hard", "super-hard"} else ""} src/main.c -o dist/{binary_name}
echo "built dist/{binary_name}"
"""
    if recipe.target == "macho":
        return f"""#!/usr/bin/env bash
# Created by {CREATED_BY}
set -euo pipefail
if [ "$(uname -s)" != "Darwin" ]; then
  echo "Mach-O building requires macOS or an advanced cross-compiler setup."
  echo "Source generation is supported on this host."
  exit 1
fi
mkdir -p dist
clang -std=c11 -O2 -Wall -Wextra{" -s" if recipe.difficulty in {"hard", "super-hard"} else ""} src/main.c -o dist/{binary_name}
echo "built dist/{binary_name}"
"""
    if recipe.target == "wasm":
        return f"""#!/usr/bin/env bash
# Created by {CREATED_BY}
set -euo pipefail
if ! command -v emcc >/dev/null 2>&1; then
  echo "missing emscripten compiler: emcc"
  exit 1
fi
mkdir -p dist
emcc src/main.c -O2 -s WASM=1 -s INVOKE_RUN=0 -s EXPORTED_RUNTIME_METHODS='["callMain"]' -o dist/challenge.js
cp index.html dist/index.html
echo "built dist/challenge.wasm and dist/index.html"
"""
    if recipe.target == "android":
        return f"""#!/usr/bin/env bash
# Created by {CREATED_BY}
set -euo pipefail
if ! command -v gradle >/dev/null 2>&1; then
  echo "missing gradle. Build with Android Studio or install Gradle."
  exit 1
fi
if [ -z "${{ANDROID_NDK_HOME:-${{ANDROID_NDK_ROOT:-}}}}" ]; then
  echo "missing Android NDK. Set ANDROID_NDK_HOME or build with Android Studio."
  exit 1
fi
gradle assembleDebug
mkdir -p dist
if [ -f app/build/outputs/apk/debug/app-debug.apk ]; then
  cp app/build/outputs/apk/debug/app-debug.apk dist/{binary_name}
fi
echo "build complete"
"""
    raise ValueError(f"unsupported target {recipe.target}")


def _makefile(recipe: ChallengeRecipe, binary_name: str) -> str:
    if recipe.target == "elf":
        strip_flag = " -s" if recipe.difficulty in {"hard", "super-hard"} else ""
        return f"""# Created by {CREATED_BY}
CC ?= gcc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra{strip_flag}

.PHONY: all clean
all:
\tmkdir -p dist
\t$(CC) $(CFLAGS) src/main.c -o dist/{binary_name}

clean:
\trm -rf dist
"""
    if recipe.target == "exe":
        strip_flag = " -s" if recipe.difficulty in {"hard", "super-hard"} else ""
        return f"""# Created by {CREATED_BY}
CC ?= x86_64-w64-mingw32-gcc
CFLAGS ?= -O2 -Wall -Wextra{strip_flag}

.PHONY: all clean
all:
\tmkdir -p dist
\t$(CC) $(CFLAGS) src/main.c -o dist/{binary_name}

clean:
\trm -rf dist
"""
    if recipe.target == "macho":
        strip_flag = " -s" if recipe.difficulty in {"hard", "super-hard"} else ""
        return f"""# Created by {CREATED_BY}
CC ?= clang
CFLAGS ?= -std=c11 -O2 -Wall -Wextra{strip_flag}

.PHONY: all clean
all:
\t@if [ "$$(uname -s)" != "Darwin" ]; then echo "Mach-O building requires macOS or an advanced cross-compiler setup."; exit 1; fi
\tmkdir -p dist
\t$(CC) $(CFLAGS) src/main.c -o dist/{binary_name}

clean:
\trm -rf dist
"""
    if recipe.target == "wasm":
        return f"""# Created by {CREATED_BY}
EMCC ?= emcc

.PHONY: all clean
all:
\tmkdir -p dist
\t$(EMCC) src/main.c -O2 -s WASM=1 -s INVOKE_RUN=0 -s EXPORTED_RUNTIME_METHODS='["callMain"]' -o dist/challenge.js
\tcp index.html dist/index.html

clean:
\trm -rf dist
"""
    if recipe.target == "android":
        return f"""# Created by {CREATED_BY}
.PHONY: all clean
all:
\tgradle assembleDebug
\tmkdir -p dist
\t@if [ -f app/build/outputs/apk/debug/app-debug.apk ]; then cp app/build/outputs/apk/debug/app-debug.apk dist/{binary_name}; fi

clean:
\trm -rf dist app/build .gradle
"""
    raise ValueError(f"unsupported target {recipe.target}")


def _write_wasm_index(challenge_dir: Path, recipe: ChallengeRecipe) -> None:
    (challenge_dir / "index.html").write_text(
        f"""<!-- Created by {CREATED_BY} -->
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{recipe.name} - RevForge</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; background: #101418; color: #f4f7fb; }}
    input, button {{ font: inherit; padding: .6rem .75rem; }}
    button {{ cursor: pointer; }}
    pre {{ background: #05070a; padding: 1rem; min-height: 8rem; white-space: pre-wrap; }}
  </style>
</head>
<body>
  <h1>{recipe.name}</h1>
  <p>{BANNER}</p>
  <input id="candidate" autocomplete="off" placeholder="flag">
  <button id="run">Check</button>
  <pre id="output"></pre>
  <script>
    const output = document.getElementById("output");
    var Module = {{
      print: text => output.textContent += text + "\\n",
      printErr: text => output.textContent += text + "\\n",
      noInitialRun: true
    }};
    document.getElementById("run").addEventListener("click", () => {{
      output.textContent = "";
      if (Module.callMain) Module.callMain([document.getElementById("candidate").value]);
    }});
  </script>
  <script src="challenge.js"></script>
</body>
</html>
""",
        encoding="utf-8",
    )


def _write_android_project(challenge_dir: Path, recipe: ChallengeRecipe, native_source: str) -> None:
    files = {
        "settings.gradle": f"""// Created by {CREATED_BY}
pluginManagement {{
    repositories {{
        google()
        mavenCentral()
        gradlePluginPortal()
    }}
}}
dependencyResolutionManagement {{ repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS); repositories {{ google(); mavenCentral() }} }}
rootProject.name = "{recipe.name}"
include ":app"
""",
        "build.gradle": f"""// Created by {CREATED_BY}
plugins {{
    id "com.android.application" version "8.5.2" apply false
}}
""",
        "app/build.gradle": f"""// Created by {CREATED_BY}
plugins {{
    id "com.android.application"
}}

android {{
    namespace "com.revforge.challenge"
    compileSdk 35

    defaultConfig {{
        applicationId "com.revforge.challenge"
        minSdk 23
        targetSdk 35
        versionCode 1
        versionName "1.0"
        externalNativeBuild {{
            cmake {{
                cppFlags "-std=c++17"
            }}
        }}
    }}

    externalNativeBuild {{
        cmake {{
            path "src/main/cpp/CMakeLists.txt"
        }}
    }}
}}
""",
        "app/src/main/AndroidManifest.xml": f"""<!-- Created by {CREATED_BY} -->
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application
        android:theme="@style/AppTheme"
        android:label="{recipe.name}"
        android:allowBackup="false"
        android:supportsRtl="true">
        <activity android:name=".MainActivity" android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
""",
        "app/src/main/res/values/styles.xml": f"""<!-- Created by {CREATED_BY} -->
<resources>
    <style name="AppTheme" parent="android:style/Theme.Material.Light.NoActionBar" />
</resources>
""",
        "app/src/main/java/com/revforge/challenge/MainActivity.java": _android_activity(recipe),
        "app/src/main/cpp/CMakeLists.txt": f"""# Created by {CREATED_BY}
cmake_minimum_required(VERSION 3.22.1)
project(revforge_challenge)
add_library(revforge_challenge SHARED native-lib.cpp)
find_library(log-lib log)
target_link_libraries(revforge_challenge ${{log-lib}})
""",
        "app/src/main/cpp/native-lib.cpp": native_source,
    }
    for relpath, content in files.items():
        path = challenge_dir / relpath
        ensure_dir(path.parent)
        path.write_text(content, encoding="utf-8")


def _android_activity(recipe: ChallengeRecipe) -> str:
    return f"""// Created by {CREATED_BY}
package com.revforge.challenge;

import android.app.Activity;
import android.os.Bundle;
import android.graphics.Color;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {{
    static {{
        System.loadLibrary("revforge_challenge");
    }}

    public native String banner();
    public native boolean checkFlag(String candidate);

    @Override
    protected void onCreate(Bundle savedInstanceState) {{
        super.onCreate(savedInstanceState);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setGravity(Gravity.CENTER);
        layout.setPadding(32, 32, 32, 32);

        TextView title = new TextView(this);
        title.setText(banner());
        title.setTextSize(18);
        title.setTextColor(Color.rgb(20, 24, 28));

        EditText input = new EditText(this);
        input.setHint("flag");
        input.setSingleLine(true);

        TextView result = new TextView(this);
        result.setText("");
        result.setTextSize(16);

        Button button = new Button(this);
        button.setText("Check");
        button.setOnClickListener(v -> {{
            boolean ok = checkFlag(input.getText().toString());
            result.setText(ok ? {c_string(recipe.success_message)} : {c_string(recipe.failure_message)});
        }});

        layout.addView(title);
        layout.addView(input);
        layout.addView(button);
        layout.addView(result);
        setContentView(layout);
    }}
}}
"""


def clean_challenge(challenge_dir: Path | str) -> list[Path]:
    path = Path(challenge_dir)
    removed: list[Path] = []
    for rel in ("dist", "build", ".gradle", "app/build"):
        target = path / rel
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            removed.append(target)
    ensure_dir(path / "dist")
    return removed
