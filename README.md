# RevForge

RevForge is a safe educational reverse engineering CTF challenge generator. It creates procedural terminal-style reverse engineering challenges with local artifacts, private recipes, generated source, binaries, solvers, and writeups for legal training.

## Safety

Generated programs are harmless local validators. They only read their local challenge artifact files and user-provided input. They do not use malware behavior, persistence, credential collection, network callbacks, destructive file operations, privilege escalation, evasion, or real exploitation.

Use RevForge only for legal advanced CTF education and authorized practice.

## Installation

```bash
git clone <revforge-repository>
cd revforge
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Optional Linux toolchains:

```bash
sudo apt update
sudo apt install -y gcc clang mingw-w64
```

WebAssembly builds require emscripten (`emcc`). Android builds require Android Studio or Gradle plus the Android NDK.

## Quick Start

```bash
revforge doctor
revforge new --name baby1 --difficulty baby
revforge new --name medium1 --difficulty medium
revforge new --name firmware_gate --difficulty hard --profile qualifier --style terminal --family terminal_firmware_blob --target elf
revforge new --name finals_boss --difficulty super-hard --profile finals --style terminal --family terminal_hybrid_finals --target elf --competition-mode
revforge audit ./finals_boss
revforge selftest-qualifier
revforge selftest-finals
```

## Terminal-Style Challenges

Terminal style creates realistic local workflows instead of a bare prompt. Generated binaries expose subcommands such as:

```bash
./dist/challenge --help
./dist/challenge info
./dist/challenge verify <candidate>
./dist/challenge check <file>
./dist/challenge inspect <file>
./dist/challenge scan <file>
./dist/challenge run <file>
./dist/challenge unlock <code>
```

`--help` describes the public interface without revealing the answer.

Terminal families:

| Family | Local artifact | Core idea |
| --- | --- | --- |
| `terminal_firmware_blob` | `firmware.blob` | Custom blob format with encoded constants and validation tables. |
| `terminal_license_vm` | `license.dat` | Encoded randomized VM bytecode with decoy blocks and final state checks. |
| `terminal_signal_pipeline` | `signal.dat` | Chunk permutation, byte transforms, lookup tables, and rolling checksums. |
| `terminal_constraints_pack` | `constraints.pack` | Encoded byte constraints with optional z3 solving. |
| `terminal_hybrid_finals` | `capsule.bin` | Finals-class mix of local format parsing, VM bytecode, constraints, transform pipeline, and rolling hash gates. |

Examples:

```bash
revforge new --name firmware_gate --difficulty hard --profile qualifier --style terminal --family terminal_firmware_blob --target elf
revforge new --name vm_license --difficulty super-hard --profile qualifier --style terminal --family terminal_license_vm --target elf
revforge new --name finals_boss --difficulty super-hard --profile finals --style terminal --family terminal_hybrid_finals --target elf --competition-mode
revforge audit ./finals_boss
revforge selftest-qualifier
revforge selftest-finals
```

Example public README content for a terminal challenge:

```text
Files:
- ./dist/firmware_gate
- ./firmware.blob

Usage:
./dist/firmware_gate --help
./dist/firmware_gate verify <candidate>
./dist/firmware_gate check firmware.blob
```

## Profiles

Profiles tune the expected reversing depth:

- `training`: source, recipe, solver, and writeup are included by default.
- `standard`: default simple challenge behavior.
- `qualifier`: qualifier-class terminal reverse engineering, stripped hard and super-hard binaries, encoded constants, neutral decoys, and audit thresholds.
- `finals`: finals-class terminal reverse engineering, larger tables or bytecode, stripped binaries, and stricter audit thresholds.

Default style:

- `baby` and `easy`: `simple`
- `medium`, `hard`, and `super-hard` with `qualifier` or `finals`: `terminal`

## AI-Assisted Generation

AI support is optional. RevForge asks a provider for a validated JSON recipe only. Provider output never becomes arbitrary executable code; RevForge internal templates generate source and binaries.

Provider defaults:

- OpenAI: `REVFORGE_OPENAI_MODEL=gpt-5.1`
- OpenAI documented alternative: `gpt-5.1-codex-mini`
- Anthropic: `REVFORGE_ANTHROPIC_MODEL=claude-sonnet-4-6`
- Anthropic strongest option: `claude-opus-4-7`
- Gemini: `REVFORGE_GEMINI_MODEL=gemini-3.1-pro-preview`
- Gemini stable fallback: `gemini-2.5-pro`

Users can set any provider-supported model through environment variables.

Configure providers with a local environment file or shell exports:

```bash
cp .env.example .env
export REVFORGE_OPENAI_API_KEY="..."
export REVFORGE_OPENAI_MODEL="gpt-5.1"
export REVFORGE_ANTHROPIC_API_KEY="..."
export REVFORGE_ANTHROPIC_MODEL="claude-sonnet-4-6"
export REVFORGE_GEMINI_API_KEY="..."
export REVFORGE_GEMINI_MODEL="gemini-3.1-pro-preview"
export REVFORGE_AI_BASE_URL="https://example.invalid/v1"
export REVFORGE_AI_API_KEY="..."
export REVFORGE_AI_MODEL="compatible-model"
```

Check configuration without printing full keys:

```bash
revforge ai-config
revforge ai-config --quiet
```

AI recipe fields include:

- `profile`
- `style`
- `terminal_commands`
- `artifact_files`
- `family`
- `technique_mix`
- `complexity_budget`

AI recipes are rejected if they request unsafe behavior, real targets, identity references, or fake real-world institutions.

## Flag Formats

Default generated flags use `revforge{...}`.

```bash
revforge new --name default1 --difficulty baby
revforge new --name custom1 --difficulty easy --flag-format "revforge{{{value}}}"
revforge new --name direct --difficulty medium --flag "revforge{custom_value}"
revforge new --name random --difficulty hard --random-flag
revforge new --name decoys --difficulty hard --fake-flags
```

Medium, hard, and super-hard challenges do not include fake flag-shaped decoys by default. Neutral decoy strings are used unless `--fake-flags` is selected.

## Output Modes

Training mode is the default:

```text
challenge_name/
├── README.md
├── metadata.json
├── recipe.json
├── src/main.c
├── build.sh
├── Makefile
├── dist/generated_binary
├── local_artifact
├── solution/solve.py
└── writeup.md
```

Competition mode:

```bash
revforge new --name finals_boss --difficulty super-hard --profile finals --style terminal --family terminal_hybrid_finals --competition-mode
```

Competition mode outputs only public files:

```text
finals_boss/
├── README.md
├── metadata_public.json
├── capsule.bin
└── dist/finals_boss
```

## Audit

RevForge audits generated challenges for:

- Score from 0 to 100 and final grade.
- Profile, style, family, and terminal commands.
- Stripped hard and super-hard binaries.
- Full-answer leaks in source or binary strings.
- Private-file leaks in competition mode.
- Direct full-input comparisons.
- Solver scripts that only print literals.
- Function count, encoded constant count, bytecode length, constraint count, and local artifact count.

Run:

```bash
revforge audit ./challenge_folder
revforge selftest-qualifier
revforge selftest-finals
```

## Targets

| Target | Support |
| --- | --- |
| `elf` | Linux ELF binaries with gcc or clang. |
| `exe` | Windows PE `.exe` builds with `x86_64-w64-mingw32-gcc`. |
| `macho` | Source generation everywhere; native builds require macOS clang. |
| `android` | Harmless local Android NDK project with JNI validation and no permissions. |
| `wasm` | Browser challenge scaffold built with emscripten when `emcc` is installed. |

## Development

```bash
python -m pip install -e ".[dev]"
python -m pytest -v
```

## Disclaimer

RevForge is for legal advanced CTF education only. Do not use it for unauthorized activity, malware development, credential collection, evasion research, or destructive behavior.
