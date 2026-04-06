from types import SimpleNamespace

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
            angle_deg=layout.component.angle,
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
            angle_deg=layout.component.angle,
            layer=layer,
        )

    yaml_data = PlaceWithKicad.positions_to_yaml_dict(
        positions,
        descriptions,
        design=design,
        preferred_children_by_module={"REG1": "REG1_C1"},
    )

    assert yaml_data["REG1"]["y"] == 5.0


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
