from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from revforge.cli import main as cli_main
from revforge.flags import DEFAULT_FLAG_FORMAT
from revforge.generator import generate_challenge
from revforge.quality import audit_challenge
from revforge.recipes import TEMPLATES_BY_DIFFICULTY


@pytest.fixture(autouse=True)
def isolated_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVFORGE_HOME", str(tmp_path / "home"))


def _metadata(path: Path) -> dict:
    return json.loads((path / "metadata.json").read_text(encoding="utf-8"))


def _solve(challenge: Path) -> str:
    return subprocess.run(
        [sys.executable, str(challenge / "solution" / "solve.py")],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def _tracked_text() -> str:
    files = subprocess.run(["git", "ls-files"], text=True, capture_output=True, check=True).stdout.splitlines()
    chunks = []
    for relpath in files:
        path = Path(relpath)
        try:
            chunks.append(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
    return "\n".join(chunks)


def _profile_for_template(template: str) -> str:
    return "finals" if template == "terminal_hybrid_finals" else "standard"


def _style_for_template(template: str) -> str | None:
    return "terminal" if template.startswith("terminal_") or template.startswith("qualifier_") else None


def test_no_identity_terms_in_tracked_files() -> None:
    text = _tracked_text()
    banned = [
        "KO" + "SCTF",
        "S" + "HC",
        "Koso" + "vo",
        "Sw" + "iss",
        "scho" + "ol",
        "te" + "am",
        "coun" + "try",
        "zy" + "r0x",
    ]
    for term in banned:
        assert term not in text


def test_challenge_folder_structure_and_branding(tmp_path: Path) -> None:
    result = generate_challenge(
        name="baby1",
        difficulty="baby",
        template="baby_strings",
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
    assert (challenge / "dist" / "baby1").exists()
    assert (challenge / "solution" / "solve.py").exists()
    assert (challenge / "writeup.md").exists()

    assert "Created by RevForge" in (challenge / "README.md").read_text(encoding="utf-8")
    assert "Created by RevForge" in (challenge / "src" / "main.c").read_text(encoding="utf-8")
    metadata = _metadata(challenge)
    assert metadata["created_by"] == "RevForge"
    assert metadata["banner"] == "RevForge challenge"


def test_recipe_hash_uniqueness_without_seed(tmp_path: Path) -> None:
    first = generate_challenge(name="one", difficulty="easy", template="easy_xor_chunks", out_dir=tmp_path)
    second = generate_challenge(name="two", difficulty="easy", template="easy_xor_chunks", out_dir=tmp_path)

    assert first.recipe_hash != second.recipe_hash


def test_default_flag_format_is_generic(tmp_path: Path) -> None:
    result = generate_challenge(name="default", difficulty="baby", out_dir=tmp_path, seed=1)
    metadata = _metadata(result.challenge_dir)

    assert metadata["flag_format"] == DEFAULT_FLAG_FORMAT
    assert metadata["flag"].startswith("revforge{")
    assert metadata["flag"].endswith("}")


def test_custom_flag_format_uses_generic_placeholder(tmp_path: Path) -> None:
    result = generate_challenge(
        name="custom",
        difficulty="easy",
        template="easy_xor_chunks",
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
        template="medium_multi_stage",
        out_dir=tmp_path,
        seed=3,
        flag="revforge{custom_value}",
    )

    assert _metadata(result.challenge_dir)["flag"] == "revforge{custom_value}"


def test_repeated_seed_gives_same_recipe_when_repeat_allowed(tmp_path: Path) -> None:
    first = generate_challenge(
        name="seeded1",
        difficulty="hard",
        template="hard_encoded_table",
        out_dir=tmp_path,
        seed=444,
        allow_repeat=True,
    )
    second = generate_challenge(
        name="seeded2",
        difficulty="hard",
        template="hard_encoded_table",
        out_dir=tmp_path,
        seed=444,
        allow_repeat=True,
    )

    assert first.recipe_hash == second.recipe_hash
    assert first.recipe.to_dict() | {"name": second.recipe.name} == second.recipe.to_dict()


def test_no_seed_gives_different_recipe(tmp_path: Path) -> None:
    first = generate_challenge(name="random1", difficulty="medium", template="medium_multi_stage", out_dir=tmp_path)
    second = generate_challenge(name="random2", difficulty="medium", template="medium_multi_stage", out_dir=tmp_path)

    assert first.recipe.seed != second.recipe.seed
    assert first.recipe_hash != second.recipe_hash


def test_competition_mode_hides_private_files_and_keeps_binary(tmp_path: Path) -> None:
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
    assert (challenge / "dist" / "final").exists()
    assert not (challenge / "metadata.json").exists()
    assert not (challenge / "recipe.json").exists()
    assert not (challenge / "src").exists()
    assert not (challenge / "solution").exists()
    assert not (challenge / "writeup.md").exists()
    assert not (challenge / "build.sh").exists()
    assert not (challenge / "Makefile").exists()


def test_env_is_ignored_and_example_exists() -> None:
    assert Path(".env.example").exists()
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert ".env" in gitignore
    assert "!.env.example" in gitignore


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
        profile=_profile_for_template(template),
        style=_style_for_template(template),
        out_dir=tmp_path,
        seed=9000 + len(template),
        allow_repeat=True,
    )
    challenge = result.challenge_dir

    assert (challenge / "README.md").exists()
    assert (challenge / "metadata.json").exists()
    assert (challenge / "src" / "main.c").exists()
    assert (challenge / "solution" / "solve.py").exists()

    assert _solve(challenge) == _metadata(challenge)["flag"]


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
@pytest.mark.parametrize(("difficulty", "template"), ALL_TEMPLATES)
def test_generated_c_source_compiles_if_gcc_exists(tmp_path: Path, difficulty: str, template: str) -> None:
    result = generate_challenge(
        name=f"compile-{template}",
        difficulty=difficulty,
        template=template,
        profile=_profile_for_template(template),
        style=_style_for_template(template),
        out_dir=tmp_path,
        seed=12000 + len(template),
        allow_repeat=True,
    )
    output = result.challenge_dir / "dist" / result.metadata["binary_name"]
    assert output.exists()


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_medium_generated_binary_does_not_contain_full_flag(tmp_path: Path) -> None:
    result = generate_challenge(
        name="mediumleak",
        difficulty="medium",
        template="medium_crc_gate",
        out_dir=tmp_path,
        seed=77,
        allow_repeat=True,
    )
    binary = result.challenge_dir / "dist" / result.metadata["binary_name"]
    assert result.metadata["flag"].encode("utf-8") not in binary.read_bytes()


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_hard_generated_binary_does_not_contain_full_flag(tmp_path: Path) -> None:
    result = generate_challenge(
        name="hardleak",
        difficulty="hard",
        template="hard_mixed_constraints",
        out_dir=tmp_path,
        seed=78,
        allow_repeat=True,
    )
    binary = result.challenge_dir / "dist" / result.metadata["binary_name"]
    assert result.metadata["flag"].encode("utf-8") not in binary.read_bytes()


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_superhard_vm_builds_and_accepts_solver_output(tmp_path: Path) -> None:
    result = generate_challenge(
        name="vmreal",
        difficulty="super-hard",
        template="superhard_toy_vm_real",
        out_dir=tmp_path,
        seed=79,
        allow_repeat=True,
    )
    solution = _solve(result.challenge_dir)
    binary = result.challenge_dir / "dist" / result.metadata["binary_name"]
    run = subprocess.run([str(binary), solution], text=True, capture_output=True, check=False)

    assert run.returncode == 0
    assert result.metadata["flag"].encode("utf-8") not in binary.read_bytes()
    assert result.metadata["bytecode_length"] >= 80


def test_audit_command_works(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    result = generate_challenge(
        name="auditme",
        difficulty="medium",
        template="medium_multi_stage",
        out_dir=tmp_path,
        seed=80,
        allow_repeat=True,
    )

    assert cli_main(["audit", str(result.challenge_dir), "--quiet"]) == 0
    assert capsys.readouterr().out.strip().isdigit()
    assert audit_challenge(result.challenge_dir).quality_score >= 80


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_terminal_hard_challenge_creates_artifact_and_commands(tmp_path: Path) -> None:
    result = generate_challenge(
        name="firmware_gate",
        difficulty="hard",
        profile="qualifier",
        style="terminal",
        family="terminal_firmware_blob",
        out_dir=tmp_path,
        seed=700,
        allow_repeat=True,
    )
    challenge = result.challenge_dir
    binary = challenge / "dist" / result.metadata["binary_name"]
    solution = _solve(challenge)

    assert (challenge / "firmware.blob").exists()
    assert "--help" in result.metadata["terminal_commands"]
    help_run = subprocess.run([str(binary), "--help"], cwd=challenge, text=True, capture_output=True, check=False)
    verify_run = subprocess.run([str(binary), "verify", solution], cwd=challenge, text=True, capture_output=True, check=False)
    check_run = subprocess.run([str(binary), "check", "firmware.blob"], cwd=challenge, text=True, capture_output=True, check=False)

    assert help_run.returncode == 0
    assert "verify <candidate>" in help_run.stdout
    assert verify_run.returncode == 0
    assert check_run.returncode == 0


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_terminal_competition_mode_hides_private_files(tmp_path: Path) -> None:
    result = generate_challenge(
        name="finals_public",
        difficulty="super-hard",
        profile="finals",
        style="terminal",
        family="terminal_hybrid_finals",
        out_dir=tmp_path,
        seed=701,
        competition_mode=True,
        allow_repeat=True,
    )
    challenge = result.challenge_dir
    names = {path.relative_to(challenge).as_posix() for path in challenge.rglob("*") if path.is_file()}

    assert names == {"README.md", "metadata_public.json", "capsule.bin", "dist/finals_public"}
    assert audit_challenge(challenge).private_files_leaked is False


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_medium_hard_superhard_do_not_leak_real_flag_in_strings(tmp_path: Path) -> None:
    cases = [
        ("medium_case", "medium", "medium_crc_gate", None, "standard", None),
        ("hard_case", "hard", "hard_encoded_table", None, "standard", None),
        ("super_case", "super-hard", None, "terminal_license_vm", "qualifier", "terminal"),
    ]
    for name, difficulty, template, family, profile, style in cases:
        result = generate_challenge(
            name=name,
            difficulty=difficulty,
            template=template,
            family=family,
            profile=profile,
            style=style,
            out_dir=tmp_path,
            seed=710 + len(name),
            allow_repeat=True,
        )
        report = audit_challenge(result.challenge_dir)
        assert report.full_flag_in_strings is False


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_hard_and_superhard_qualifier_binaries_are_stripped(tmp_path: Path) -> None:
    for name, difficulty, family in [
        ("qual_hard", "hard", "terminal_firmware_blob"),
        ("qual_super", "super-hard", "terminal_license_vm"),
    ]:
        result = generate_challenge(
            name=name,
            difficulty=difficulty,
            profile="qualifier",
            style="terminal",
            family=family,
            out_dir=tmp_path,
            seed=730 + len(name),
            allow_repeat=True,
        )
        assert audit_challenge(result.challenge_dir).binary_stripped is True


def test_fake_flag_decoys_absent_by_default_in_medium_plus(tmp_path: Path) -> None:
    result = generate_challenge(
        name="no_decoys",
        difficulty="hard",
        template="hard_encoded_table",
        out_dir=tmp_path,
        seed=740,
        allow_repeat=True,
    )
    source = (result.challenge_dir / "src" / "main.c").read_text(encoding="utf-8")
    assert "decoy_" not in source
    assert "revforge{decoy_" not in source


def test_fake_flag_decoys_only_with_flag_option(tmp_path: Path) -> None:
    result = generate_challenge(
        name="with_decoys",
        difficulty="hard",
        template="hard_encoded_table",
        out_dir=tmp_path,
        seed=741,
        allow_repeat=True,
        fake_flags=True,
        fake_flag_count=8,
        fake_flag_style="mixed",
    )
    source = (result.challenge_dir / "src" / "main.c").read_text(encoding="utf-8")
    assert "revforge{decoy_" in source
    assert "flag{decoy_" in source
    assert "CTF{decoy_" in source
    assert result.metadata["fake_flags_enabled"] is True
    assert result.metadata["fake_flag_count"] == 8
    assert result.metadata["fake_flag_style"] == "mixed"


def test_solve_py_for_medium_plus_does_not_only_print_literal(tmp_path: Path) -> None:
    result = generate_challenge(
        name="solver_shape",
        difficulty="medium",
        template="medium_multi_stage",
        out_dir=tmp_path,
        seed=742,
        allow_repeat=True,
    )
    report = audit_challenge(result.challenge_dir)
    assert report.solve_py_literal_print is False


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_vm_bytecode_and_constraint_thresholds(tmp_path: Path) -> None:
    vm = generate_challenge(
        name="vm_threshold",
        difficulty="super-hard",
        profile="qualifier",
        style="terminal",
        family="terminal_license_vm",
        out_dir=tmp_path,
        seed=743,
        allow_repeat=True,
    )
    constraints = generate_challenge(
        name="constraints_threshold",
        difficulty="hard",
        profile="qualifier",
        style="terminal",
        family="terminal_constraints_pack",
        out_dir=tmp_path,
        seed=744,
        allow_repeat=True,
    )

    assert vm.metadata["bytecode_length"] >= 180
    assert constraints.metadata["constraint_count"] >= 40


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_finals_hybrid_includes_three_techniques_and_scores(tmp_path: Path) -> None:
    result = generate_challenge(
        name="hybrid_score",
        difficulty="super-hard",
        profile="finals",
        style="terminal",
        family="terminal_hybrid_finals",
        out_dir=tmp_path,
        seed=745,
        allow_repeat=True,
    )
    report = audit_challenge(result.challenge_dir)

    assert len(result.metadata["technique_mix"]) >= 3
    assert result.metadata["bytecode_length"] >= 350
    assert result.metadata["constraint_count"] >= 80
    assert report.quality_score >= 95


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_audit_score_thresholds_work(tmp_path: Path) -> None:
    hard = generate_challenge(
        name="audit_hard_qual",
        difficulty="hard",
        profile="qualifier",
        style="terminal",
        family="terminal_firmware_blob",
        out_dir=tmp_path,
        seed=746,
        allow_repeat=True,
    )
    super_hard = generate_challenge(
        name="audit_super_qual",
        difficulty="super-hard",
        profile="qualifier",
        style="terminal",
        family="terminal_license_vm",
        out_dir=tmp_path,
        seed=747,
        allow_repeat=True,
    )

    assert audit_challenge(hard.challenge_dir).quality_score >= 80
    assert audit_challenge(super_hard.challenge_dir).quality_score >= 90


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_selftest_serious_command_works(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["selftest-serious", "--quiet"]) == 0
    assert capsys.readouterr().out.strip() == "ok"


@pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc is not installed")
def test_selftest_qualifier_and_finals_commands_work(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["selftest-qualifier", "--quiet"]) == 0
    assert capsys.readouterr().out.strip() == "ok"
    assert cli_main(["selftest-finals", "--quiet"]) == 0
    assert capsys.readouterr().out.strip() == "ok"
    assert cli_main(["selftest-fake-flags", "--quiet"]) == 0
    assert capsys.readouterr().out.strip() == "ok"
