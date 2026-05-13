from __future__ import annotations

import json
from pathlib import Path

import pytest

from revforge.ai import commands as ai_commands
from revforge.ai.anthropic_provider import AnthropicProvider
from revforge.ai.base import AIProviderNotConfigured
from revforge.ai.gemini_provider import GeminiProvider
from revforge.ai.openai_provider import OpenAIProvider
from revforge.ai.providers import get_provider
from revforge.ai.validator import AIRecipeValidationError, validate_ai_recipe_json
from revforge.cli import main as cli_main
from revforge.generator import generate_challenge


@pytest.fixture(autouse=True)
def isolated_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVFORGE_HOME", str(tmp_path / "home"))


def valid_recipe(**overrides) -> dict:
    recipe = {
        "name": "ai_case",
        "difficulty": "medium",
        "target": "elf",
        "template_family": "medium_multi_stage",
        "theme": "retro terminal",
        "story": "A local decoder validates one candidate string.",
        "fake_strings": ["offline mode", "debug gate closed"],
        "function_name_style": "short technical names",
        "variable_name_style": "compact state names",
        "hint_levels": ["Find the staged checker.", "Recover modular equations.", "Rebuild the input."],
        "complexity": 6,
        "requested_features": ["staged checks", "encoded constants"],
        "profile": "qualifier",
        "style": "terminal",
        "terminal_commands": ["--help", "verify", "check"],
        "artifact_files": ["constraints.pack"],
        "family": "terminal_constraints_pack",
        "technique_mix": ["encoded constraints", "local artifact"],
        "complexity_budget": 7,
    }
    recipe.update(overrides)
    return recipe


class FakeProvider:
    def __init__(self, recipe: dict | None = None, text: str = "Score: 88/100") -> None:
        self.recipe = recipe or valid_recipe()
        self.text = text

    def generate_recipe(self, request):
        return json.dumps(self.recipe | {"name": request["name"], "difficulty": request["difficulty"], "target": request["target"]})

    def generate_hints(self, context, levels: int):
        return self.text

    def generate_review(self, context):
        return self.text

    def generate_writeup(self, context):
        return self.text


def test_ai_recipe_validator_accepts_valid_recipe() -> None:
    recipe = validate_ai_recipe_json(valid_recipe())
    assert recipe.template_family == "medium_multi_stage"
    assert recipe.complexity == 6
    assert recipe.profile == "qualifier"
    assert recipe.style == "terminal"
    assert recipe.family == "terminal_constraints_pack"


def test_ai_recipe_validator_rejects_unsafe_fields() -> None:
    unsafe = valid_recipe(requested_features=["network callback"])
    with pytest.raises(AIRecipeValidationError):
        validate_ai_recipe_json(unsafe)


def test_ai_recipe_validator_rejects_identity_terms() -> None:
    for term in ("Koso" + "vo", "S" + "HC", "KO" + "SCTF"):
        blocked = valid_recipe(story=f"bad reference {term}")
        with pytest.raises(AIRecipeValidationError):
            validate_ai_recipe_json(blocked)


def test_provider_config_masks_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVFORGE_OPENAI_API_KEY", "sk-test1234abcd")
    config = get_provider("openai").config()

    assert config.configured
    assert config.masked_key == "sk-...abcd"
    assert "sk-test1234abcd" not in config.masked_key


def test_modern_ai_defaults_appear_in_ai_config(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    for key in (
        "REVFORGE_OPENAI_API_KEY",
        "OPENAI_API_KEY",
        "REVFORGE_OPENAI_MODEL",
        "REVFORGE_ANTHROPIC_API_KEY",
        "ANTHROPIC_API_KEY",
        "REVFORGE_ANTHROPIC_MODEL",
        "REVFORGE_GEMINI_API_KEY",
        "GEMINI_API_KEY",
        "REVFORGE_GEMINI_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)

    assert cli_main(["ai-config", "--quiet"]) == 0
    out = capsys.readouterr().out
    assert "openai: missing key, model=gpt-5.1" in out
    assert "anthropic: missing key, model=claude-sonnet-4-6" in out
    assert "gemini: missing key, model=gemini-3.1-pro-preview" in out


def test_missing_api_key_gives_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REVFORGE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIProvider()

    with pytest.raises(AIProviderNotConfigured):
        provider.require_configured()


def test_ai_command_missing_api_key_fails_cleanly(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.delenv("REVFORGE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    code = cli_main(
        [
            "ai-new",
            "--provider",
            "openai",
            "--name",
            "missing_key",
            "--difficulty",
            "medium",
            "--target",
            "elf",
            "--theme",
            "retro terminal",
        ]
    )

    assert code == 1
    assert "not configured" in capsys.readouterr().out


def test_mocked_openai_provider_returns_valid_recipe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVFORGE_OPENAI_API_KEY", "sk-test1234abcd")
    monkeypatch.setattr(OpenAIProvider, "_complete", lambda self, system, user, json_mode: json.dumps(valid_recipe()))

    recipe = validate_ai_recipe_json(OpenAIProvider().generate_recipe(valid_recipe()))
    assert recipe.name == "ai_case"


def test_mocked_anthropic_provider_returns_valid_recipe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVFORGE_ANTHROPIC_API_KEY", "ak-test1234abcd")
    monkeypatch.setattr(AnthropicProvider, "_complete", lambda self, user: json.dumps(valid_recipe()))

    recipe = validate_ai_recipe_json(AnthropicProvider().generate_recipe(valid_recipe()))
    assert recipe.target == "elf"


def test_mocked_gemini_provider_returns_valid_recipe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVFORGE_GEMINI_API_KEY", "gk-test1234abcd")
    monkeypatch.setattr(GeminiProvider, "_complete", lambda self, user: json.dumps(valid_recipe()))

    recipe = validate_ai_recipe_json(GeminiProvider().generate_recipe(valid_recipe()))
    assert recipe.difficulty == "medium"


def test_ai_new_with_mocked_provider_creates_valid_challenge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("revforge.ai.providers.get_provider", lambda name=None: FakeProvider())
    path, recipe = ai_commands.ai_new(
        provider_name="openai",
        name="ai_case",
        difficulty="medium",
        target="elf",
        theme="retro terminal",
        out_dir=str(tmp_path),
        seed="123",
        competition_mode=False,
        allow_repeat=True,
    )

    assert path.exists()
    assert recipe.template_family == "medium_multi_stage"
    assert (path / "ai_recipe.json").exists()
    assert (path / "dist" / "ai_case").exists()
    assert "A local decoder validates one candidate string." in (path / "README.md").read_text(encoding="utf-8")


def test_ai_hints_does_not_reveal_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = generate_challenge(
        name="hintcase",
        difficulty="medium",
        template="medium_multi_stage",
        out_dir=tmp_path,
        seed=321,
        allow_repeat=True,
    )
    flag = result.metadata["flag"]
    monkeypatch.setattr("revforge.ai.providers.get_provider", lambda name=None: FakeProvider(text=f"Hint 1: never print {flag}"))

    hints = ai_commands.ai_hints(result.challenge_dir, provider_name="openai", levels=3)
    text = hints.read_text(encoding="utf-8")

    assert flag not in text
    assert "[redacted]" in text


def test_ai_review_returns_quality_score(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = generate_challenge(
        name="reviewcase",
        difficulty="easy",
        template="easy_xor_chunks",
        out_dir=tmp_path,
        seed=222,
        allow_repeat=True,
    )
    monkeypatch.setattr("revforge.ai.providers.get_provider", lambda name=None: FakeProvider(text="Looks solid."))

    text = ai_commands.ai_review(result.challenge_dir, provider_name="anthropic")
    assert "Score:" in text


def test_agent_prompt_generates_for_supported_agents() -> None:
    for agent in ("codex", "claude-code", "gemini"):
        text = ai_commands.agent_prompt(agent=agent, name="boss1", difficulty="hard", profile="qualifier", theme="firmware lock")
        assert "structured JSON recipes only" in text
        assert "internal safe templates" in text
        assert "Profile: qualifier" in text


def test_no_api_keys_written_to_generated_challenge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "sk-secret-value-1234"
    monkeypatch.setenv("REVFORGE_OPENAI_API_KEY", secret)
    monkeypatch.setattr("revforge.ai.providers.get_provider", lambda name=None: FakeProvider())
    path, _ = ai_commands.ai_new(
        provider_name="openai",
        name="keycase",
        difficulty="medium",
        target="elf",
        theme="retro terminal",
        out_dir=str(tmp_path),
        seed="555",
        competition_mode=False,
        allow_repeat=True,
    )

    for file_path in path.rglob("*"):
        if file_path.is_file():
            assert secret not in file_path.read_text(encoding="utf-8", errors="ignore")


def test_generated_ai_docs_do_not_contain_identity_terms(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("revforge.ai.providers.get_provider", lambda name=None: FakeProvider(text="Hint: inspect the staged checker."))
    path, _ = ai_commands.ai_new(
        provider_name="gemini",
        name="doccase",
        difficulty="medium",
        target="elf",
        theme="retro terminal",
        out_dir=str(tmp_path),
        seed="777",
        competition_mode=False,
        allow_repeat=True,
    )
    ai_commands.ai_hints(path, provider_name="gemini", levels=2)
    text = "\n".join(file.read_text(encoding="utf-8", errors="ignore") for file in path.rglob("*") if file.is_file())

    for term in ("Koso" + "vo", "S" + "HC", "KO" + "SCTF", "Sw" + "iss", "scho" + "ol", "te" + "am", "coun" + "try"):
        assert term not in text
