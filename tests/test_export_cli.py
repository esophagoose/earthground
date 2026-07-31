from pathlib import Path

from earthground.cli import main
from earthground.cli.export_kicad import export_kicad_project


def _create_design_file(
    tmp_path: Path,
    *,
    module_name: str,
    module_source: str,
    configured: bool = True,
) -> Path:
    project = tmp_path / module_name
    project.mkdir(parents=True)
    if configured:
        config = project / ".earthground" / "config.yaml"
        config.parent.mkdir()
        config.write_text("kicad: {}\n", encoding="utf-8")
    design_file = project / f"{module_name}.py"
    design_file.write_text(module_source, encoding="utf-8")
    return design_file


def test_export_kicad_writes_board_under_project(tmp_path, capsys):
    design_file = _create_design_file(
        tmp_path,
        module_name="exportable_board",
        module_source="\n".join(
            [
                "from earthground.schematic import Design",
                "",
                "class ExportableBoard(Design):",
                "    def __init__(self):",
                "        super().__init__('Exportable Board')",
                "",
            ]
        ),
    )

    assert main(["export", "kicad", str(design_file)]) == 0

    output_path = (
        design_file.parent / "generated_outputs" / "Exportable Board.kicad_pcb"
    )
    output = capsys.readouterr()
    assert output.err == ""
    assert f"Wrote board file: {output_path}" in output.out
    assert output_path.is_file()
    assert "(kicad_pcb" in output_path.read_text(encoding="utf-8")


def test_export_kicad_accepts_a_relative_design_file(tmp_path, monkeypatch, capsys):
    design_file = _create_design_file(
        tmp_path,
        module_name="current_export_board",
        module_source="\n".join(
            [
                "from earthground.schematic import Design",
                "",
                "class CurrentExportBoard(Design):",
                "    def __init__(self):",
                "        super().__init__('Current Export Board')",
                "",
            ]
        ),
    )
    monkeypatch.chdir(design_file.parent)

    assert main(["export", "kicad", design_file.name]) == 0
    assert "Current Export Board.kicad_pcb" in capsys.readouterr().out


def test_export_kicad_reports_overwrite(tmp_path, capsys):
    design_file = _create_design_file(
        tmp_path,
        module_name="overwrite_board",
        module_source="\n".join(
            [
                "from earthground.schematic import Design",
                "",
                "class OverwriteBoard(Design):",
                "    def __init__(self):",
                "        super().__init__('Overwrite Board')",
                "",
            ]
        ),
    )

    output_path = export_kicad_project(design_file)
    capsys.readouterr()
    assert output_path.is_file()

    assert main(["export", "kicad", str(design_file)]) == 0
    assert f"Overwrote board file: {output_path}" in capsys.readouterr().out


def test_export_kicad_stops_before_writing_when_validation_fails(tmp_path, capsys):
    design_file = _create_design_file(
        tmp_path,
        module_name="invalid_export_board",
        module_source="\n".join(
            [
                "from earthground.components import Component",
                "from earthground.schematic import Design",
                "",
                "class InvalidExportBoard(Design):",
                "    def __init__(self):",
                "        super().__init__('Invalid Export Board')",
                "        component = Component()",
                "        component.name = 'Missing footprint'",
                "        self.add_component(component)",
                "",
            ]
        ),
    )

    assert main(["export", "kicad", str(design_file)]) == 1

    output = capsys.readouterr()
    assert output.out == ""
    assert "Export failed validation for Invalid Export Board:" in output.err
    assert " - No footprint: Missing footprint" in output.err
    assert not (design_file.parent / "generated_outputs").exists()


def test_export_kicad_creates_missing_project_config(tmp_path, capsys):
    design_file = _create_design_file(
        tmp_path,
        module_name="unconfigured_export_board",
        configured=False,
        module_source="\n".join(
            [
                "from earthground.schematic import Design",
                "",
                "class UnconfiguredExportBoard(Design):",
                "    def __init__(self):",
                "        super().__init__('Unconfigured Export Board')",
                "",
            ]
        ),
    )

    assert main(["export", "kicad", str(design_file)]) == 0

    output = capsys.readouterr()
    assert output.err == ""
    assert (design_file.parent / ".earthground" / "config.yaml").is_file()


def test_export_kicad_uses_module_level_design(tmp_path, capsys):
    design_file = _create_design_file(
        tmp_path,
        module_name="module_design",
        module_source="\n".join(
            [
                "from earthground.schematic import Design",
                "",
                "design = Design('Module-level Design')",
                "",
            ]
        ),
    )

    assert main(["export", "kicad", str(design_file)]) == 0
    assert "Module-level Design.kicad_pcb" in capsys.readouterr().out


def test_export_kicad_discovers_project_above_nested_design_file(tmp_path, capsys):
    project = tmp_path / "workspace"
    config = project / ".earthground" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("kicad: {}\n", encoding="utf-8")
    design_file = project / "designs" / "boards" / "nested_board.py"
    design_file.parent.mkdir(parents=True)
    design_file.write_text(
        "\n".join(
            [
                "from earthground.schematic import Design",
                "",
                "design = Design('Nested Board')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["export", "kicad", str(design_file)]) == 0
    output_path = project / "generated_outputs" / "Nested Board.kicad_pcb"
    assert output_path.is_file()
    assert str(output_path) in capsys.readouterr().out


def test_export_kicad_imports_top_level_namespace_from_repository_root(
    tmp_path, capsys
):
    repository = tmp_path / "workspace"
    repository.joinpath(".git").mkdir(parents=True)
    project = repository / "hardware"
    config = project / ".earthground" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("kicad: {}\n", encoding="utf-8")
    helper = project / "library" / "design_name.py"
    helper.parent.mkdir(parents=True)
    helper.write_text("DESIGN_NAME = 'Import Root Fixture'\n", encoding="utf-8")
    design_file = project / "boards" / "namespaced_board.py"
    design_file.parent.mkdir(parents=True)
    design_file.write_text(
        "\n".join(
            [
                "from earthground.schematic import Design",
                "from hardware.library.design_name import DESIGN_NAME",
                "",
                "design = Design(DESIGN_NAME)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert main(["export", "kicad", str(design_file)]) == 0
    output_path = project / "generated_outputs" / "Import Root Fixture.kicad_pcb"
    assert output_path.is_file()
    assert str(output_path) in capsys.readouterr().out


def test_export_kicad_rejects_a_project_directory(tmp_path, capsys):
    project = tmp_path / "not_a_design_file"
    project.mkdir()

    assert main(["export", "kicad", str(project)]) == 2
    assert "Earthground design file not found" in capsys.readouterr().err
