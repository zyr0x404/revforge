# Contributing

Created by zyr0x

Thanks for improving RevForge. Keep changes focused, testable, and aligned with the safety policy.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e ".[dev]"
pytest
```

## Template Rules

New templates must:

- Generate different recipes through randomized constants, names, fake strings, stories, and checker logic.
- Be reproducible with `--seed`.
- Produce only harmless local crackme behavior.
- Include `Created by zyr0x` in generated source files.
- Include a real `solution/solve.py` unless competition mode omits it.
- Add tests that exercise the new template.

## Target Rules

Target support must be honest. If a toolchain is missing or cross-compilation is not generally available, report that clearly in `doctor` and build errors.

## Pull Request Checklist

- `pytest` passes.
- New behavior is documented.
- Safety rules are preserved.
- Generated metadata includes `created_by: "zyr0x"`.

