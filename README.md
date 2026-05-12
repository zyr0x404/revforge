# RevForge

Created by zyr0x

```text
 ____             _____
|  _ \ _____   __|  ___|__  _ __ __ _  ___
| |_) / _ \ \ / /| |_ / _ \| '__/ _` |/ _ \
|  _ <  __/\ V / |  _| (_) | | | (_| |  __/
|_| \_\___| \_/  |_|  \___/|_|  \__, |\___|
                                |___/
```

RevForge is a safe educational reverse engineering CTF challenge generator. It creates harmless crackme-style training challenges for legal CTF practice and varies recipes procedurally so repeated runs do not just reuse a fixed set of examples.

## Safety Statement

RevForge does not generate malware, persistence, credential collection, network callbacks, privilege escalation, destructive behavior, or antivirus evasion. Generated binaries are local training programs that read user input and print success or failure.

Use RevForge only for legal CTF education, training labs, classrooms, and authorized practice.

## Installation

```bash
git clone https://github.com/zyr0x/revforge.git
cd revforge
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

Optional compilers:

```bash
sudo apt update
sudo apt install -y gcc clang mingw-w64
```

WebAssembly builds require emscripten (`emcc`). Android builds require Android Studio or Gradle plus the Android NDK.

## Quick Start

```bash
revforge doctor
revforge new --name baby1 --difficulty baby
revforge build ./baby1
./baby1/dist/baby1
```

More examples:

```bash
revforge new --name xor1 --difficulty medium --template xor
revforge new --name boss1 --difficulty super-hard --target elf
revforge new --name win1 --difficulty easy --target exe
revforge new --name android1 --difficulty medium --target android
revforge new --name web1 --difficulty easy --target wasm
revforge batch --count 20 --difficulty easy --out ./generated
```

## Flag Options

Default generated flags use `zyr0x{...}`.

```bash
revforge new --name default1 --difficulty baby
revforge new --name custom_format --difficulty easy --flag-format "CTF{{{value}}}"
revforge new --name direct --difficulty medium --flag "zyr0x{my_custom_flag}"
revforge new --name random --difficulty hard --random-flag
```

## Uniqueness

Every challenge is generated from a `ChallengeRecipe` containing the template, difficulty, target, seed, flag, constants, fake strings, transformations, function names, variable names, story text, and checker logic. RevForge saves a recipe hash in `metadata.json` and records generated hashes in `~/.revforge/history.json`.

Use `--seed` for reproducible generation. If the same deterministic recipe already exists, RevForge refuses it unless `--allow-repeat` is supplied. Without `--seed`, RevForge uses secure randomness and regenerates if it hits a known recipe hash.

## Difficulties

| Difficulty | Design |
| --- | --- |
| baby | Beginner-friendly checks such as plain compare, reverse compare, and Caesar-shifted bytes. |
| easy | Basic reverse engineering with XOR arrays, split strings, and arithmetic checks. |
| medium | Ghidra/gdb practice with chained XOR, chunked functions, and modular arithmetic validators. |
| hard | State-machine and multi-stage encoded-table validation with decoy logic. |
| super-hard | Safe toy VM bytecode checker with generated instruction streams and a real solver unless competition mode is enabled. |

## Targets

| Target | Support |
| --- | --- |
| `elf` | Linux ELF binaries with gcc or clang on Kali, Ubuntu, Debian, and WSL. |
| `exe` | Windows PE `.exe` cross-builds with `x86_64-w64-mingw32-gcc`; missing compiler message includes `sudo apt update && sudo apt install -y mingw-w64`. |
| `macho` | Source generation everywhere; native Mach-O builds require macOS clang. |
| `android` | Android Gradle project with JNI `native-lib.cpp`; no permissions, no network, local-only UI. |
| `wasm` | Browser challenge scaffold built with emscripten when `emcc` is installed. |

## Generated Folder Structure

```text
challenge_name/
├── README.md
├── metadata.json
├── recipe.json
├── src/
│   └── main.c
├── build.sh
├── Makefile
├── dist/
├── solution/
│   └── solve.py
└── writeup.md
```

Android targets generate a Gradle project with `app/src/main/cpp/native-lib.cpp`. WASM targets also include `index.html`.

Competition mode:

```bash
revforge new --name final1 --difficulty hard --competition-mode
```

Competition mode omits private source, recipes, solutions, and writeups, and writes `metadata_public.json`.

## Example Output

```text
RevForge Challenge Generated
Name           xor1
Difficulty     medium
Target         elf
Template       medium_xor_chain
Seed           17787028097554025891
Flag format    zyr0x{{{value}}}
Output folder  /work/xor1
Created by     zyr0x
```

## Commands

```bash
revforge list-templates
revforge list-targets
revforge doctor
revforge build ./challenge_folder
revforge clean ./challenge_folder
revforge package ./challenge_folder --zip
```

## Development

```bash
python -m pip install -e ".[dev]"
pytest
```

## Roadmap

- Add more template families for each difficulty.
- Add richer WASM exports for browser-native validation.
- Add optional Docker build profiles for reproducible Linux releases.
- Add plugin discovery for external template packages.
- Add CI smoke builds for compilers available on each runner.

## Contributing

Contributions are welcome when they preserve RevForge safety rules. New templates must be harmless, local-only, deterministic under `--seed`, covered by tests, and documented.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SAFETY.md](SAFETY.md).

## Disclaimer

RevForge is for legal CTF education only. Do not use it for unauthorized activity, malware development, credential collection, evasion research, or destructive behavior.

