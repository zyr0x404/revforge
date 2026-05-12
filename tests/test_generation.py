from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from revforge.flags import DEFAULT_FLAG_FORMAT
from revforge.generator import generate_challenge
from revforge.recipes import TEMPLATES_BY_DIFFICULTY


@pytest.fixture(autouse=True)
def isolated_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVFORGE_HOME", str(tmp_path / "home"))


def _metadata(path: Path) -> dict:
    return json.loads((path / "metadata.json").read_text(encoding="utf-8"))


def test_challenge_folder_structure_and_branding(tmp_path: Path) -> None:
    result = generate_challenge(
        name="baby1",
        difficulty="baby",
        template="baby_plain",
        out_dir=tmp_path,
        seed=1234,
    )
    challenge = result.challenge_dir

    assert (challenge / "README.md").exists()
    assert (challenge / "metadata.json").exists()
    assert (challenge / "recipe.json").exists()
    assert (challenge / "src" / "main.c").exists()
    assert (challenge / "build.sh").exists()
    assert (challenge / "Makefile").exists()
    assert (challenge / "dist").is_dir()
    assert (challenge / "solution" / "solve.py").exists()
    assert (challenge / "writeup.md").exists()

    assert "Created by zyr0x" in (challenge / "README.md").read_text(encoding="utf-8")
    assert "Created by zyr0x" in (challenge / "src" / "main.c").read_text(encoding="utf-8")
    metadata = _metadata(challenge)
    assert metadata["created_by"] == "zyr0x"
    assert metadata["banner"] == "RevForge challenge - created by zyr0x"


def test_recipe_hash_uniqueness_without_seed(tmp_path: Path) -> None:
    first = generate_challenge(name="one", difficulty="easy", template="easy_xor", out_dir=tmp_path)
    second = generate_challenge(name="two", difficulty="easy", template="easy_xor", out_dir=tmp_path)

    assert first.recipe_hash != second.recipe_hash


def test_default_flag_format_is_zyr0x(tmp_path: Path) -> None:
    result = generate_challenge(name="default", difficulty="baby", out_dir=tmp_path, seed=1)
    metadata = _metadata(result.challenge_dir)

    assert metadata["flag_format"] == DEFAULT_FLAG_FORMAT
    assert metadata["flag"].startswith("zyr0x{")
    assert metadata["flag"].endswith("}")


def test_custom_flag_format_uses_value_placeholder(tmp_path: Path) -> None:
    result = generate_challenge(
        name="custom",
        difficulty="easy",
        template="easy_xor",
        out_dir=tmp_path,
        seed=2,
        flag_format="CTF{{{value}}}",
    )
    metadata = _metadata(result.challenge_dir)

    assert metadata["flag"].startswith("CTF{")
    assert metadata["flag"].endswith("}")


def test_direct_flag_is_preserved(tmp_path: Path) -> None:
    result = generate_challenge(
        name="direct",
        difficulty="medium",
        template="medium_xor_chain",
        out_dir=tmp_path,
        seed=3,
        flag="zyr0x{my_custom_flag}",
    )

    assert _metadata(result.challenge_dir)["flag"] == "zyr0x{my_custom_flag}"


def test_repeated_seed_gives_same_recipe_when_repeat_allowed(tmp_path: Path) -> None:
    first = generate_challenge(
        name="seeded1",
        difficulty="hard",
        template="hard_multistage",
        out_dir=tmp_path,
        seed=444,
        allow_repeat=True,
    )
    second = generate_challenge(
        name="seeded2",
        difficulty="hard",
        template="hard_multistage",
        out_dir=tmp_path,
        seed=444,
        allow_repeat=True,
    )

    assert first.recipe_hash == second.recipe_hash
    assert first.recipe.to_dict() | {"name": second.recipe.name} == second.recipe.to_dict()


def test_no_seed_gives_different_recipe(tmp_path: Path) -> None:
    first = generate_challenge(name="random1", difficulty="medium", template="medium_xor_chain", out_dir=tmp_path)
    second = generate_challenge(name="random2", difficulty="medium", template="medium_xor_chain", out_dir=tmp_path)

    assert first.recipe.seed != second.recipe.seed
    assert first.recipe_hash != second.recipe_hash


def test_competition_mode_hides_private_files(tmp_path: Path) -> None:
    result = generate_challenge(
        name="final",
        difficulty="super-hard",
        template="vm",
        out_dir=tmp_path,
        seed=555,
        competition_mode=True,
    )
    challenge = result.challenge_dir

    assert (challenge / "README.md").exists()
    assert (challenge / "metadata_public.json").exists()
    assert not (challenge / "metadata.json").exists()
    assert not (challenge / "recipe.json").exists()
    assert not (challenge / "src").exists()
    assert not (challenge / "solution").exists()
    assert not (challenge / "writeup.md").exists()


ALL_TEMPLATES = [
    (difficulty, template)
    for difficulty, templates in TEMPLATES_BY_DIFFICULTY.items()
    for template in templates
]


@pytest.mark.parametrize(("difficulty", "template"), ALL_TEMPLATES)
def test_all_templates_generate_valid_files_and_solver(tmp_path: Path, difficulty: str, template: str) -> None:
    result = generate_challenge(
        name=template,
        difficulty=difficulty,
        template=template,
        out_dir=tmp_path,
        seed=9000 + len(template),
        allow_repeat=True,
    )
    challenge = result.challenge_dir

    assert (challenge / "README.md").exists()
    assert (challenge / "metadata.json").exists()
    assert (challenge / "src" / "main.c").exists()
    assert (challenge / "solution" / "solve.py").exists()

    solved = subprocess.run(
        [sys.executable, str(challenge / "solution" / "solve.py")],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    assert solved == _metadata(challenge)["flag"]


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
@pytest.mark.parametrize(("difficulty", "template"), ALL_TEMPLATES)
def test_generated_c_source_compiles_if_gcc_exists(tmp_path: Path, difficulty: str, template: str) -> None:
    result = generate_challenge(
        name=f"compile-{template}",
        difficulty=difficulty,
        template=template,
        out_dir=tmp_path,
        seed=12000 + len(template),
        allow_repeat=True,
    )
    challenge = result.challenge_dir
    output = challenge / "dist" / "challenge"

    subprocess.run(
        [
            "gcc",
            "-std=c11",
            "-O2",
            "-Wall",
            "-Wextra",
            str(challenge / "src" / "main.c"),
            "-o",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert output.exists()
