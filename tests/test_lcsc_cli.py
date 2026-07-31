import json
import sqlite3
from pathlib import Path

import pytest

from earthground.cli import main
from earthground.cli.lcsc import (
    LcscDatabaseError,
    get_database_path,
    lookup_parts,
)


def _create_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("""
            CREATE TABLE components (
                lcsc INTEGER PRIMARY KEY,
                mfr TEXT NOT NULL,
                package TEXT NOT NULL,
                description TEXT NOT NULL,
                preferred INTEGER NOT NULL DEFAULT 0,
                stock INTEGER NOT NULL DEFAULT 0
            )
            """)
        connection.executemany(
            """
            INSERT INTO components
                (lcsc, mfr, package, description, preferred, stock)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (132291, "FUSB302B", "QFN-14", "USB Type-C controller", 1, 50),
                (5187527, "CH334R", "QFN-32", "Four-port USB hub", 0, 100),
                (999, "DUPLICATE", "SOP-8", "Preferred option", 1, 10),
                (1000, "DUPLICATE", "SOP-8", "Stocked option", 0, 100),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def _create_project(tmp_path: Path) -> tuple[Path, Path]:
    project = tmp_path / "board"
    config = project / ".earthground" / "config.yaml"
    config.parent.mkdir(parents=True)
    database = project / "parts.sqlite3"
    _create_database(database)
    config.write_text(
        "\n".join(
            [
                "lcsc:",
                "  db: ./parts.sqlite3",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return project, database


def test_get_database_path_resolves_relative_to_project(tmp_path):
    project, database = _create_project(tmp_path)

    assert get_database_path(project_root=project) == database


def test_lookup_parts_returns_c_prefixed_ids_case_insensitively(tmp_path):
    _, database = _create_project(tmp_path)

    matches = lookup_parts(database, "fusb302b")

    assert len(matches) == 1
    assert matches[0].lcsc_id == "C132291"
    assert matches[0].mpn == "FUSB302B"


def test_lookup_parts_returns_deterministic_multiple_matches(tmp_path):
    _, database = _create_project(tmp_path)

    matches = lookup_parts(database, "DUPLICATE")

    assert [match.lcsc_id for match in matches] == ["C999", "C1000"]


def test_hierarchical_lcsc_lookup_human_and_id_only(tmp_path, capsys):
    project, _ = _create_project(tmp_path)

    assert (
        main(
            [
                "lcsc",
                "lookup",
                "--project-root",
                str(project),
                "FUSB302B",
            ]
        )
        == 0
    )
    human = capsys.readouterr().out
    assert "MPN: FUSB302B" in human
    assert "LCSC ID: C132291" in human

    assert (
        main(
            [
                "lcsc",
                "lookup",
                "--project-root",
                str(project),
                "--id-only",
                "CH334R",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == "C5187527\n"


def test_hierarchical_lcsc_lookup_json_reports_missing_parts(tmp_path, capsys):
    project, _ = _create_project(tmp_path)

    result = main(
        [
            "lcsc",
            "lookup",
            "--project-root",
            str(project),
            "--json",
            "FUSB302B",
            "NOT-A-PART",
        ]
    )

    assert result == 1
    document = json.loads(capsys.readouterr().out)
    assert document["results"][0]["matches"][0]["lcsc_id"] == "C132291"
    assert document["results"][1] == {
        "query": "NOT-A-PART",
        "matches": [],
    }


def test_missing_lcsc_config_is_actionable(tmp_path):
    project = tmp_path / "board"
    (project / ".earthground").mkdir(parents=True)
    (project / ".earthground" / "config.yaml").write_text(
        "kicad: {}\n", encoding="utf-8"
    )

    with pytest.raises(LcscDatabaseError, match="'lcsc' mapping"):
        get_database_path(project_root=project)
