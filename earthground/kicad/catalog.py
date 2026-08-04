from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import keyword
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from typing import Iterable, Optional, Sequence, Union

import yaml
from pykicad import Footprint, read_from_file

CATALOG_SCHEMA = 1
CONFIG_DIRECTORY = ".earthground"
CONFIG_FILENAME = "config.yaml"
METADATA_FILENAME = "kicad-catalog.json"
ENVIRONMENT_OUTPUT = "environment"


class KicadCatalogError(RuntimeError):
    """Raised when the KiCad catalog cannot be configured or generated."""


@dataclass(frozen=True)
class ProjectPaths:
    root: pathlib.Path
    config: pathlib.Path
    metadata: pathlib.Path


@dataclass
class KicadConfig:
    executable: Optional[pathlib.Path] = None
    footprint_root: Optional[pathlib.Path] = None
    additional_footprint_roots: list[pathlib.Path] = field(default_factory=list)
    catalog_output: Union[str, pathlib.Path] = ENVIRONMENT_OUTPUT


@dataclass(frozen=True)
class KicadInstallation:
    executable: Optional[pathlib.Path]
    footprint_root: pathlib.Path
    version: str


@dataclass(frozen=True)
class FootprintEntry:
    library: str
    footprint_name: str
    path: Optional[pathlib.Path] = field(default=None, compare=False)

    @property
    def canonical_name(self) -> str:
        return f"{self.library}:{self.footprint_name}"


@dataclass(frozen=True)
class CatalogContext:
    project: ProjectPaths
    config: KicadConfig
    installation: KicadInstallation
    roots: tuple[pathlib.Path, ...]
    output: pathlib.Path
    environment_output: bool
    entries: tuple[FootprintEntry, ...]
    fingerprint: str


def _ancestors(start: pathlib.Path) -> Iterable[pathlib.Path]:
    current = start.resolve()
    yield current
    yield from current.parents


def find_project_root(
    start: Optional[Union[str, pathlib.Path]] = None,
    explicit: Optional[Union[str, pathlib.Path]] = None,
) -> pathlib.Path:
    """Find the Earthground project containing ``start``."""
    if explicit is not None:
        return pathlib.Path(explicit).expanduser().resolve()

    environment_root = os.environ.get("EARTHGROUND_PROJECT_ROOT")
    if environment_root:
        return pathlib.Path(environment_root).expanduser().resolve()

    starting_path = pathlib.Path(start or pathlib.Path.cwd()).expanduser().resolve()
    for candidate in _ancestors(starting_path):
        if (candidate / CONFIG_DIRECTORY / CONFIG_FILENAME).is_file():
            return candidate
    for candidate in _ancestors(starting_path):
        if (candidate / ".git").exists() or (candidate / "pyproject.toml").is_file():
            return candidate
    return starting_path


def get_project_paths(
    project_root: Optional[Union[str, pathlib.Path]] = None,
    config_path: Optional[Union[str, pathlib.Path]] = None,
) -> ProjectPaths:
    if config_path is not None:
        config = pathlib.Path(config_path).expanduser().resolve()
        if project_root is not None:
            root = pathlib.Path(project_root).expanduser().resolve()
        elif config.parent.name == CONFIG_DIRECTORY:
            root = config.parent.parent
        else:
            root = config.parent
    else:
        root = find_project_root(explicit=project_root)
        config = root / CONFIG_DIRECTORY / CONFIG_FILENAME
    return ProjectPaths(
        root=root,
        config=config,
        metadata=root / CONFIG_DIRECTORY / METADATA_FILENAME,
    )


def _resolve_config_path(value: str, project_root: pathlib.Path) -> pathlib.Path:
    expanded = pathlib.Path(os.path.expandvars(value)).expanduser()
    if not expanded.is_absolute():
        expanded = project_root / expanded
    return expanded.resolve()


def load_config(project: ProjectPaths) -> KicadConfig:
    if not project.config.is_file():
        raise KicadCatalogError(f"Earthground config not found: {project.config}")
    try:
        document = yaml.safe_load(project.config.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise KicadCatalogError(
            f"Unable to read Earthground config {project.config}: {exc}"
        ) from exc

    if not isinstance(document, dict) or not isinstance(
        document.get("kicad", {}), dict
    ):
        raise KicadCatalogError(f"{project.config} must contain a 'kicad' mapping")
    raw = document.get("kicad", {})
    allowed = {
        "executable",
        "footprint_root",
        "additional_footprint_roots",
        "catalog_output",
    }
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise KicadCatalogError(
            f"Unknown KiCad config keys in {project.config}: {', '.join(unknown)}"
        )

    extra_roots = raw.get("additional_footprint_roots", [])
    if extra_roots is None:
        extra_roots = []
    if not isinstance(extra_roots, list) or not all(
        isinstance(path, str) for path in extra_roots
    ):
        raise KicadCatalogError("'additional_footprint_roots' must be a list of paths")

    executable = raw.get("executable")
    footprint_root = raw.get("footprint_root")
    output = raw.get("catalog_output", ENVIRONMENT_OUTPUT)
    if executable is not None and not isinstance(executable, str):
        raise KicadCatalogError("'executable' must be a path or null")
    if footprint_root is not None and not isinstance(footprint_root, str):
        raise KicadCatalogError("'footprint_root' must be a path or null")
    if not isinstance(output, str):
        raise KicadCatalogError("'catalog_output' must be 'environment' or a path")

    resolved_output: Union[str, pathlib.Path]
    if output == ENVIRONMENT_OUTPUT:
        resolved_output = output
    else:
        resolved_output = _resolve_config_path(output, project.root)

    return KicadConfig(
        executable=(
            _resolve_config_path(executable, project.root) if executable else None
        ),
        footprint_root=(
            _resolve_config_path(footprint_root, project.root)
            if footprint_root
            else None
        ),
        additional_footprint_roots=[
            _resolve_config_path(path, project.root) for path in extra_roots
        ],
        catalog_output=resolved_output,
    )


def _version_key(version: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", version)
    return tuple(int(number) for number in numbers) if numbers else (0,)


def get_kicad_version(executable: Optional[pathlib.Path]) -> str:
    if executable is None:
        return "unknown"
    try:
        result = subprocess.run(
            [str(executable), "version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return result.stdout.strip() or result.stderr.strip() or "unknown"


def _executable_candidates(platform_name: str) -> list[pathlib.Path]:
    candidates: list[pathlib.Path] = []
    found = shutil.which("kicad-cli")
    if found:
        candidates.append(pathlib.Path(found))

    if platform_name == "darwin":
        for applications in (
            pathlib.Path("/Applications"),
            pathlib.Path.home() / "Applications",
        ):
            candidates.extend(applications.glob("KiCad*.app/Contents/MacOS/kicad-cli"))
            candidates.append(
                applications
                / "KiCad"
                / "KiCad.app"
                / "Contents"
                / "MacOS"
                / "kicad-cli"
            )
    elif platform_name.startswith("win"):
        for variable in ("ProgramFiles", "ProgramFiles(x86)"):
            program_files = os.environ.get(variable)
            if program_files:
                candidates.extend(
                    pathlib.Path(program_files).glob("KiCad/*/bin/kicad-cli.exe")
                )
                candidates.append(
                    pathlib.Path(program_files) / "KiCad" / "bin" / "kicad-cli.exe"
                )
    else:
        candidates.extend(
            [
                pathlib.Path("/usr/bin/kicad-cli"),
                pathlib.Path("/usr/local/bin/kicad-cli"),
            ]
        )

    unique: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved not in seen and resolved.is_file():
            seen.add(resolved)
            unique.append(resolved)
    return unique


def _footprint_root_candidates(
    executable: Optional[pathlib.Path], platform_name: str
) -> list[pathlib.Path]:
    candidates: list[pathlib.Path] = []
    if executable is not None:
        if platform_name == "darwin" and executable.parent.name == "MacOS":
            candidates.append(executable.parent.parent / "SharedSupport" / "footprints")
        elif platform_name.startswith("win"):
            candidates.append(
                executable.parent.parent / "share" / "kicad" / "footprints"
            )
            candidates.append(executable.parent.parent / "share" / "kicad" / "modules")
        else:
            prefix = executable.parent.parent
            candidates.append(prefix / "share" / "kicad" / "footprints")
            candidates.append(prefix / "share" / "kicad" / "modules")
    if platform_name == "darwin":
        candidates.append(
            pathlib.Path(
                "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints"
            )
        )
    elif not platform_name.startswith("win"):
        candidates.extend(
            [
                pathlib.Path("/usr/share/kicad/footprints"),
                pathlib.Path("/usr/share/kicad/modules"),
                pathlib.Path("/usr/local/share/kicad/footprints"),
            ]
        )
    return candidates


def _is_footprint_root(path: pathlib.Path) -> bool:
    return path.is_dir() and any(path.glob("*.pretty"))


def detect_kicad_installation(
    executable: Optional[Union[str, pathlib.Path]] = None,
    footprint_root: Optional[Union[str, pathlib.Path]] = None,
    platform_name: Optional[str] = None,
) -> Optional[KicadInstallation]:
    platform_name = platform_name or sys.platform
    explicit_executable = (
        pathlib.Path(executable).expanduser().resolve() if executable else None
    )
    explicit_root = (
        pathlib.Path(footprint_root).expanduser().resolve() if footprint_root else None
    )

    if explicit_root is not None:
        return KicadInstallation(
            executable=explicit_executable,
            footprint_root=explicit_root,
            version=get_kicad_version(explicit_executable),
        )

    executables = (
        [explicit_executable]
        if explicit_executable
        else _executable_candidates(platform_name)
    )
    installations: list[KicadInstallation] = []
    for candidate in executables:
        for root in _footprint_root_candidates(candidate, platform_name):
            if _is_footprint_root(root):
                installations.append(
                    KicadInstallation(
                        executable=candidate,
                        footprint_root=root.resolve(),
                        version=get_kicad_version(candidate),
                    )
                )
                break

    if not installations:
        for root in _footprint_root_candidates(None, platform_name):
            if _is_footprint_root(root):
                installations.append(
                    KicadInstallation(
                        executable=explicit_executable,
                        footprint_root=root.resolve(),
                        version=get_kicad_version(explicit_executable),
                    )
                )
    if not installations:
        return None
    return max(installations, key=lambda item: _version_key(item.version))


def _standard_path_comments(platform_name: str) -> list[str]:
    if platform_name == "darwin":
        return [
            "# Standard macOS executable: /Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
            "# Standard macOS footprints: /Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints",
        ]
    if platform_name.startswith("win"):
        return [
            "# Standard Windows executable: C:/Program Files/KiCad/<version>/bin/kicad-cli.exe",
            "# Standard Windows footprints: C:/Program Files/KiCad/<version>/share/kicad/footprints",
        ]
    return [
        "# Standard Linux executable: /usr/bin/kicad-cli",
        "# Standard Linux footprints: /usr/share/kicad/footprints",
    ]


def write_config(
    project: ProjectPaths,
    installation: Optional[KicadInstallation],
    existing: Optional[KicadConfig] = None,
    platform_name: Optional[str] = None,
) -> KicadConfig:
    platform_name = platform_name or sys.platform
    config = KicadConfig(
        executable=installation.executable if installation else None,
        footprint_root=installation.footprint_root if installation else None,
        additional_footprint_roots=(
            list(existing.additional_footprint_roots) if existing else []
        ),
        catalog_output=existing.catalog_output if existing else ENVIRONMENT_OUTPUT,
    )
    if project.config.is_file():
        try:
            document = yaml.safe_load(project.config.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise KicadCatalogError(
                f"Unable to read Earthground config {project.config}: {exc}"
            ) from exc
        if not isinstance(document, dict):
            raise KicadCatalogError(
                f"{project.config} must contain a top-level YAML mapping"
            )
    else:
        document = {"project": {"design_class": None}}

    document["kicad"] = {
        "executable": str(config.executable) if config.executable else None,
        "footprint_root": str(config.footprint_root) if config.footprint_root else None,
        "additional_footprint_roots": [
            str(path) for path in config.additional_footprint_roots
        ],
        "catalog_output": (
            str(config.catalog_output)
            if config.catalog_output != ENVIRONMENT_OUTPUT
            else ENVIRONMENT_OUTPUT
        ),
    }
    comments = [
        "# Generated by Earthground. Edit this file to select another KiCad installation.",
        "# Set project.design_class to python.module:DesignClass before using `earthground compile`.",
        *_standard_path_comments(platform_name),
    ]
    project.config.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(comments) + "\n" + yaml.safe_dump(document, sort_keys=False)
    _atomic_write(project.config, content)
    return config


def initialize_project(
    project: ProjectPaths,
    force: bool = False,
    executable: Optional[Union[str, pathlib.Path]] = None,
    footprint_root: Optional[Union[str, pathlib.Path]] = None,
    platform_name: Optional[str] = None,
) -> KicadConfig:
    if project.config.is_file() and not force:
        return load_config(project)
    existing: Optional[KicadConfig] = None
    if project.config.is_file():
        existing = load_config(project)
    installation = detect_kicad_installation(
        executable=executable,
        footprint_root=footprint_root,
        platform_name=platform_name,
    )
    return write_config(project, installation, existing, platform_name)


def _deduplicate_paths(paths: Iterable[pathlib.Path]) -> tuple[pathlib.Path, ...]:
    result: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for path in paths:
        resolved = path.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return tuple(result)


def scan_footprints(roots: Sequence[pathlib.Path]) -> tuple[FootprintEntry, ...]:
    entries: dict[str, FootprintEntry] = {}
    for root in roots:
        if not _is_footprint_root(root):
            raise KicadCatalogError(
                f"KiCad footprint root does not contain *.pretty libraries: {root}"
            )
        for library_path in sorted(root.glob("*.pretty"), key=lambda path: path.name):
            library = library_path.stem
            for footprint_path in sorted(
                library_path.glob("*.kicad_mod"), key=lambda path: path.name
            ):
                entry = FootprintEntry(library, footprint_path.stem, footprint_path)
                entries.setdefault(entry.canonical_name, entry)
    return tuple(sorted(entries.values(), key=lambda item: item.canonical_name))


def find_footprint_path(
    roots: Sequence[pathlib.Path], library: str, footprint_name: str
) -> pathlib.Path:
    """Find one footprint in precedence-ordered KiCad library roots."""
    library_path = library if library.endswith(".pretty") else f"{library}.pretty"
    footprint_path = (
        footprint_name
        if footprint_name.endswith(".kicad_mod")
        else f"{footprint_name}.kicad_mod"
    )
    for root in roots:
        candidate = root / library_path / footprint_path
        if candidate.is_file():
            return candidate
    searched = ", ".join(str(root) for root in roots)
    raise KicadCatalogError(
        f"Footprint '{library}:{footprint_name}' was not found in: {searched}"
    )


def read_footprint_description(path: pathlib.Path) -> Optional[str]:
    """Read a KiCad footprint's description without constructing its geometry."""
    try:
        with path.open(encoding="utf-8", errors="replace") as footprint:
            header = footprint.read(65536)
    except OSError:
        return None

    string_value = r'"((?:\\.|[^"\\])*)"'
    for pattern in (
        rf"\(descr\s+{string_value}\s*\)",
        rf'\(property\s+"Description"\s+{string_value}',
    ):
        match = re.search(pattern, header)
        if match:
            encoded = match.group(1)
            try:
                return json.loads(f'"{encoded}"')
            except json.JSONDecodeError:
                return encoded.replace(r"\"", '"').replace(r"\\", "\\")

    try:
        model = read_from_file(path).model
    except Exception:
        return None
    if not isinstance(model, Footprint):
        return None
    if model.description:
        return model.description
    description = next(
        (item.value for item in model.property if item.name == "Description"),
        None,
    )
    return description


def resolve_footprint_roots(
    additional_roots: Sequence[Union[str, pathlib.Path]] = (),
    project_root: Optional[Union[str, pathlib.Path]] = None,
    config_path: Optional[Union[str, pathlib.Path]] = None,
    executable: Optional[Union[str, pathlib.Path]] = None,
    initialize: bool = False,
) -> tuple[pathlib.Path, ...]:
    """Resolve importer search roots without building the footprint inventory."""
    project = get_project_paths(project_root, config_path)
    if project.config.is_file():
        config = load_config(project)
    elif initialize:
        config = initialize_project(project, executable=executable)
    else:
        detected = detect_kicad_installation(executable=executable)
        if detected is None:
            config = KicadConfig()
        else:
            config = KicadConfig(
                executable=detected.executable,
                footprint_root=detected.footprint_root,
            )

    roots: list[pathlib.Path] = [
        *(pathlib.Path(path) for path in additional_roots),
        *config.additional_footprint_roots,
    ]
    installation = None
    if config.footprint_root is not None or config.executable is not None:
        installation = detect_kicad_installation(
            executable=executable or config.executable,
            footprint_root=config.footprint_root,
        )
    if installation is not None and _is_footprint_root(installation.footprint_root):
        roots.append(installation.footprint_root)
    usable_roots = _deduplicate_paths(roots)
    if not usable_roots:
        raise KicadCatalogError(
            "No usable KiCad footprint installation was found. Run "
            "`earthground kicad catalog generate` from the project root."
        )
    return usable_roots


def _earthground_version() -> str:
    try:
        return importlib.metadata.version("earthground")
    except importlib.metadata.PackageNotFoundError:
        return "development"


def calculate_fingerprint(
    installation: KicadInstallation,
    roots: Sequence[pathlib.Path],
    entries: Sequence[FootprintEntry],
) -> str:
    payload = {
        "schema": CATALOG_SCHEMA,
        "earthground_version": _earthground_version(),
        "kicad_version": installation.version,
        "roots": [str(path) for path in roots],
        "footprints": [entry.canonical_name for entry in entries],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def environment_catalog_path(package_directory: pathlib.Path) -> pathlib.Path:
    return package_directory / "_generated.py"


def resolve_context(
    package_directory: Optional[pathlib.Path] = None,
    project_root: Optional[Union[str, pathlib.Path]] = None,
    config_path: Optional[Union[str, pathlib.Path]] = None,
    executable: Optional[Union[str, pathlib.Path]] = None,
    footprint_roots: Sequence[Union[str, pathlib.Path]] = (),
    output: Optional[Union[str, pathlib.Path]] = None,
    initialize: bool = True,
) -> CatalogContext:
    project = get_project_paths(project_root, config_path)
    if not project.config.is_file():
        if initialize:
            initialize_project(project, executable=executable)
        else:
            detected = detect_kicad_installation(executable=executable)
            config = KicadConfig(
                executable=detected.executable if detected else None,
                footprint_root=detected.footprint_root if detected else None,
            )
    if project.config.is_file():
        config = load_config(project)

    selected_executable = (
        pathlib.Path(executable).expanduser().resolve()
        if executable is not None
        else config.executable
    )
    installation = detect_kicad_installation(
        executable=selected_executable,
        footprint_root=config.footprint_root,
    )
    if installation is None or not _is_footprint_root(installation.footprint_root):
        raise KicadCatalogError(
            "No usable KiCad footprint installation was found. Edit "
            f"{project.config}, or remove it and rerun "
            "`earthground kicad catalog generate` to detect KiCad again."
        )

    cli_roots = [pathlib.Path(path) for path in footprint_roots]
    roots = _deduplicate_paths(
        [*cli_roots, *config.additional_footprint_roots, installation.footprint_root]
    )
    entries = scan_footprints(roots)

    selected_output: Union[str, pathlib.Path] = (
        output if output is not None else config.catalog_output
    )
    environment_output = selected_output == ENVIRONMENT_OUTPUT
    if environment_output:
        if package_directory is None:
            import earthground.footprints

            package_directory = (
                pathlib.Path(earthground.footprints.__file__).parent / "kicad"
            )
        output_path = environment_catalog_path(package_directory)
    else:
        output_path = pathlib.Path(selected_output).expanduser()
        if not output_path.is_absolute():
            output_path = pathlib.Path.cwd() / output_path
        output_path = output_path.resolve()
        if output_path.suffix != ".py":
            raise KicadCatalogError("A standalone catalog output must end in '.py'")

    fingerprint = calculate_fingerprint(installation, roots, entries)
    return CatalogContext(
        project=project,
        config=config,
        installation=installation,
        roots=roots,
        output=output_path,
        environment_output=environment_output,
        entries=entries,
        fingerprint=fingerprint,
    )


def python_identifier(name: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not identifier:
        identifier = "_"
    if identifier[0].isdigit():
        identifier = f"_{identifier}"
    if keyword.iskeyword(identifier):
        identifier += "_"
    return identifier


def _unique_identifier(name: str, used: dict[str, str]) -> str:
    identifier = python_identifier(name)
    existing = used.get(identifier)
    if existing is not None and existing != name:
        suffix = hashlib.sha256(name.encode()).hexdigest()[:8].upper()
        base_identifier = identifier
        identifier = f"{base_identifier}_{suffix}"
        counter = 2
        while identifier in used and used[identifier] != name:
            identifier = f"{base_identifier}_{suffix}_{counter}"
            counter += 1
    used[identifier] = name
    return identifier


def render_catalog(context: CatalogContext) -> tuple[str, list[str]]:
    by_library: dict[str, list[FootprintEntry]] = {}
    for entry in context.entries:
        by_library.setdefault(entry.library, []).append(entry)

    class_names: list[str] = []
    used_classes: dict[str, str] = {}
    lines = [
        "# Generated by Earthground. Do not edit.",
        "from earthground.footprint_types import KicadFootprintRef",
        "",
        f"__catalog_fingerprint__ = {context.fingerprint!r}",
        "",
    ]
    for library, entries in sorted(by_library.items()):
        class_name = _unique_identifier(library, used_classes)
        class_names.append(class_name)
        lines.append(f"class {class_name}(KicadFootprintRef):")
        used_members: dict[str, str] = {}
        for entry in entries:
            member = _unique_identifier(entry.footprint_name, used_members)
            lines.append(
                f"    {member} = ({entry.library!r}, {entry.footprint_name!r})"
            )
        lines.append("")
    lines.append(f"__all__ = {class_names!r}")
    lines.append("")
    return "\n".join(lines), class_names


def render_export_stub(class_names: Sequence[str]) -> str:
    lines = ["# Generated by Earthground. Do not edit."]
    for class_name in class_names:
        lines.append(f"from ._generated import {class_name} as {class_name}")
    lines.append("")
    lines.append(f"__all__ = {list(class_names)!r}")
    lines.append("")
    return "\n".join(lines)


def _atomic_write(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    except OSError as exc:
        if temporary_name:
            try:
                pathlib.Path(temporary_name).unlink()
            except OSError:
                pass
        raise KicadCatalogError(f"Unable to write {path}: {exc}") from exc


def read_catalog_fingerprint(path: pathlib.Path) -> Optional[str]:
    if not path.is_file():
        return None
    pattern = re.compile(r"^__catalog_fingerprint__ = ['\"]([0-9a-f]+)['\"]$")
    try:
        with path.open(encoding="utf-8") as catalog:
            for _ in range(10):
                line = catalog.readline()
                if not line:
                    break
                match = pattern.match(line.rstrip())
                if match:
                    return match.group(1)
    except OSError:
        return None
    return None


def catalog_is_fresh(context: CatalogContext) -> bool:
    return read_catalog_fingerprint(context.output) == context.fingerprint


def _metadata(context: CatalogContext) -> dict:
    return {
        "schema": CATALOG_SCHEMA,
        "earthground_version": _earthground_version(),
        "kicad_version": context.installation.version,
        "kicad_executable": (
            str(context.installation.executable)
            if context.installation.executable
            else None
        ),
        "roots": [str(root) for root in context.roots],
        "output": str(context.output),
        "fingerprint": context.fingerprint,
        "footprint_count": len(context.entries),
    }


def generate_catalog(context: CatalogContext, force: bool = False) -> bool:
    """Generate a catalog and return whether its Python output changed."""
    export_stub = context.output.parent / "_generated_exports.pyi"
    changed = (
        force
        or not catalog_is_fresh(context)
        or (context.environment_output and not export_stub.is_file())
    )
    if changed:
        source, class_names = render_catalog(context)
        _atomic_write(context.output, source)
        if context.environment_output:
            _atomic_write(export_stub, render_export_stub(class_names))
        importlib.invalidate_caches()
    metadata = json.dumps(_metadata(context), indent=2, sort_keys=True) + "\n"
    try:
        current_metadata = context.project.metadata.read_text(encoding="utf-8")
    except OSError:
        current_metadata = None
    if current_metadata != metadata:
        _atomic_write(context.project.metadata, metadata)
    return changed


def ensure_environment_catalog(package_directory: pathlib.Path) -> CatalogContext:
    context = resolve_context(package_directory=package_directory, initialize=True)
    if not context.environment_output:
        raise KicadCatalogError(
            f"{context.project.config} configures standalone output "
            f"{context.output}. Run `earthground kicad catalog generate` and "
            "import that module by its project module path."
        )
    generate_catalog(context)
    return context
