from earthground.components import Capacitor, Resistor
from earthground.exporters.kicad_sch import write_design_to_kicad_schematic
from earthground.exporters.schematic_generation.kicad_schematic import (
    build_schematic_bundle,
)
from earthground.exporters.schematic_generation.writer import (
    write_kicad_schematic_bundle,
)
from earthground.schematic import Design


def build_hierarchical_design() -> Design:
    parent = Design("Parent")
    module = Design("ChildModule", "CH", ports=["VIN", "VOUT", "GND"])

    resistor = module.add_component(Resistor(1000))
    capacitor = module.add_component(Capacitor(1e-6, 10))
    module.connect([module.port["VIN"], resistor.pins[1]], "VIN")
    module.connect([resistor.pins[2], capacitor.pins[1], module.port["VOUT"]], "VOUT")
    module.connect([capacitor.pins[2], module.port["GND"]], "GND")

    parent.add_module(module)
    parent.join_net(module.port["VIN"], "VIN")
    parent.join_net(module.port["VOUT"], "VOUT")
    parent.join_net(module.port["GND"], "GND")
    return parent


def test_writer_emits_root_and_child_files(tmp_path):
    bundle = build_schematic_bundle(build_hierarchical_design())

    paths = write_kicad_schematic_bundle(bundle, tmp_path)

    assert (tmp_path / "root.kicad_sch").exists()
    assert len(paths) == 2
    assert any(path.name != "root.kicad_sch" for path in paths)


def test_public_wrapper_writes_design(tmp_path):
    paths = write_design_to_kicad_schematic(build_hierarchical_design(), tmp_path)

    assert (tmp_path / "root.kicad_sch").exists()
    assert len(paths) == 2
