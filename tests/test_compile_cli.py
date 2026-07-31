from pathlib import Path

import pytest

from earthground.cli import main
from earthground.schematic import SchematicValidationError
from earthground.cli.compile_project import (
    CompileProjectError,
    compile_project,
    load_design_class,
)


def _create_project(
    tmp_path: Path,
    *,
    module_name: str,
    class_name: str,
    module_source: str,
) -> Path:
    project = tmp_path / module_name
    config = project / ".earthground" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "\n".join(
            [
                "project:",
                f"  design_class: {module_name}:{class_name}",
                "kicad: {}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (project / f"{module_name}.py").write_text(module_source, encoding="utf-8")
    return project


def test_compile_loads_and_validates_configured_design(tmp_path, capsys):
    project = _create_project(
        tmp_path,
        module_name="valid_board",
        class_name="BoardDesign",
        module_source="\n".join(
            [
                "from earthground.schematic import Design",
                "",
                "class BoardDesign(Design):",
                "    def __init__(self):",
                "        super().__init__('Valid board')",
                "",
            ]
        ),
    )

    assert main(["compile", str(project)]) == 0

    output = capsys.readouterr()
    assert output.err == ""
    assert output.out == "Compiled Valid board: 0 components, 0 modules, 1 nets\n"


def test_compile_defaults_to_current_directory(tmp_path, monkeypatch, capsys):
    project = _create_project(
        tmp_path,
        module_name="current_board",
        class_name="CurrentBoard",
        module_source="\n".join(
            [
                "from earthground.schematic import Design",
                "",
                "class CurrentBoard(Design):",
                "    def __init__(self):",
                "        super().__init__('Current board')",
                "",
            ]
        ),
    )
    monkeypatch.chdir(project)

    assert main(["compile"]) == 0
    assert "Compiled Current board" in capsys.readouterr().out


def test_compile_keeps_project_importable_during_design_construction(tmp_path, capsys):
    project = _create_project(
        tmp_path,
        module_name="lazy_import_board",
        class_name="LazyImportBoard",
        module_source="\n".join(
            [
                "from earthground.schematic import Design",
                "",
                "class LazyImportBoard(Design):",
                "    def __init__(self):",
                "        from local_settings import DESIGN_NAME",
                "        super().__init__(DESIGN_NAME)",
                "",
            ]
        ),
    )
    (project / "local_settings.py").write_text(
        "DESIGN_NAME = 'Lazy import board'\n",
        encoding="utf-8",
    )

    assert main(["compile", str(project)]) == 0
    assert "Compiled Lazy import board" in capsys.readouterr().out


def test_compile_reports_each_design_validation_error(tmp_path, capsys):
    project = _create_project(
        tmp_path,
        module_name="invalid_board",
        class_name="InvalidBoard",
        module_source="\n".join(
            [
                "from earthground.components import Component",
                "from earthground.schematic import Design",
                "",
                "class InvalidBoard(Design):",
                "    def __init__(self):",
                "        super().__init__('Invalid board')",
                "        component = Component()",
                "        component.name = 'Unpackaged IC'",
                "        self.add_component(component)",
                "",
            ]
        ),
    )

    assert main(["compile", str(project)]) == 1

    output = capsys.readouterr()
    assert output.out == ""
    assert "Compilation failed for Invalid board:" in output.err
    assert " - No footprint: Unpackaged IC" in output.err


def test_compile_validates_components_in_deeply_nested_modules(tmp_path, capsys):
    project = _create_project(
        tmp_path,
        module_name="nested_board",
        class_name="NestedBoard",
        module_source="\n".join(
            [
                "from earthground.components import Component",
                "from earthground.schematic import Design",
                "",
                "class NestedBoard(Design):",
                "    def __init__(self):",
                "        super().__init__('Nested board')",
                "        child = Design('Child')",
                "        grandchild = Design('Grandchild')",
                "        component = Component()",
                "        component.name = 'Deeply nested component'",
                "        grandchild.add_component(component)",
                "        child.add_module(grandchild)",
                "        self.add_module(child)",
                "",
            ]
        ),
    )

    assert main(["compile", str(project)]) == 1

    output = capsys.readouterr()
    assert output.out == ""
    assert " - No footprint: Deeply nested component" in output.err


def test_compile_summary_counts_deeply_nested_design_objects(tmp_path):
    project = _create_project(
        tmp_path,
        module_name="nested_summary_board",
        class_name="NestedSummaryBoard",
        module_source="\n".join(
            [
                "from earthground.components import Component",
                "from earthground.schematic import Design",
                "",
                "class NestedSummaryBoard(Design):",
                "    def __init__(self):",
                "        super().__init__('Nested summary board')",
                "        child = Design('Child')",
                "        grandchild = Design('Grandchild')",
                "        component = Component()",
                "        component.virtual = True",
                "        grandchild.add_component(component)",
                "        child.add_module(grandchild)",
                "        self.add_module(child)",
                "",
            ]
        ),
    )

    result = compile_project(project)

    assert result.component_count == 3
    assert result.module_count == 2
    assert result.net_count == 3


def test_compile_project_preserves_structured_validation_error(tmp_path):
    project = _create_project(
        tmp_path,
        module_name="api_invalid_board",
        class_name="InvalidBoard",
        module_source="\n".join(
            [
                "from earthground.components import Component",
                "from earthground.schematic import Design",
                "",
                "class InvalidBoard(Design):",
                "    def __init__(self):",
                "        super().__init__('API invalid board')",
                "        self.add_component(Component())",
                "",
            ]
        ),
    )

    with pytest.raises(SchematicValidationError) as excinfo:
        compile_project(project)

    assert excinfo.value.errors == ["No footprint: "]


def test_compile_rejects_non_design_class(tmp_path, capsys):
    project = _create_project(
        tmp_path,
        module_name="not_a_design",
        class_name="BoardDesign",
        module_source="\n".join(
            [
                "class BoardDesign:",
                "    pass",
                "",
            ]
        ),
    )

    assert main(["compile", str(project)]) == 2
    assert "must refer to a subclass" in capsys.readouterr().err


def test_compile_reports_constructor_errors(tmp_path, capsys):
    project = _create_project(
        tmp_path,
        module_name="exploding_board",
        class_name="ExplodingBoard",
        module_source="\n".join(
            [
                "from earthground.schematic import Design",
                "",
                "class ExplodingBoard(Design):",
                "    def __init__(self):",
                "        raise ValueError('bad component value')",
                "",
            ]
        ),
    )

    assert main(["compile", str(project)]) == 1
    assert "Compilation failed: bad component value" in capsys.readouterr().err


def test_compile_requires_project_design_class(tmp_path):
    project = tmp_path / "missing_design"
    config = project / ".earthground" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("kicad: {}\n", encoding="utf-8")

    with pytest.raises(CompileProjectError, match="'project' mapping"):
        load_design_class(project)


def test_compile_rejects_invalid_design_reference(tmp_path):
    project = tmp_path / "invalid_reference"
    config = project / ".earthground" / "config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text(
        "project:\n  design_class: BoardDesign\n",
        encoding="utf-8",
    )

    with pytest.raises(CompileProjectError, match="python.module:DesignClass"):
        load_design_class(project)
