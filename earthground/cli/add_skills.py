"""Install Earthground's packaged skills into the current Claude project."""

from __future__ import annotations

import pathlib
import shutil
import sys
from dataclasses import dataclass
from importlib import resources
from typing import Callable, Optional, Sequence, TextIO

SKILLS_PACKAGE = "earthground.skills"
CLAUDE_SKILLS_PATH = pathlib.Path(".claude") / "skills"


class SkillsAddError(RuntimeError):
    """Raised when packaged Earthground skills cannot be installed."""


@dataclass(frozen=True)
class SkillsAddPlan:
    """A read-only description of a proposed skill installation."""

    source: object
    destination: pathlib.Path
    skill_names: tuple[str, ...]
    existing_skill_names: tuple[str, ...]


@dataclass(frozen=True)
class SkillsAddResult:
    """The outcome of an interactive skill installation."""

    destination: pathlib.Path
    skill_names: tuple[str, ...]
    copied: bool


def get_skills_add_plan(
    current_directory: pathlib.Path | str | None = None,
) -> SkillsAddPlan:
    """Inspect packaged skills and the current project's Claude destination."""
    destination_root = (
        pathlib.Path(
            current_directory if current_directory is not None else pathlib.Path.cwd()
        )
        .expanduser()
        .resolve()
    )
    destination = destination_root / CLAUDE_SKILLS_PATH

    try:
        source = resources.files(SKILLS_PACKAGE)
        skill_names = tuple(
            sorted(
                child.name
                for child in source.iterdir()
                if child.is_dir() and child.joinpath("SKILL.md").is_file()
            )
        )
    except (ModuleNotFoundError, OSError) as exc:
        raise SkillsAddError(
            f"Unable to read packaged Earthground skills: {exc}"
        ) from exc

    if not skill_names:
        raise SkillsAddError("No packaged Earthground skills were found")

    existing = tuple(
        name for name in skill_names if destination.joinpath(name).exists()
    )
    return SkillsAddPlan(
        source=source,
        destination=destination,
        skill_names=skill_names,
        existing_skill_names=existing,
    )


def _copy_resource_tree(source, destination: pathlib.Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            _copy_resource_tree(child, target)
            continue
        with child.open("rb") as source_file, target.open("wb") as target_file:
            shutil.copyfileobj(source_file, target_file)


def _print_plan(plan: SkillsAddPlan, output: TextIO) -> None:
    print(
        f"Earthground will copy {len(plan.skill_names)} skills into this project.",
        file=output,
    )
    print(f"Source: {plan.source}", file=output)
    print(f"Destination: {plan.destination}", file=output)
    print("Skills:", file=output)
    for name in plan.skill_names:
        print(f" - {name}", file=output)
    if plan.existing_skill_names:
        print(
            "Existing skill directories will be updated: "
            + ", ".join(plan.existing_skill_names),
            file=output,
        )
    print(
        "Files with matching paths will be overwritten; other files will remain.",
        file=output,
    )


def add_skills(
    current_directory: pathlib.Path | str | None = None,
    *,
    input_func: Optional[Callable[[], str]] = None,
    output: Optional[TextIO] = None,
) -> SkillsAddResult:
    """Confirm, then copy packaged skills into ``.claude/skills``."""
    output = output or sys.stdout
    input_func = input_func or input
    plan = get_skills_add_plan(current_directory)
    _print_plan(plan, output)
    print("Continue? [y/N] ", end="", flush=True, file=output)

    try:
        response = input_func().strip().casefold()
    except EOFError:
        response = ""

    if response not in {"y", "yes"}:
        print("Cancelled. No files were changed.", file=output)
        return SkillsAddResult(
            destination=plan.destination,
            skill_names=plan.skill_names,
            copied=False,
        )

    try:
        for name in plan.skill_names:
            _copy_resource_tree(
                plan.source.joinpath(name),
                plan.destination / name,
            )
    except OSError as exc:
        raise SkillsAddError(
            f"Unable to copy Earthground skills to {plan.destination}: {exc}"
        ) from exc

    print(
        f"Added {len(plan.skill_names)} Earthground skills to {plan.destination}",
        file=output,
    )
    return SkillsAddResult(
        destination=plan.destination,
        skill_names=plan.skill_names,
        copied=True,
    )


def run_parsed_args(_args) -> int:
    """Run the interactive skills add command."""
    try:
        add_skills()
    except SkillsAddError as exc:
        print(f"earthground skills add: error: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the standalone interactive skill installer."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="earthground skills add",
        description="Add Earthground skills to the current Claude project",
    )
    return run_parsed_args(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
