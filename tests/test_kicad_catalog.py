import importlib.util
import json
from pathlib import Path

import pytest

import earthground.kicad.catalog as catalog
from earthground.cli import main as earthground_main
from earthground.footprint_types import KicadFootprintRef
from earthground.importers.kicad import KicadImporter
from earthground.cli.generate_kicad_footprints import main


def _make_library(root: Path, library: str, footprints: list[str]) -> Path:
    library_path = root / f"{library}.pretty"
    library_path.mkdir(parents=True)
    for footprint in footprints:
        (library_path / f"{footprint}.kicad_mod").write_text(
            f'(footprint "{footprint}")', encoding="utf-8"
        )
    return library_path


def _write_config(
    project: Path,
    footprint_root: Path,
    *,
    additional_roots: list[Path] | None = None,
    output: str = "environment",
) -> Path:
    config_path = project / ".earthground" / "config.yaml"
    config_path.parent.mkdir(parents=True)
    extras = additional_roots or []
    extra_yaml = "\n".join(f"      - {path}" for path in extras)
    if not extra_yaml:
        extra_yaml = "      []"
    config_path.write_text(
        "\n".join(
            [
                "kicad:",
                "  executable: null",
                f"  footprint_root: {footprint_root}",
                "  additional_footprint_roots:",
                extra_yaml,
                f"  catalog_output: {output}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def test_find_project_root_searches_upward(tmp_path, monkeypatch):
    project = tmp_path / "board"
    nested = project / "src" / "circuits"
    nested.mkdir(parents=True)
    (project / ".earthground").mkdir()
    (project / ".earthground" / "config.yaml").write_text("kicad: {}", encoding="utf-8")

    monkeypatch.chdir(nested)

    assert catalog.find_project_root() == project


def test_find_project_root_environment_override(tmp_path, monkeypatch):
    project = tmp_path / "selected"
    project.mkdir()
    monkeypatch.setenv("EARTHGROUND_PROJECT_ROOT", str(project))

    assert catalog.find_project_root() == project


def test_initialize_project_writes_detected_standard_paths(tmp_path, monkeypatch):
    project = catalog.get_project_paths(tmp_path)
    footprint_root = tmp_path / "kicad" / "footprints"
    _make_library(footprint_root, "Connector_JST", ["JST-SH"])
    executable = tmp_path / "kicad-cli"
    executable.write_text("", encoding="utf-8")
    installation = catalog.KicadInstallation(
        executable=executable,
        footprint_root=footprint_root,
        version="10.0.0",
    )
    monkeypatch.setattr(
        catalog, "detect_kicad_installation", lambda **kwargs: installation
    )

    config = catalog.initialize_project(project, platform_name="darwin")
    loaded = catalog.load_config(project)

    assert project.config.is_file()
    assert config.executable == executable
    assert loaded.footprint_root == footprint_root
    assert loaded.catalog_output == catalog.ENVIRONMENT_OUTPUT
    assert "Standard macOS" in project.config.read_text(encoding="utf-8")


def test_initialize_force_preserves_user_settings(tmp_path, monkeypatch):
    project = catalog.get_project_paths(tmp_path)
    old_root = tmp_path / "old"
    custom_root = tmp_path / "custom"
    output = tmp_path / "catalog.py"
    _make_library(old_root, "Old", ["One"])
    _make_library(custom_root, "Custom", ["Two"])
    _write_config(
        tmp_path,
        old_root,
        additional_roots=[custom_root],
        output=str(output),
    )
    new_root = tmp_path / "new"
    _make_library(new_root, "New", ["Three"])
    installation = catalog.KicadInstallation(None, new_root, "11.0.0")
    monkeypatch.setattr(
        catalog, "detect_kicad_installation", lambda **kwargs: installation
    )

    catalog.initialize_project(project, force=True)
    loaded = catalog.load_config(project)

    assert loaded.footprint_root == new_root
    assert loaded.additional_footprint_roots == [custom_root]
    assert loaded.catalog_output == output


def test_scan_footprints_uses_root_precedence_and_sorted_output(tmp_path):
    custom = tmp_path / "custom"
    standard = tmp_path / "standard"
    _make_library(custom, "Library", ["Shared", "Custom"])
    _make_library(standard, "Library", ["Shared", "Standard"])

    entries = catalog.scan_footprints([custom, standard])

    assert [entry.canonical_name for entry in entries] == [
        "Library:Custom",
        "Library:Shared",
        "Library:Standard",
    ]


def test_render_catalog_normalizes_identifiers_and_preserves_values(tmp_path):
    context = catalog.CatalogContext(
        project=catalog.get_project_paths(tmp_path),
        config=catalog.KicadConfig(),
        installation=catalog.KicadInstallation(None, tmp_path, "10.0"),
        roots=(tmp_path,),
        output=tmp_path / "catalog.py",
        environment_output=False,
        entries=(
            catalog.FootprintEntry("Connector_FFC-FPC", "1.00mm-Part"),
            catalog.FootprintEntry("Connector_FFC-FPC", "class"),
        ),
        fingerprint="abc123",
    )

    source, classes = catalog.render_catalog(context)

    assert classes == ["Connector_FFC_FPC"]
    assert "class Connector_FFC_FPC(KicadFootprintRef):" in source
    assert "_1_00mm_Part = ('Connector_FFC-FPC', '1.00mm-Part')" in source
    assert "class_ = ('Connector_FFC-FPC', 'class')" in source


def test_generate_standalone_catalog_and_import_it(tmp_path):
    root = tmp_path / "footprints"
    _make_library(root, "Connector_JST", ["JST-SH_1.00"])
    project = catalog.get_project_paths(tmp_path)
    context = catalog.CatalogContext(
        project=project,
        config=catalog.KicadConfig(),
        installation=catalog.KicadInstallation(None, root, "10.0"),
        roots=(root,),
        output=tmp_path / "generated_catalog.py",
        environment_output=False,
        entries=catalog.scan_footprints([root]),
        fingerprint="abc123",
    )

    assert catalog.generate_catalog(context) is True
    assert catalog.generate_catalog(context) is False

    spec = importlib.util.spec_from_file_location("generated_catalog", context.output)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    member = module.Connector_JST.JST_SH_1_00

    assert isinstance(member, KicadFootprintRef)
    assert member.library == "Connector_JST"
    assert member.footprint_name == "JST-SH_1.00"
    metadata = json.loads(project.metadata.read_text(encoding="utf-8"))
    assert metadata["footprint_count"] == 1


def test_read_footprint_description_supports_descr_and_property(tmp_path):
    described = tmp_path / "described.kicad_mod"
    described.write_text(
        '(footprint "Described" (descr "Primary description"))',
        encoding="utf-8",
    )
    property_description = tmp_path / "property.kicad_mod"
    property_description.write_text(
        '(footprint "Property" (property "Description" "Property description"))',
        encoding="utf-8",
    )

    assert catalog.read_footprint_description(described) == "Primary description"
    assert (
        catalog.read_footprint_description(property_description)
        == "Property description"
    )


def test_environment_generation_writes_autocomplete_exports(tmp_path):
    root = tmp_path / "footprints"
    _make_library(root, "Package_QFN", ["QFN-16"])
    package = tmp_path / "kicad_package"
    project = catalog.get_project_paths(tmp_path)
    entries = catalog.scan_footprints([root])
    installation = catalog.KicadInstallation(None, root, "10.0")
    context = catalog.CatalogContext(
        project=project,
        config=catalog.KicadConfig(),
        installation=installation,
        roots=(root,),
        output=catalog.environment_catalog_path(package),
        environment_output=True,
        entries=entries,
        fingerprint=catalog.calculate_fingerprint(installation, [root], entries),
    )

    catalog.generate_catalog(context)

    exports = (package / "_generated_exports.pyi").read_text(encoding="utf-8")
    assert "from ._generated import Package_QFN as Package_QFN" in exports
    assert catalog.catalog_is_fresh(context)


def test_ensure_environment_catalog_initializes_project(tmp_path, monkeypatch):
    project = tmp_path / "board"
    project.mkdir()
    root = tmp_path / "footprints"
    _make_library(root, "Package_QFN", ["QFN-16"])
    package = tmp_path / "site-packages" / "earthground" / "footprints" / "kicad"
    installation = catalog.KicadInstallation(None, root, "10.0")
    monkeypatch.setenv("EARTHGROUND_PROJECT_ROOT", str(project))
    monkeypatch.setattr(
        catalog, "detect_kicad_installation", lambda **kwargs: installation
    )

    context = catalog.ensure_environment_catalog(package)

    assert context.output == package / "_generated.py"
    assert context.output.is_file()
    assert (package / "_generated_exports.pyi").is_file()
    assert (project / ".earthground" / "config.yaml").is_file()
    assert (project / ".earthground" / "kicad-catalog.json").is_file()


def test_importer_accepts_generated_enum_and_legacy_strings(tmp_path, monkeypatch):
    project = tmp_path / "board"
    root = tmp_path / "footprints"
    _make_library(root, "Test_Library", ["Test-Footprint"])
    _write_config(project, root)
    monkeypatch.setenv("EARTHGROUND_PROJECT_ROOT", str(project))

    class TestLibrary(KicadFootprintRef):
        Test_Footprint = ("Test_Library", "Test-Footprint")

    importer = KicadImporter()
    enum_footprint = importer.import_footprint(TestLibrary.Test_Footprint)
    string_footprint = importer.import_footprint("Test_Library", "Test-Footprint")

    assert enum_footprint.sexp == string_footprint.sexp
    assert enum_footprint.name == "Test-Footprint"


def test_importer_can_use_only_an_explicit_custom_root(tmp_path, monkeypatch):
    project = tmp_path / "board"
    project.mkdir()
    root = tmp_path / "footprints"
    _make_library(root, "Custom", ["Only"])
    monkeypatch.setenv("EARTHGROUND_PROJECT_ROOT", str(project))
    monkeypatch.setattr(catalog, "detect_kicad_installation", lambda **kwargs: None)

    importer = KicadImporter([root])

    assert importer.import_footprint("Custom", "Only").name == "Only"


def test_cli_generate_and_status(tmp_path, capsys):
    project = tmp_path / "board"
    root = tmp_path / "footprints"
    output = tmp_path / "catalog.py"
    _make_library(root, "Library", ["Footprint"])
    _write_config(project, root, output=str(output))

    assert main(["generate", "--project-root", str(project)]) == 0
    assert main(["status", "--project-root", str(project)]) == 0

    stdout = capsys.readouterr().out
    assert "Footprints: 1" in stdout
    assert "Catalog status: current" in stdout


def test_hierarchical_generate_creates_missing_config(tmp_path, monkeypatch):
    project = tmp_path / "board"
    project.mkdir()
    root = tmp_path / "footprints"
    output = tmp_path / "catalog.py"
    _make_library(root, "Library", ["Footprint"])
    installation = catalog.KicadInstallation(None, root, "10.0")
    monkeypatch.setattr(
        catalog, "detect_kicad_installation", lambda **kwargs: installation
    )

    result = earthground_main(
        [
            "kicad",
            "catalog",
            "generate",
            "--project-root",
            str(project),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert (project / ".earthground" / "config.yaml").is_file()
    assert output.is_file()


def test_cli_status_does_not_create_missing_config(tmp_path, monkeypatch):
    project = tmp_path / "board"
    project.mkdir()
    root = tmp_path / "footprints"
    _make_library(root, "Library", ["Footprint"])
    installation = catalog.KicadInstallation(None, root, "10.0")
    monkeypatch.setattr(
        catalog, "detect_kicad_installation", lambda **kwargs: installation
    )

    assert main(["status", "--project-root", str(project)]) == 1
    assert not (project / ".earthground" / "config.yaml").exists()


def test_cli_get_does_not_create_missing_config(tmp_path, monkeypatch, capsys):
    project = tmp_path / "board"
    project.mkdir()
    root = tmp_path / "footprints"
    _make_library(root, "Library", ["Footprint"])
    installation = catalog.KicadInstallation(None, root, "10.0")
    monkeypatch.setattr(
        catalog, "detect_kicad_installation", lambda **kwargs: installation
    )

    assert (
        earthground_main(
            [
                "kicad",
                "catalog",
                "get",
                "--project-root",
                str(project),
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["footprint_count"] == 1
    assert not (project / ".earthground" / "config.yaml").exists()


def test_hierarchical_cli_gets_footprint_description_as_json(tmp_path, capsys):
    project = tmp_path / "board"
    root = tmp_path / "footprints"
    library = _make_library(root, "Connector_JST", ["JST-SH"])
    (library / "JST-SH.kicad_mod").write_text(
        '(footprint "JST-SH" (descr "JST SH connector"))',
        encoding="utf-8",
    )
    _write_config(project, root)

    result = earthground_main(
        [
            "kicad",
            "catalog",
            "get",
            "--project-root",
            str(project),
            "--json",
            "Connector_JST:JST-SH",
        ]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["reference"] == "Connector_JST:JST-SH"
    assert output["description"] == "JST SH connector"
    assert output["path"].endswith("Connector_JST.pretty/JST-SH.kicad_mod")


def test_hierarchical_cli_get_lists_all_libraries_and_footprints(tmp_path, capsys):
    project = tmp_path / "board"
    root = tmp_path / "footprints"
    jst_library = _make_library(root, "Connector_JST", ["JST-A", "JST-B"])
    (jst_library / "JST-A.kicad_mod").write_text(
        '(footprint "JST-A" (descr "JST connector A"))',
        encoding="utf-8",
    )
    _make_library(root, "Package_QFN", ["QFN-16"])
    _write_config(project, root)

    result = earthground_main(
        [
            "kicad",
            "catalog",
            "get",
            "--project-root",
            str(project),
            "--json",
        ]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["library_count"] == 2
    assert output["footprint_count"] == 3
    assert output["libraries"] == {
        "Connector_JST": [
            {"description": "JST connector A", "name": "JST-A"},
            {"description": None, "name": "JST-B"},
        ],
        "Package_QFN": [{"description": None, "name": "QFN-16"}],
    }


def test_hierarchical_cli_get_can_list_one_library(tmp_path, capsys):
    project = tmp_path / "board"
    root = tmp_path / "footprints"
    _make_library(root, "Connector_JST", ["JST-A", "JST-B"])
    _make_library(root, "Package_QFN", ["QFN-16"])
    _write_config(project, root)

    result = earthground_main(
        [
            "kicad",
            "catalog",
            "get",
            "--project-root",
            str(project),
            "Connector_JST",
        ]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "Connector_JST:" in output
    assert "  JST-A" in output
    assert "Description: (none provided)" in output
    assert "Package_QFN" not in output
    assert "Footprints: 2" in output


def test_hierarchical_cli_get_accepts_separate_names(tmp_path, capsys):
    project = tmp_path / "board"
    root = tmp_path / "footprints"
    _make_library(root, "Library", ["Footprint"])
    _write_config(project, root)

    result = earthground_main(
        [
            "kicad",
            "catalog",
            "get",
            "--project-root",
            str(project),
            "Library",
            "Footprint",
        ]
    )

    assert result == 0
    output = capsys.readouterr().out
    assert "Reference: Library:Footprint" in output
    assert "Description: (none provided)" in output
