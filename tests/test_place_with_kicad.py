from types import SimpleNamespace

import yaml

import earthground.layout as layout_lib
from earthground.cli import main as cli_main
from earthground.schematic import Design
from earthground.library.integrated_circuits.voltage_regulators.linear import lm317
from earthground.tools.place_with_kicad import PlaceWithKicad


def test_merge_yaml_changes_updates_only_changed_entries():
    existing = {
        "R1": {"x": 1.0, "y": 2.0, "layer": "TOP", "rotation": 0.0},
        "C1": {"x": 3.0, "y": 4.0, "layer": "TOP", "rotation": 0.0},
    }
    snapshot = {
        "R1": {"x": 10.0, "y": 20.0, "layer": "BOTTOM", "rotation": 90.0},
        "C1": {"x": 30.0, "y": 40.0, "layer": "TOP", "rotation": 180.0},
    }

    merged = PlaceWithKicad.merge_yaml_changes(existing, snapshot, {"R1"})

    assert merged == {
        "R1": {"x": 10.0, "y": 20.0, "layer": "BOTTOM", "rotation": 90.0},
        "C1": {"x": 3.0, "y": 4.0, "layer": "TOP", "rotation": 0.0},
    }


def test_position_changed_uses_same_thresholds_as_polling():
    old = SimpleNamespace(x_mm=1.0, y_mm=2.0, angle_deg=0.0, layer="F.Cu")
    same = SimpleNamespace(x_mm=1.0005, y_mm=2.0005, angle_deg=0.04, layer="F.Cu")
    changed = SimpleNamespace(x_mm=1.0, y_mm=2.002, angle_deg=0.0, layer="F.Cu")

    assert PlaceWithKicad.position_changed(old, same) is False
    assert PlaceWithKicad.position_changed(old, changed) is True


def test_changed_refs_reuses_position_changed_logic():
    old = {
        "R1": SimpleNamespace(x_mm=1.0, y_mm=2.0, angle_deg=0.0, layer="F.Cu"),
        "C1": SimpleNamespace(x_mm=3.0, y_mm=4.0, angle_deg=0.0, layer="F.Cu"),
    }
    new = {
        "R1": SimpleNamespace(x_mm=1.0, y_mm=2.0, angle_deg=0.0, layer="F.Cu"),
        "C1": SimpleNamespace(x_mm=3.0, y_mm=4.1, angle_deg=0.0, layer="F.Cu"),
        "U1": SimpleNamespace(x_mm=5.0, y_mm=6.0, angle_deg=0.0, layer="F.Cu"),
    }

    assert PlaceWithKicad.changed_refs(old, new) == ["C1", "U1"]


def test_position_to_yaml_entry_converts_kicad_angle_to_layout_angle():
    pos = SimpleNamespace(x_mm=1.0, y_mm=2.0, angle_deg=-90.0, layer="F.Cu")

    entry = PlaceWithKicad.position_to_yaml_entry("R1", pos, {"R1": "resistor"})

    assert entry == {
        "description": "resistor",
        "layer": "TOP",
        "x": 1.0,
        "y": 2.0,
        "rotation": 90.0,
    }


def test_changed_yaml_keys_collapses_module_child_to_parent():
    design = lm317.LM317AMDTX.generate_design(3.3)
    design.add_module(lm317.LM317AMDTX.generate_design(3.3))

    changed_keys = PlaceWithKicad.changed_yaml_keys(
        ["REG1_U1", "R1"],
        design=design,
    )

    assert changed_keys == {"REG1", "R1"}


def test_positions_to_yaml_dict_writes_module_entry_from_child_translation():
    design = lm317.LM317AMDTX.generate_design(3.3)
    design.add_module(lm317.LM317AMDTX.generate_design(3.3))
    descriptions = PlaceWithKicad.build_description_map(design)
    module_spec = PlaceWithKicad.build_module_specs(design)["REG1"]

    positions = {}
    for refdes, layout in module_spec.child_layouts.items():
        layer = "B.Cu" if layout.layer.name == "BOTTOM" else "F.Cu"
        positions[refdes] = SimpleNamespace(
            x_mm=layout.component.x,
            y_mm=layout.component.y + 5.0,
            angle_deg=-layout.component.angle,
            layer=layer,
        )

    yaml_data = PlaceWithKicad.positions_to_yaml_dict(
        positions,
        descriptions,
        design=design,
    )

    assert "REG1" in yaml_data
    assert "REG1_U1" not in yaml_data
    assert yaml_data["REG1"]["y"] == 5.0


def test_positions_to_yaml_dict_prefers_changed_child_for_module_entry():
    design = lm317.LM317AMDTX.generate_design(3.3)
    design.add_module(lm317.LM317AMDTX.generate_design(3.3))
    descriptions = PlaceWithKicad.build_description_map(design)
    module_spec = PlaceWithKicad.build_module_specs(design)["REG1"]

    positions = {}
    for refdes, layout in module_spec.child_layouts.items():
        layer = "B.Cu" if layout.layer.name == "BOTTOM" else "F.Cu"
        y_offset = 5.0 if refdes == "REG1_C1" else 0.0
        positions[refdes] = SimpleNamespace(
            x_mm=layout.component.x,
            y_mm=layout.component.y + y_offset,
            angle_deg=-layout.component.angle,
            layer=layer,
        )

    yaml_data = PlaceWithKicad.positions_to_yaml_dict(
        positions,
        descriptions,
        design=design,
        preferred_children_by_module={"REG1": "REG1_C1"},
    )

    assert yaml_data["REG1"]["y"] == 5.0


def test_positions_to_yaml_dict_infers_module_layout_rotation_from_kicad_angle():
    design = lm317.LM317AMDTX.generate_design(3.3)
    design.add_module(lm317.LM317AMDTX.generate_design(3.3))
    descriptions = PlaceWithKicad.build_description_map(design)
    module_spec = PlaceWithKicad.build_module_specs(design)["REG1"]
    module_rotation = 90.0
    module_translation = (10.0, 20.0)

    positions = {}
    for refdes, component_layout in module_spec.child_layouts.items():
        rotated = component_layout.component.rotate(module_rotation)
        layer = "B.Cu" if component_layout.layer == layout_lib.Layer.BOTTOM else "F.Cu"
        positions[refdes] = SimpleNamespace(
            x_mm=rotated.x + module_translation[0],
            y_mm=rotated.y + module_translation[1],
            angle_deg=-(component_layout.component.angle + module_rotation),
            layer=layer,
        )

    yaml_data = PlaceWithKicad.positions_to_yaml_dict(
        positions,
        descriptions,
        design=design,
    )

    assert yaml_data["REG1"]["x"] == 10.0
    assert yaml_data["REG1"]["y"] == 20.0
    assert yaml_data["REG1"]["rotation"] == 90.0


def test_prune_module_child_entries_removes_existing_child_keys():
    design = lm317.LM317AMDTX.generate_design(3.3)
    design.add_module(lm317.LM317AMDTX.generate_design(3.3))

    pruned = PlaceWithKicad.prune_module_child_entries(
        {
            "REG1": {"y": 5.0},
            "REG1_U1": {"y": 10.0},
            "R1": {"y": 1.0},
        },
        design=design,
    )

    assert pruned == {
        "REG1": {"y": 5.0},
        "R1": {"y": 1.0},
    }


def test_normalize_yaml_document_migrates_legacy_placements():
    legacy = {"R1": {"x": 1, "y": 2, "rotation": 0}}

    assert PlaceWithKicad.normalize_yaml_document(legacy) == {
        "schema_version": 1,
        "placements": legacy,
    }


def test_copper_snapshot_serialization_is_deterministic():
    snapshot = SimpleNamespace(
        tracks=(
            layout_lib.TrackSegment(
                start=layout_lib.LayoutPoint(5, 4),
                end=layout_lib.LayoutPoint(3, 2),
                width=0.25,
                layer="F.Cu",
                net_name="GND",
            ),
        ),
        vias=(layout_lib.ViaConfig(layout_lib.Position(3, 2, 0), "GND", 0.8, 0.4),),
        zones=(
            layout_lib.Zone(
                net_name="GND",
                layers=("B.Cu",),
                outline=(
                    layout_lib.LayoutPoint(10, 10),
                    layout_lib.LayoutPoint(0, 10),
                    layout_lib.LayoutPoint(0, 0),
                    layout_lib.LayoutPoint(10, 0),
                ),
            ),
        ),
    )

    sections = PlaceWithKicad.copper_to_yaml_sections(snapshot)

    assert sections["tracks"][0]["start"] == {"x": 3, "y": 2}
    assert sections["tracks"][0]["end"] == {"x": 5, "y": 4}
    assert sections["vias"][0]["diameter"] == 0.8
    assert sections["zones"][0]["outline"][0] == {"x": 0, "y": 0}


def test_poll_loop_persists_deletion_of_last_track(tmp_path):
    position = SimpleNamespace(x_mm=1.0, y_mm=2.0, angle_deg=0.0, layer="F.Cu")
    track = layout_lib.TrackSegment(
        start=layout_lib.LayoutPoint(1, 2),
        end=layout_lib.LayoutPoint(3, 4),
        width=0.25,
        layer="F.Cu",
        net_name="GND",
    )
    snapshots = iter(
        [
            SimpleNamespace(
                positions={"R1": position}, tracks=(track,), vias=(), zones=()
            ),
            SimpleNamespace(positions={"R1": position}, tracks=(), vias=(), zones=()),
        ]
    )

    class FakeIpc:
        def get_board_snapshot(self):
            try:
                return next(snapshots)
            except StopIteration:
                raise KeyboardInterrupt

    yaml_path = tmp_path / "layout.yaml"
    yaml_path.write_text("""
schema_version: 1
placements:
  R1: {x: 1, y: 2, rotation: 0}
tracks:
  - type: segment
    net: GND
    layer: F.Cu
    width: 0.25
    start: {x: 1, y: 2}
    end: {x: 3, y: 4}
""".lstrip())
    tool = PlaceWithKicad(
        script_path=tmp_path / "design.py",
        yaml_path=yaml_path,
        poll_interval=0,
    )
    tool.design = Design("TEST")

    tool.poll_loop(FakeIpc())

    assert yaml.safe_load(yaml_path.read_text())["tracks"] == []


def test_earthground_kicad_place_dispatches_existing_workflow(tmp_path, monkeypatch):
    design_file = tmp_path / "board.py"
    output = tmp_path / "board-layout.yaml"
    observed = {}

    def fake_run(tool):
        observed.update(
            script_path=tool.script_path,
            yaml_path=tool.yaml_path,
            poll_interval=tool.poll_interval,
            no_open=tool.no_open,
        )

    monkeypatch.setattr(PlaceWithKicad, "run", fake_run)

    assert (
        cli_main(
            [
                "kicad",
                "place",
                str(design_file),
                "--output",
                str(output),
                "--poll-interval",
                "0.25",
                "--no-open",
            ]
        )
        == 0
    )
    assert observed == {
        "script_path": design_file.resolve(),
        "yaml_path": output.resolve(),
        "poll_interval": 0.25,
        "no_open": True,
    }


def test_earthground_kicad_place_reports_runtime_errors(tmp_path, monkeypatch, capsys):
    def fail(_tool):
        raise RuntimeError("KiCad is unavailable")

    monkeypatch.setattr(PlaceWithKicad, "run", fail)

    assert cli_main(["kicad", "place", str(tmp_path / "board.py")]) == 1
    assert (
        capsys.readouterr().err
        == "earthground kicad place: error: KiCad is unavailable\n"
    )
