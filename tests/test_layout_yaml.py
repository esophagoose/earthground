import pytest

import earthground.components as cmp
import earthground.layout as layout_lib
from earthground.library.integrated_circuits.voltage_regulators.linear import lm317
from earthground.schematic import Design
from earthground.models.layout_models import LayoutPlacementMap


def test_load_placements_from_yaml_populates_layout_dict(tmp_path):
    design = Design("TEST")
    design.add_component(cmp.Resistor(100))
    design.add_component(cmp.Capacitor("1u", "10V"))

    yaml_path = tmp_path / "placements.yaml"
    yaml_path.write_text("""
R1:
  description: ''
  layer: TOP
  x: 1.25
  y: -2.5
  rotation: 180.0
C1:
  description: ''
  layer: BOTTOM
  x: 3.0
  y: 4.5
  rotation: 90.0
""".lstrip())

    design.layout.load_placements_from_yaml(yaml_path)

    assert design.layout.placement == {
        "R1": layout_lib.Placement(
            position=layout_lib.Position(x=1.25, y=-2.5, angle=180.0),
            id=None,
            layer=layout_lib.Layer.TOP,
        ),
        "C1": layout_lib.Placement(
            position=layout_lib.Position(x=3.0, y=4.5, angle=90.0),
            id=None,
            layer=layout_lib.Layer.BOTTOM,
        ),
    }


def test_load_placements_from_yaml_rejects_invalid_layer(tmp_path):
    design = Design("TEST")
    design.add_component(cmp.Resistor(100))

    yaml_path = tmp_path / "placements.yaml"
    yaml_path.write_text("""
R1:
  description: ''
  layer: INNER
  x: 1.25
  y: -2.5
  rotation: 180.0
""".lstrip())

    try:
        design.layout.load_placements_from_yaml(yaml_path)
        assert False, "Expected ValueError for invalid layer"
    except ValueError as exc:
        assert "Invalid layer" in str(exc)

    assert design.layout.placement == {}


def test_layout_placement_map_validates_yaml_shape():
    placement_map = LayoutPlacementMap.model_validate(
        {
            "R1": {"layer": "top", "x": "1.25", "y": "-2.5", "rotation": "180.0"},
            "C1": {"x": 3, "y": 4.5, "rotation": 90},
        }
    )

    assert placement_map.root["R1"].layer == "TOP"
    assert placement_map.root["R1"].x == 1.25
    assert placement_map.root["R1"].y == -2.5
    assert placement_map.root["R1"].rotation == 180.0
    assert placement_map.root["C1"].layer == "TOP"


def test_load_placements_from_yaml_accepts_module_refdes(tmp_path):
    design = lm317.LM317AMDTX.generate_design(3.3)
    design.add_module(lm317.LM317AMDTX.generate_design(3.3))

    yaml_path = tmp_path / "placements.yaml"
    yaml_path.write_text("""
REG1:
  description: ''
  layer: TOP
  x: 25.0
  y: 40.0
  rotation: 90.0
""".lstrip())

    design.layout.load_placements_from_yaml(yaml_path)

    assert design.layout.placement["REG1"] == layout_lib.Placement(
        position=layout_lib.Position(x=25.0, y=40.0, angle=90.0),
        id=None,
        layer=layout_lib.Layer.TOP,
    )


def test_load_structured_layout_yaml_populates_copper_geometry(tmp_path):
    design = Design("TEST")
    design.add_component(cmp.Resistor(100))
    yaml_path = tmp_path / "layout.yaml"
    yaml_path.write_text("""
schema_version: 1
placements:
  R1: {layer: TOP, x: 1, y: 2, rotation: 0}
tracks:
  - type: segment
    net: GND
    layer: f.cu
    width: 0.25
    start: {x: 1, y: 2}
    end: {x: 3, y: 4}
  - type: arc
    net: SIG
    layer: B.Cu
    width: 0.15
    start: {x: 3, y: 4}
    mid: {x: 4, y: 5}
    end: {x: 5, y: 4}
vias:
  - net: GND
    position: {x: 3, y: 4}
    diameter: 0.8
    drill: 0.4
zones:
  - net: GND
    layers: [B.Cu]
    outline:
      - {x: 0, y: 0}
      - {x: 10, y: 0}
      - {x: 10, y: 10}
      - {x: 0, y: 10}
    name: Ground plane
    priority: 2
""".lstrip())

    design.layout.load_layout_from_yaml(yaml_path)

    assert design.layout.placement["R1"].position == layout_lib.Position(1, 2, 0)
    assert design.layout.tracks == [
        layout_lib.TrackSegment(
            start=layout_lib.LayoutPoint(1, 2),
            end=layout_lib.LayoutPoint(3, 4),
            width=0.25,
            layer="F.Cu",
            net_name="GND",
        ),
        layout_lib.TrackArc(
            start=layout_lib.LayoutPoint(3, 4),
            mid=layout_lib.LayoutPoint(4, 5),
            end=layout_lib.LayoutPoint(5, 4),
            width=0.15,
            layer="B.Cu",
            net_name="SIG",
        ),
    ]
    assert design.layout.vias == [
        layout_lib.ViaConfig(layout_lib.Position(3, 4, 0), "GND", 0.8, 0.4)
    ]
    assert design.layout.zones[0].name == "Ground plane"
    assert design.layout.zones[0].priority == 2


def test_invalid_structured_layout_does_not_partially_mutate_layout(tmp_path):
    design = Design("TEST")
    design.add_component(cmp.Resistor(100))
    original = layout_lib.Placement(layout_lib.Position(9, 9, 0))
    design.layout.placement["R1"] = original
    yaml_path = tmp_path / "layout.yaml"
    yaml_path.write_text("""
schema_version: 1
placements:
  R1: {x: 1, y: 2, rotation: 0}
tracks:
  - type: segment
    net: GND
    layer: F.Cu
    width: -0.25
    start: {x: 1, y: 2}
    end: {x: 3, y: 4}
""".lstrip())

    with pytest.raises(ValueError, match="greater than 0"):
        design.layout.load_layout_from_yaml(yaml_path)

    assert design.layout.placement == {"R1": original}
    assert design.layout.tracks == []


def test_get_placement_keeps_left_reference_on_left_when_rotated_180():
    design = Design("TEST")
    design.add_component(cmp.Resistor(100))
    refdes = next(iter(design.components))
    design.layout.placement[refdes] = layout_lib.Placement(
        position=layout_lib.Position(x=10.0, y=20.0, angle=180.0),
        id=layout_lib.Orientation.LEFT,
        layer=layout_lib.Layer.TOP,
    )

    placement = design.layout.get_placement(refdes)

    assert placement.id_orientation == layout_lib.Orientation.LEFT
    assert placement.id.x > 0
    assert placement.id.y == 0
    assert placement.id.angle == 180.0
