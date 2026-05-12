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
from .builders import build_challenge
from .builders import android_ndk_builder, clang_builder, gcc_builder, mingw_builder, wasm_builder
from .generator import clean_challenge, generate_challenge
from .recipes import DIFFICULTIES, TARGETS, TEMPLATES_BY_DIFFICULTY
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

    return parser


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--quiet", action="store_true", default=argparse.SUPPRESS, help="print minimal output")
    parser.add_argument("--verbose", action="store_true", default=argparse.SUPPRESS, help="show tracebacks and debugging details")


def _add_common_generation_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", required=True, help="challenge folder/name")
    parser.add_argument("--difficulty", choices=DIFFICULTIES, required=True)
    parser.add_argument("--target", choices=TARGETS, default="elf")
    parser.add_argument("--template", help="template name or alias")
    parser.add_argument("--out", default=".", help="output directory")
    parser.add_argument("--seed", help="reproducible seed")
    parser.add_argument("--flag-format", default=None, help='format using {{{value}}}, e.g. "flag{{{value}}}"')
    flag_group = parser.add_mutually_exclusive_group()
    flag_group.add_argument("--flag", help="direct flag value")
    flag_group.add_argument("--random-flag", action="store_true", help="force a random generated flag")
    parser.add_argument("--competition-mode", action="store_true", help="omit private source, recipe, solution, and writeup")
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
        out_dir=args.out,
        seed=args.seed,
        flag=args.flag,
        random_flag=args.random_flag,
        flag_format=args.flag_format,
        allow_repeat=args.allow_repeat,
        competition_mode=args.competition_mode,
        include_source=include_source,
        include_solution=include_solution,
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


def _print_generation_summary(result) -> None:
    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold")
    table.add_column()
    table.add_row("Name", result.recipe.name)
    table.add_row("Difficulty", result.recipe.difficulty)
    table.add_row("Target", result.recipe.target)
    table.add_row("Template", result.recipe.template_family)
    table.add_row("Seed", str(result.recipe.seed))
    table.add_row("Flag format", result.recipe.flag_format)
    table.add_row("Output folder", str(result.challenge_dir))
    table.add_row("Created by", CREATED_BY)
    console.print(Panel(table, title="RevForge Challenge Generated", border_style="green"))


if __name__ == "__main__":
    sys.exit(main())
