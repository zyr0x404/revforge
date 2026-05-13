"""Command line interface for RevForge."""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .ai import commands as ai_commands
from .ai.providers import PROVIDER_NAMES, provider_configs
from .builders import build_challenge
from .builders import android_ndk_builder, clang_builder, gcc_builder, mingw_builder, wasm_builder
from .generator import clean_challenge, generate_challenge
from .quality import audit_challenge
from .recipes import DIFFICULTIES, FAKE_FLAG_STYLES, PROFILES, STYLES, TARGETS, TEMPLATES_BY_DIFFICULTY
from .selftest import run_selftest_fake_flags, run_selftest_finals, run_selftest_qualifier, run_selftest_serious
from .targets import all_targets
from .uniqueness import DuplicateRecipeError
from .utils import CREATED_BY

console = Console()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 2
    try:
        return args.handler(args)
    except Exception as exc:  # noqa: BLE001 - CLI should render clean failures by default.
        if getattr(args, "verbose", False):
            raise
        if not getattr(args, "quiet", False):
            console.print(f"[bold red]error:[/bold red] {exc}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="revforge", description="Safe educational reverse engineering CTF challenge generator.")
    parser.add_argument("--version", action="version", version=f"RevForge {__version__}")
    parser.add_argument("--quiet", action="store_true", help="print minimal output")
    parser.add_argument("--verbose", action="store_true", help="show tracebacks and debugging details")
    sub = parser.add_subparsers(dest="command")

    new = sub.add_parser("new", help="generate one challenge")
    _add_output_args(new)
    _add_common_generation_args(new)
    new.set_defaults(handler=cmd_new)

    batch = sub.add_parser("batch", help="generate many challenges")
    _add_output_args(batch)
    batch.add_argument("--count", type=int, required=True, help="number of challenges to generate")
    batch.add_argument("--difficulty", choices=DIFFICULTIES, required=True)
    batch.add_argument("--out", default=".", help="output directory")
    batch.add_argument("--target", choices=TARGETS, default="elf")
    batch.add_argument("--template", help="template name or alias")
    batch.add_argument("--seed", help="base seed; each challenge uses seed + index")
    batch.add_argument("--flag-format", default=None)
    batch.add_argument("--allow-repeat", action="store_true")
    batch.set_defaults(handler=cmd_batch)

    list_templates = sub.add_parser("list-templates", help="show implemented templates")
    _add_output_args(list_templates)
    list_templates.set_defaults(handler=cmd_list_templates)
    list_targets = sub.add_parser("list-targets", help="show supported targets")
    _add_output_args(list_targets)
    list_targets.set_defaults(handler=cmd_list_targets)
    doctor = sub.add_parser("doctor", help="check local toolchain availability")
    _add_output_args(doctor)
    doctor.set_defaults(handler=cmd_doctor)

    build = sub.add_parser("build", help="build a generated challenge")
    _add_output_args(build)
    build.add_argument("challenge_folder")
    build.set_defaults(handler=cmd_build)

    clean = sub.add_parser("clean", help="remove generated build artifacts")
    _add_output_args(clean)
    clean.add_argument("challenge_folder")
    clean.set_defaults(handler=cmd_clean)

    package = sub.add_parser("package", help="package a generated challenge")
    _add_output_args(package)
    package.add_argument("challenge_folder")
    package.add_argument("--zip", action="store_true", dest="make_zip", help="create a zip archive")
    package.set_defaults(handler=cmd_package)

    audit = sub.add_parser("audit", help="audit a generated challenge for leaks and quality")
    _add_output_args(audit)
    audit.add_argument("challenge_folder")
    audit.set_defaults(handler=cmd_audit)

    selftest = sub.add_parser("selftest-serious", help="generate, build, solve, and audit serious ELF challenges")
    _add_output_args(selftest)
    selftest.set_defaults(handler=cmd_selftest_serious)

    selftest_qualifier = sub.add_parser("selftest-qualifier", help="generate, build, solve, and audit qualifier-class terminal challenges")
    _add_output_args(selftest_qualifier)
    selftest_qualifier.set_defaults(handler=cmd_selftest_qualifier)

    selftest_finals = sub.add_parser("selftest-finals", help="generate, build, solve, and audit finals-class terminal challenges")
    _add_output_args(selftest_finals)
    selftest_finals.set_defaults(handler=cmd_selftest_finals)

    selftest_fake_flags = sub.add_parser("selftest-fake-flags", help="verify fake flag decoys are opt-in and safe")
    _add_output_args(selftest_fake_flags)
    selftest_fake_flags.set_defaults(handler=cmd_selftest_fake_flags)

    ai_config = sub.add_parser("ai-config", help="show AI provider configuration without leaking keys")
    _add_output_args(ai_config)
    ai_config.set_defaults(handler=cmd_ai_config)

    ai_new = sub.add_parser("ai-new", help="generate a challenge from a validated AI JSON recipe")
    _add_output_args(ai_new)
    _add_ai_provider_arg(ai_new)
    ai_new.add_argument("--name", required=True)
    ai_new.add_argument("--difficulty", choices=DIFFICULTIES, required=True)
    ai_new.add_argument("--target", choices=TARGETS, default="elf")
    ai_new.add_argument("--theme", required=True)
    ai_new.add_argument("--out", default=".")
    ai_new.add_argument("--seed")
    ai_new.add_argument("--competition-mode", action="store_true")
    ai_new.add_argument("--allow-repeat", action="store_true")
    ai_new.set_defaults(handler=cmd_ai_new)

    ai_hints = sub.add_parser("ai-hints", help="generate progressive hints for a training challenge")
    _add_output_args(ai_hints)
    _add_ai_provider_arg(ai_hints)
    ai_hints.add_argument("challenge_folder")
    ai_hints.add_argument("--levels", type=int, default=3)
    ai_hints.set_defaults(handler=cmd_ai_hints)

    ai_review = sub.add_parser("ai-review", help="AI-assisted challenge quality review")
    _add_output_args(ai_review)
    _add_ai_provider_arg(ai_review)
    ai_review.add_argument("challenge_folder")
    ai_review.set_defaults(handler=cmd_ai_review)

    ai_writeup = sub.add_parser("ai-writeup", help="AI-assisted educational writeup")
    _add_output_args(ai_writeup)
    _add_ai_provider_arg(ai_writeup)
    ai_writeup.add_argument("challenge_folder")
    ai_writeup.add_argument("--force", action="store_true")
    ai_writeup.set_defaults(handler=cmd_ai_writeup)

    agent_prompt = sub.add_parser("agent-prompt", help="print a safe coding-agent handoff prompt")
    _add_output_args(agent_prompt)
    agent_prompt.add_argument("--agent", choices=("codex", "claude-code", "gemini", "generic"), required=True)
    agent_prompt.add_argument("--name", required=True)
    agent_prompt.add_argument("--difficulty", choices=DIFFICULTIES, required=True)
    agent_prompt.add_argument("--profile", choices=PROFILES, default="standard")
    agent_prompt.add_argument("--theme", required=True)
    agent_prompt.set_defaults(handler=cmd_agent_prompt)

    return parser


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS, help="print minimal output")
    parser.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS, help="show tracebacks and debugging details")


def _add_ai_provider_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", choices=PROVIDER_NAMES, default=None, help="AI provider to use")


def _add_common_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", required=True, help="challenge folder/name")
    parser.add_argument("--difficulty", choices=DIFFICULTIES, required=True)
    parser.add_argument("--target", choices=TARGETS, default="elf")
    parser.add_argument("--template", help="template name or alias")
    parser.add_argument("--family", help="terminal challenge family")
    parser.add_argument("--profile", choices=PROFILES, default="standard")
    parser.add_argument("--style", choices=STYLES, default=None)
    parser.add_argument("--out", default=".", help="output directory")
    parser.add_argument("--seed", help="reproducible seed")
    parser.add_argument("--flag-format", default=None, help='format using {{{value}}}, e.g. "flag{{{value}}}"')
    flag_group = parser.add_mutually_exclusive_group()
    flag_group.add_argument("--flag", help="direct flag value")
    flag_group.add_argument("--random-flag", action="store_true", help="force a random generated flag")
    parser.add_argument("--competition-mode", action="store_true", help="omit private source, recipe, solution, and writeup")
    parser.add_argument("--fake-flags", action="store_true", help="include fake flag-shaped decoys")
    parser.add_argument("--fake-flag-count", type=int, default=3, help="number of fake flag decoys when --fake-flags is enabled")
    parser.add_argument("--fake-flag-style", choices=FAKE_FLAG_STYLES, default="default", help="fake flag decoy style")
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("--with-source", action="store_true")
    source_group.add_argument("--no-source", action="store_true")
    solution_group = parser.add_mutually_exclusive_group()
    solution_group.add_argument("--with-solution", action="store_true")
    solution_group.add_argument("--no-solution", action="store_true")
    parser.add_argument("--allow-repeat", action="store_true", help="allow a recipe hash already present in local history")


def cmd_new(args: argparse.Namespace) -> int:
    include_source = True if args.with_source else False if args.no_source else None
    include_solution = True if args.with_solution else False if args.no_solution else None
    result = generate_challenge(
        name=args.name,
        difficulty=args.difficulty,
        target=args.target,
        template=args.template,
        family=args.family,
        out_dir=args.out,
        seed=args.seed,
        flag=args.flag,
        random_flag=args.random_flag,
        flag_format=args.flag_format,
        allow_repeat=args.allow_repeat,
        competition_mode=args.competition_mode,
        include_source=include_source,
        include_solution=include_solution,
        profile=args.profile,
        style=args.style,
        fake_flags=args.fake_flags,
        fake_flag_count=args.fake_flag_count,
        fake_flag_style=args.fake_flag_style,
    )
    if args.quiet:
        print(result.challenge_dir)
        return 0
    _print_generation_summary(result)
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    if args.count < 1:
        raise ValueError("--count must be at least 1")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    generated = []
    for index in range(args.count):
        seed = None
        if args.seed is not None:
            seed = str(int(args.seed, 0) + index)
        name = f"{args.difficulty.replace('-', '_')}_{index + 1:03d}"
        result = generate_challenge(
            name=name,
            difficulty=args.difficulty,
            target=args.target,
            template=args.template,
            out_dir=out,
            seed=seed,
            flag_format=args.flag_format,
            allow_repeat=args.allow_repeat,
        )
        generated.append(result)
    if args.quiet:
        for result in generated:
            print(result.challenge_dir)
        return 0
    table = Table(title=f"Generated {len(generated)} RevForge challenges")
    table.add_column("Name")
    table.add_column("Template")
    table.add_column("Seed")
    table.add_column("Folder")
    for result in generated:
        table.add_row(result.recipe.name, result.recipe.template_family, str(result.recipe.seed), str(result.challenge_dir))
    console.print(table)
    return 0


def cmd_list_templates(args: argparse.Namespace) -> int:
    table = Table(title="RevForge Templates")
    table.add_column("Difficulty", style="cyan")
    table.add_column("Implemented Templates")
    for difficulty, names in TEMPLATES_BY_DIFFICULTY.items():
        table.add_row(difficulty, ", ".join(names))
    console.print(table)
    return 0


def cmd_list_targets(args: argparse.Namespace) -> int:
    table = Table(title="RevForge Targets")
    table.add_column("Target", style="cyan")
    table.add_column("Display")
    table.add_column("Source")
    table.add_column("Notes")
    for target in all_targets():
        table.add_row(target.name, target.display, target.source_relpath, target.description)
    console.print(table)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    table = Table(title="RevForge Doctor")
    table.add_column("Target")
    table.add_column("Builder")
    table.add_column("Status")
    table.add_row("elf", "gcc/clang", gcc_builder.status())
    table.add_row("exe", "mingw-w64", mingw_builder.status())
    table.add_row("macho", "clang", clang_builder.status())
    table.add_row("android", "Android NDK/Gradle", android_ndk_builder.status())
    table.add_row("wasm", "emscripten", wasm_builder.status())
    console.print(table)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    ok, message = build_challenge(Path(args.challenge_folder))
    if args.quiet:
        print(message)
    elif ok:
        console.print(f"[green]{message}[/green]")
    else:
        console.print(f"[red]{message}[/red]")
    return 0 if ok else 1


def cmd_clean(args: argparse.Namespace) -> int:
    removed = clean_challenge(Path(args.challenge_folder))
    if args.quiet:
        return 0
    if removed:
        for path in removed:
            console.print(f"removed {path}")
    else:
        console.print("nothing to clean")
    return 0


def cmd_package(args: argparse.Namespace) -> int:
    folder = Path(args.challenge_folder).resolve()
    if not folder.exists():
        raise FileNotFoundError(folder)
    if not args.make_zip:
        raise ValueError("package currently supports --zip")
    zip_path = folder.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob("*"):
            if path == zip_path or path.is_dir():
                continue
            archive.write(path, path.relative_to(folder.parent))
    if args.quiet:
        print(zip_path)
    else:
        console.print(f"[green]created {zip_path}[/green]")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    report = audit_challenge(Path(args.challenge_folder))
    if args.quiet:
        print(report.quality_score)
        return 0
    table = Table(title="RevForge Audit")
    table.add_column("Check")
    table.add_column("Value")
    table.add_row("Metadata valid", str(report.metadata_valid))
    table.add_row("Difficulty", report.difficulty)
    table.add_row("Profile", report.profile)
    table.add_row("Style", report.style)
    table.add_row("Family", report.family)
    table.add_row("Template", report.template)
    table.add_row("Competition mode", str(report.competition_mode))
    table.add_row("Source exists", str(report.source_exists))
    table.add_row("Binary exists", str(report.binary_exists))
    table.add_row("Solution exists", str(report.solution_exists))
    table.add_row("Full flag in source", str(report.full_flag_in_source))
    table.add_row("Full flag in strings", str(report.full_flag_in_strings))
    table.add_row("Binary stripped", str(report.binary_stripped))
    table.add_row("Private files leaked", str(report.private_files_leaked))
    table.add_row("Direct full-input compare", str(report.direct_full_input_compare))
    table.add_row("Literal solver print", str(report.solve_py_literal_print))
    table.add_row("Generated functions", str(report.generated_function_count))
    table.add_row("Encoded constants", str(report.encoded_constant_count))
    table.add_row("Bytecode length", str(report.bytecode_length))
    table.add_row("Constraint count", str(report.constraint_count))
    table.add_row("Local artifacts", str(report.local_artifact_count))
    table.add_row("Terminal commands", ", ".join(report.terminal_commands_detected) or "-")
    table.add_row("Fake flags enabled", str(report.fake_flags_enabled))
    table.add_row("Fake flag count", str(report.fake_flag_count))
    table.add_row("Fake flag style", report.fake_flag_style)
    table.add_row("Quality score", f"{report.quality_score}/100")
    table.add_row("Final grade", report.final_grade)
    console.print(table)
    if report.findings:
        finding_table = Table(title="Findings")
        finding_table.add_column("Finding")
        for finding in report.findings:
            finding_table.add_row(finding)
        console.print(finding_table)
    else:
        console.print("[green]No audit findings.[/green]")
    return 0


def cmd_selftest_serious(args: argparse.Namespace) -> int:
    results = run_selftest_serious()
    if args.quiet:
        print("ok")
        return 0
    table = Table(title="RevForge Serious Selftest")
    table.add_column("Difficulty")
    table.add_column("Template")
    table.add_column("Solved")
    table.add_column("Accepted")
    table.add_column("Leaked")
    table.add_column("Audit")
    for result in results:
        table.add_row(
            result.case.difficulty,
            result.case.template,
            str(result.solved),
            str(result.accepted),
            str(result.leaked),
            str(result.audit_score),
        )
    console.print(table)
    console.print("[green]Serious selftest passed.[/green]")
    return 0


def cmd_selftest_qualifier(args: argparse.Namespace) -> int:
    results = run_selftest_qualifier()
    if args.quiet:
        print("ok")
        return 0
    _print_selftest_table("RevForge Qualifier Selftest", results)
    console.print("[green]Qualifier selftest passed.[/green]")
    return 0


def cmd_selftest_finals(args: argparse.Namespace) -> int:
    results = run_selftest_finals()
    if args.quiet:
        print("ok")
        return 0
    _print_selftest_table("RevForge Finals Selftest", results)
    console.print("[green]Finals selftest passed.[/green]")
    return 0


def cmd_selftest_fake_flags(args: argparse.Namespace) -> int:
    results = run_selftest_fake_flags()
    if args.quiet:
        print("ok")
        return 0
    table = Table(title="RevForge Fake Flag Selftest")
    table.add_column("Case")
    table.add_column("Enabled")
    table.add_column("Expected")
    table.add_column("Observed")
    table.add_column("Real leaked")
    table.add_column("Private leaked")
    table.add_column("Audit")
    for result in results:
        table.add_row(
            result.name,
            str(result.fake_flags_enabled),
            str(result.expected_fake_count),
            str(result.observed_flag_like_count),
            str(result.real_flag_leaked),
            str(result.private_files_leaked),
            str(result.audit_score),
        )
    console.print(table)
    console.print("[green]Fake-flags selftest passed.[/green]")
    return 0


def _print_selftest_table(title: str, results) -> None:
    table = Table(title=title)
    table.add_column("Difficulty")
    table.add_column("Family")
    table.add_column("Solved")
    table.add_column("Accepted")
    table.add_column("Leaked")
    table.add_column("Audit")
    for result in results:
        table.add_row(
            result.case.difficulty,
            result.case.template,
            str(result.solved),
            str(result.accepted),
            str(result.leaked),
            str(result.audit_score),
        )
    console.print(table)


def cmd_ai_config(args: argparse.Namespace) -> int:
    configs = provider_configs()
    if args.quiet:
        for config in configs:
            status = "configured" if config.configured else "missing key"
            print(f"{config.name}: {status}, model={config.model or '-'}")
        return 0
    table = Table(title="RevForge AI Providers")
    table.add_column("Provider")
    table.add_column("Status")
    table.add_column("Model")
    table.add_column("Base URL")
    table.add_column("Key")
    for config in configs:
        table.add_row(
            config.name,
            "configured" if config.configured else config.detail,
            config.model or "-",
            config.base_url or "-",
            config.masked_key,
        )
    console.print(table)
    return 0


def cmd_ai_new(args: argparse.Namespace) -> int:
    path, recipe = ai_commands.ai_new(
        provider_name=args.provider,
        name=args.name,
        difficulty=args.difficulty,
        target=args.target,
        theme=args.theme,
        out_dir=args.out,
        seed=args.seed,
        competition_mode=args.competition_mode,
        allow_repeat=args.allow_repeat,
    )
    if args.quiet:
        print(path)
        return 0
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Name", recipe.name)
    table.add_row("Difficulty", recipe.difficulty)
    table.add_row("Target", recipe.target)
    table.add_row("Template", recipe.template_family)
    table.add_row("Theme", recipe.theme)
    table.add_row("Output folder", str(path))
    console.print(Panel(table, title="RevForge AI Challenge Generated", border_style="green"))
    return 0


def cmd_ai_hints(args: argparse.Namespace) -> int:
    if args.levels < 1 or args.levels > 10:
        raise ValueError("--levels must be between 1 and 10")
    path = ai_commands.ai_hints(args.challenge_folder, provider_name=args.provider, levels=args.levels)
    if args.quiet:
        print(path)
    else:
        console.print(f"[green]saved {path}[/green]")
    return 0


def cmd_ai_review(args: argparse.Namespace) -> int:
    text = ai_commands.ai_review(args.challenge_folder, provider_name=args.provider)
    print(text)
    return 0


def cmd_ai_writeup(args: argparse.Namespace) -> int:
    path = ai_commands.ai_writeup(args.challenge_folder, provider_name=args.provider, force=args.force)
    if args.quiet:
        print(path)
    else:
        console.print(f"[green]saved {path}[/green]")
    return 0


def cmd_agent_prompt(args: argparse.Namespace) -> int:
    print(ai_commands.agent_prompt(agent=args.agent, name=args.name, difficulty=args.difficulty, profile=args.profile, theme=args.theme))
    return 0


def _print_generation_summary(result) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Name", result.recipe.name)
    table.add_row("Difficulty", result.recipe.difficulty)
    table.add_row("Target", result.recipe.target)
    table.add_row("Template", result.recipe.template_family)
    table.add_row("Profile", result.recipe.profile)
    table.add_row("Style", result.recipe.style)
    table.add_row("Family", result.recipe.family or result.recipe.template_family)
    table.add_row("Seed", str(result.recipe.seed))
    table.add_row("Flag format", result.recipe.flag_format)
    table.add_row("Output folder", str(result.challenge_dir))
    table.add_row("Created by", CREATED_BY)
    console.print(Panel(table, title="RevForge Challenge Generated", border_style="green"))


if __name__ == "__main__":
    sys.exit(main())
