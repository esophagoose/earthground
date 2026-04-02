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
    yaml_path.write_text(
        """
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
""".lstrip()
    )

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
    yaml_path.write_text(
        """
R1:
  description: ''
  layer: INNER
  x: 1.25
  y: -2.5
  rotation: 180.0
""".lstrip()
    )

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
    yaml_path.write_text(
        """
REG1:
  description: ''
  layer: TOP
  x: 25.0
  y: 40.0
  rotation: 90.0
""".lstrip()
    )

    design.layout.load_placements_from_yaml(yaml_path)

    assert design.layout.placement["REG1"] == layout_lib.Placement(
        position=layout_lib.Position(x=25.0, y=40.0, angle=90.0),
        id=None,
        layer=layout_lib.Layer.TOP,
    )


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
