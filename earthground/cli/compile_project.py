"""Load and validate an Earthground design declared by a project."""

from __future__ import annotations

import hashlib
import importlib
import importlib.machinery
import pathlib
import sys
import types
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional, Sequence

import yaml

from earthground.kicad.catalog import (
    find_project_root,
    get_project_paths,
    initialize_project,
)
from earthground.schematic import Design, SchematicValidationError

CONFIG_PATH = pathlib.Path(".earthground") / "config.yaml"


class CompileProjectError(RuntimeError):
    """Raised when an Earthground project cannot be loaded for compilation."""


@dataclass(frozen=True)
class CompileResult:
    """Summary of a successfully compiled design."""

    design_name: str
    component_count: int
    module_count: int
    net_count: int


@dataclass(frozen=True)
class LoadedDesignFile:
    """A design loaded from a Python source file."""

    source: pathlib.Path
    project_root: pathlib.Path
    design: Design


def _load_design_reference(project_root: pathlib.Path) -> str:
    config_path = project_root / CONFIG_PATH
    if not config_path.is_file():
        raise CompileProjectError(f"Earthground config not found: {config_path}")

    try:
        document = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise CompileProjectError(
            f"Unable to read Earthground config {config_path}: {exc}"
        ) from exc

    if not isinstance(document, dict):
        raise CompileProjectError(f"{config_path} must contain a YAML mapping")

    project_config = document.get("project")
    if not isinstance(project_config, dict):
        raise CompileProjectError(f"{config_path} must contain a 'project' mapping")

    design_reference = project_config.get("design_class")
    if not isinstance(design_reference, str) or not design_reference.strip():
        raise CompileProjectError(f"{config_path} must define 'project.design_class'")
    return design_reference.strip()


def _resolve_project_root(project: pathlib.Path | str) -> pathlib.Path:
    project_root = pathlib.Path(project).expanduser().resolve()
    if not project_root.is_dir():
        raise CompileProjectError(f"Project directory not found: {project_root}")
    return project_root


def _resolve_design_file(design_file: pathlib.Path | str) -> pathlib.Path:
    source = pathlib.Path(design_file).expanduser().resolve()
    if not source.is_file():
        raise CompileProjectError(f"Earthground design file not found: {source}")
    if source.suffix != ".py":
        raise CompileProjectError(
            f"Earthground design file must be a Python file: {source}"
        )
    return source


def _find_import_root(source: pathlib.Path, project_root: pathlib.Path) -> pathlib.Path:
    for candidate in (source.parent, *source.parent.parents):
        if any((candidate / marker).exists() for marker in (".git", ".hg", ".jj")):
            return candidate
    return project_root


@contextmanager
def _project_import_path(*roots: pathlib.Path) -> Iterator[None]:
    original_path = list(sys.path)
    for root in reversed(dict.fromkeys(roots)):
        sys.path.insert(0, str(root))
    try:
        yield
    finally:
        sys.path[:] = original_path


def _project_module_name(source: pathlib.Path, project_root: pathlib.Path) -> str:
    relative_module = source.relative_to(project_root).with_suffix("")
    parts = list(relative_module.parts)
    if parts[-1] == "__init__":
        parts.pop()
    if not parts or not all(part.isidentifier() for part in parts):
        raise CompileProjectError(
            f"Design file path must form a valid Python module beneath "
            f"{project_root}: {source}"
        )
    digest = hashlib.sha256(str(project_root).encode()).hexdigest()[:12]
    return ".".join([f"_earthground_project_{digest}", *parts])


def _import_project_module(
    source: pathlib.Path, project_root: pathlib.Path
) -> types.ModuleType:
    module_name = _project_module_name(source, project_root)
    namespace = module_name.partition(".")[0]
    for loaded_name in tuple(sys.modules):
        if loaded_name == namespace or loaded_name.startswith(f"{namespace}."):
            sys.modules.pop(loaded_name)

    package = types.ModuleType(namespace)
    package.__package__ = namespace
    package.__path__ = [str(project_root)]
    package.__spec__ = importlib.machinery.ModuleSpec(
        namespace, loader=None, is_package=True
    )
    sys.modules[namespace] = package

    importlib.invalidate_caches()
    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        raise CompileProjectError(
            f"Unable to import Earthground design file {source}: {exc}"
        ) from exc


def _design_from_module(module: types.ModuleType, source: pathlib.Path) -> Design:
    for preferred_name in ("design", "schematic"):
        candidate = vars(module).get(preferred_name)
        if candidate is not None:
            if isinstance(candidate, Design):
                return candidate
            raise CompileProjectError(
                f"{source} defines '{preferred_name}', but it is not an "
                "earthground.schematic.Design"
            )

    design_classes = [
        candidate
        for candidate in vars(module).values()
        if isinstance(candidate, type)
        and issubclass(candidate, Design)
        and candidate is not Design
        and candidate.__module__ == module.__name__
    ]
    if len(design_classes) == 1:
        return design_classes[0]()
    if len(design_classes) > 1:
        names = ", ".join(sorted(candidate.__name__ for candidate in design_classes))
        raise CompileProjectError(
            f"{source} defines multiple Design subclasses ({names}). "
            "Assign the design to a module-level variable named 'design'."
        )
    raise CompileProjectError(
        f"{source} must define a module-level Design named 'design' or exactly "
        "one Design subclass"
    )


def load_design_file(
    design_file: pathlib.Path | str,
    *,
    initialize_config: bool = False,
) -> LoadedDesignFile:
    """Load an Earthground design directly from a Python source file."""
    source = _resolve_design_file(design_file)
    project_root = find_project_root(start=source.parent)
    import_root = _find_import_root(source, project_root)
    if initialize_config:
        initialize_project(get_project_paths(project_root))
    with _project_import_path(project_root, import_root):
        module = _import_project_module(source, import_root)
        design = _design_from_module(module, source)
    return LoadedDesignFile(source, project_root, design)


def compile_design_file(
    design_file: pathlib.Path | str,
    *,
    initialize_config: bool = False,
) -> LoadedDesignFile:
    """Load and validate an Earthground design from a Python source file."""
    loaded = load_design_file(design_file, initialize_config=initialize_config)
    loaded.design.validate()
    return loaded


def _resolve_design_class(design_reference: str) -> type[Design]:
    module_name, separator, attribute_path = design_reference.partition(":")
    if not separator or not module_name or not attribute_path:
        raise CompileProjectError(
            "'project.design_class' must use the format 'python.module:DesignClass'"
        )

    importlib.invalidate_caches()
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        raise CompileProjectError(
            f"Unable to import design module '{module_name}': {exc}"
        ) from exc

    target: object = module
    try:
        for attribute in attribute_path.split("."):
            target = getattr(target, attribute)
    except AttributeError as exc:
        raise CompileProjectError(
            f"Design class '{attribute_path}' was not found in module "
            f"'{module_name}'"
        ) from exc

    if not isinstance(target, type) or not issubclass(target, Design):
        raise CompileProjectError(
            f"'{design_reference}' must refer to a subclass of "
            "'earthground.schematic.Design'"
        )
    return target


def load_design_class(project: pathlib.Path | str) -> type[Design]:
    """Load the configured design class for an Earthground project."""
    project_root = _resolve_project_root(project)
    design_reference = _load_design_reference(project_root)
    with _project_import_path(project_root):
        return _resolve_design_class(design_reference)


def compile_design(project: pathlib.Path | str) -> Design:
    """Instantiate and validate a project's configured design class."""
    project_root = _resolve_project_root(project)
    design_reference = _load_design_reference(project_root)
    with _project_import_path(project_root):
        design_class = _resolve_design_class(design_reference)
        design = design_class()
        design.validate()
    return design


def compile_project(project: pathlib.Path | str) -> CompileResult:
    """Compile a project and return its design summary."""
    design = compile_design(project)
    return CompileResult(
        design_name=design.name,
        component_count=sum(1 for _ in design.iter_components()),
        module_count=sum(1 for _ in design.iter_modules()),
        net_count=sum(len(item.nets) for item in design.iter_designs()),
    )


def configure_compile_parser(parser) -> None:
    """Add project compilation arguments to an argparse parser."""
    parser.add_argument(
        "project",
        nargs="?",
        default=".",
        help="Project directory (defaults to the current directory)",
    )


def run_parsed_args(args) -> int:
    """Run the compile command for already-parsed CLI arguments."""
    try:
        result = compile_project(args.project)
    except CompileProjectError as exc:
        print(f"earthground compile: error: {exc}", file=sys.stderr)
        return 2
    except SchematicValidationError as exc:
        print(f"Compilation failed for {exc.design_name}:", file=sys.stderr)
        for error in exc.errors:
            print(f" - {error}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Compilation failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Compiled {result.design_name}: "
        f"{result.component_count} components, "
        f"{result.module_count} modules, "
        f"{result.net_count} nets"
    )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run project compilation as a standalone command."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="earthground compile",
        description="Load and validate an Earthground design project",
    )
    configure_compile_parser(parser)
    return run_parsed_args(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
