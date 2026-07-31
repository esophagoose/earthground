from __future__ import annotations

import os
import pathlib
import sqlite3
from dataclasses import asdict, dataclass
from typing import Optional, Sequence, Union

import yaml

from earthground.kicad.catalog import get_project_paths


class LcscDatabaseError(RuntimeError):
    """Raised when the configured LCSC database cannot be queried."""


@dataclass(frozen=True)
class LcscPart:
    lcsc_id: str
    mpn: str
    package: str
    description: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def get_database_path(
    project_root: Optional[Union[str, pathlib.Path]] = None,
    config_path: Optional[Union[str, pathlib.Path]] = None,
) -> pathlib.Path:
    """Resolve ``lcsc.db`` from the project's Earthground config."""
    project = get_project_paths(project_root, config_path)
    if not project.config.is_file():
        raise LcscDatabaseError(
            f"Earthground config not found: {project.config}. Add an 'lcsc.db' path."
        )
    try:
        document = yaml.safe_load(project.config.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise LcscDatabaseError(
            f"Unable to read Earthground config {project.config}: {exc}"
        ) from exc
    if not isinstance(document, dict) or not isinstance(document.get("lcsc"), dict):
        raise LcscDatabaseError(
            f"{project.config} must contain an 'lcsc' mapping with a 'db' path"
        )
    configured_path = document["lcsc"].get("db")
    if not isinstance(configured_path, str) or not configured_path.strip():
        raise LcscDatabaseError(
            f"{project.config} must define a non-empty string at 'lcsc.db'"
        )

    expanded = pathlib.Path(os.path.expandvars(configured_path)).expanduser()
    if not expanded.is_absolute():
        expanded = project.root / expanded
    database_path = expanded.resolve()
    if not database_path.is_file():
        raise LcscDatabaseError(f"LCSC database not found: {database_path}")
    return database_path


def lookup_parts(database_path: pathlib.Path, mpn: str) -> tuple[LcscPart, ...]:
    """Return every exact manufacturer-part-number match."""
    normalized_mpn = mpn.strip()
    if not normalized_mpn:
        raise LcscDatabaseError("Manufacturer part number cannot be empty")

    query = """
        SELECT lcsc, mfr, package, description
        FROM components
        WHERE mfr = ? COLLATE NOCASE
        ORDER BY preferred DESC, stock DESC, lcsc ASC
    """
    try:
        connection = sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        try:
            rows = connection.execute(query, (normalized_mpn,)).fetchall()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise LcscDatabaseError(
            f"Unable to query LCSC database {database_path}: {exc}"
        ) from exc

    return tuple(
        LcscPart(
            lcsc_id=f"C{row['lcsc']}",
            mpn=row["mfr"],
            package=row["package"],
            description=row["description"],
        )
        for row in rows
    )


def lookup_many(
    database_path: pathlib.Path, mpns: Sequence[str]
) -> list[dict[str, object]]:
    return [
        {
            "query": mpn,
            "matches": [part.as_dict() for part in lookup_parts(database_path, mpn)],
        }
        for mpn in mpns
    ]
