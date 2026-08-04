from decimal import Decimal

import earthground.components as cmp
import earthground.layout as layout
import earthground.standard_values as sv
from earthground.analysis import DesignAnalysis
from earthground.contracts import (
    Decoupling,
    LeaveOpenIfUnused,
    RoutingConstraint,
    SameNet,
    TieIfUnused,
)
from earthground.ratings import Ratings
from earthground.schematic import Design, SchematicValidationError
from earthground.straps import StrapLevel, StrapPin
from earthground.thermal import (
    ConstantPower,
    RailCurrent,
    SupplyCurrentPower,
    ThermalModel,
    estimate_power,
)


def exact_ohms(value):
    return sv.ohms(value, typ=value, max=value)


LEVELS = (
    StrapLevel(name="VIL", ratio=sv.ratio(0, max=0.2), meaning="low"),
    StrapLevel(name="VIM", ratio=sv.ratio(0.4, max=0.6), meaning="middle"),
    StrapLevel(name="VIH", ratio=sv.ratio(0.8, max=1), meaning="high"),
)


class StrapDevice(cmp.Component):
    strap_pins = (
        StrapPin(
            id="cfg",
            pin="CFG",
            reference="VCC",
            levels=LEVELS,
            internal_pull_up=exact_ohms(100_000),
            internal_pull_down=exact_ohms(100_000),
            sampled_on="reset",
            source="datasheet strap table",
        ),
    )

    def __init__(self):
        super().__init__()
        self.name = "STRAP_DEVICE"
        self.pins = cmp.PinContainer.from_dict({1: "VCC", 2: "CFG"}, self)


class ContractDevice(cmp.Component):
    def __init__(self, requirements):
        super().__init__()
        self.name = "CONTRACT_DEVICE"
        self.pins = cmp.PinContainer.from_dict(
            {1: "VCC", 2: "VREG", 3: "VDD", 4: "UNUSED"}, self
        )
        self.requires = tuple(requirements)


def test_analysis_flattens_hierarchy_without_mutating_and_requires_explicit_placement():
    child = Design("Child", "CH", ["VCC"])
    device = child.add_component(StrapDevice())
    child.connect([device.pins.by_name("VCC"), child.port["VCC"]], "VCC")
    child.layout.placement["U1"] = layout.Placement(
        layout.Position(2, 3, 0), layer=layout.Layer.TOP
    )

    parent = Design("Parent")
    module = parent.add_module(child)
    parent.join_net(module.port["VCC"], "P1V8")
    parent.declare_rail("P1V8", sv.volts(1.7, typ=1.8, max=1.9))

    before_components = dict(child.components)
    analysis = DesignAnalysis(parent)
    resolved = analysis.component_for(device)

    assert resolved.refdes == "CH1_U1"
    assert resolved.placement is None
    assert analysis.net_for_pin(device.pins.by_name("VCC")).name == "P1V8"
    assert dict(child.components) == before_components

    parent.layout.placement["CH1"] = layout.Placement(layout.Position(10, 20, 90))
    placed = DesignAnalysis(parent).component_for(device)
    assert placed.placement is not None
    assert placed.placement.component.x == 7
    assert placed.placement.component.y == 22


def test_analysis_preserves_each_repeated_module_segment_in_refdes():
    leaf = Design("Leaf", "DI2C")
    capacitor = leaf.add_component(cmp.Capacitor("100n", 10))

    wrapper = Design("Wrapper", "DI2C")
    wrapper.add_module(leaf)

    board = Design("Board")
    board.add_module(wrapper)

    resolved = DesignAnalysis(board).component_for(capacitor)
    assert resolved is not None
    assert resolved.refdes == "DI2C1_DI2C1_C1"


def test_strap_resolves_floating_and_external_pullup_with_expectations():
    design = Design("Straps")
    device = design.add_component(StrapDevice())
    design.join_net(device.pins.by_name("VCC"), "P1V8")
    design.join_net(device.pins.by_name("CFG"), "CFG")
    design.declare_rail("P1V8", sv.volts(1.8, typ=1.8, max=1.8))
    design.expect_strap(device, "cfg", "VIM", "floating default")

    result = design.check_straps().results[0]
    assert result.status is sv.CheckStatus.PASS
    assert result.level == "VIM"
    assert result.ratio.typ == Decimal("0.5")

    resistor = design.add_component(cmp.Resistor("4.7k"))
    design.connect([device.pins.by_name("CFG"), resistor.pins[1]], "CFG")
    design.connect([device.pins.by_name("VCC"), resistor.pins[2]], "P1V8")

    mismatch = design.check_straps().results[0]
    assert mismatch.status is sv.CheckStatus.FAIL
    assert mismatch.level == "VIH"
    assert mismatch.externally_overridden

    design.expect_strap(device, "cfg", "VIH", "I2C pull-up")
    selected = design.check_straps().results[0]
    assert selected.status is sv.CheckStatus.PASS
    assert "external bias overrides" in selected.message
    assert selected.determining_components == ("R1",)


def test_strap_reports_unknown_for_unsupported_branch():
    design = Design("Complex strap")
    device = design.add_component(StrapDevice())
    driver = design.add_component(cmp.Component())
    driver.pins = cmp.PinContainer.from_dict(
        {1: cmp.DigitalPinSpec.output(name="OUT")}, driver
    )
    design.join_net(device.pins.by_name("VCC"), "P1V8")
    design.connect([device.pins.by_name("CFG"), driver.pins[1]], "CFG")
    design.declare_rail("P1V8", sv.volts(1.8, typ=1.8, max=1.8))

    assert design.check_straps().results[0].status is sv.CheckStatus.UNKNOWN


def test_thermal_report_models_passives_and_rja_junction_temperature(tmp_path):
    design = Design("Thermal")
    resistor = design.add_component(cmp.Resistor("1k"))
    capacitor = design.add_component(cmp.Capacitor("100n", 10))
    ic = design.add_component(cmp.Component())
    ic.name = "IC"
    ic.mpn = "IC123"
    ic.power = ConstantPower(power=sv.watts(0.5, typ=0.5, max=0.5))
    ic.thermal = ThermalModel(
        r_ja=sv.celsius_per_watt(40, typ=40, max=40, source="thermal table")
    )
    ic.abs_max = Ratings(tj=sv.celsius(min=sv.UNBOUNDED, max=105))

    design.connect([resistor.pins[1], capacitor.pins[1]], "P3V3")
    design.connect([resistor.pins[2], capacitor.pins[2]], "GND")
    design.declare_rail("P3V3", sv.volts(3.3, typ=3.3, max=3.3))
    design.declare_ambient(sv.celsius(25, typ=25, max=25))
    design.layout.placement["U1"] = layout.Placement(layout.Position(1, 2, 0))

    rows = {row.reference_designator: row for row in design.thermal_report().rows}
    assert rows["R1"].power_dissipation.typ == Decimal("0.01089")
    assert rows["C1"].power_dissipation.max == 0
    assert rows["U1"].junction_temperature.typ == 45
    assert rows["U1"].status is sv.CheckStatus.PASS

    output = design.thermal_report().write_csv(tmp_path / "thermal.csv")
    assert output.read_text().splitlines()[0].startswith("reference designator")
    assert "IC123" in output.read_text()


def test_supply_current_power_uses_resolved_rail_voltage():
    design = Design("Supply current")
    device = design.add_component(cmp.Component())
    device.pins = cmp.PinContainer.from_dict({1: "VCC"}, device)
    device.power = SupplyCurrentPower(
        rails=(
            RailCurrent(
                pin="VCC",
                current=sv.amps(0.01, typ=0.01, max=0.01),
            ),
        )
    )
    design.join_net(device.pins[1], "P5V0")
    design.declare_rail("P5V0", sv.volts(5, typ=5, max=5))

    estimate = estimate_power(device, DesignAnalysis(design))
    assert estimate.status is sv.CheckStatus.PASS
    assert estimate.power.typ == Decimal("0.05")


def test_contracts_are_hierarchy_aware_and_waivers_are_aspect_local():
    requirements = (
        Decoupling(
            id="vcc-decoupling",
            pin="VCC",
            capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
            max_distance_mm=3,
        ),
        SameNet(id="reg-link", pins=("VREG", "VDD")),
        RoutingConstraint(
            id="reg-width",
            pins=("VREG", "VDD"),
            min_trace_width_mm=0.254,
        ),
        TieIfUnused(id="unused-tie", pins=("UNUSED",), to="GND"),
    )
    child = Design("Child", "CH", ["VCC", "GND"])
    device = child.add_component(ContractDevice(requirements))
    child.connect([device.pins.by_name("VCC"), child.port["VCC"]], "VCC")
    child.connect([device.pins.by_name("UNUSED"), child.port["GND"]], "GND")
    child.connect([device.pins.by_name("VREG"), device.pins.by_name("VDD")], "P1V2")

    parent = Design("Parent")
    module = parent.add_module(child)
    parent.join_net(module.port["VCC"], "P1V8")
    parent.join_net(module.port["GND"], "GND")
    capacitor = parent.add_component(cmp.Capacitor("100n", 10))
    parent.join_net(capacitor.pins[1], "P1V8")
    parent.join_net(capacitor.pins[2], "GND")

    report = parent.check_contracts()
    by_id = {check.check_id: check for check in report.checks}
    assert by_id["vcc-decoupling.topology"].status is sv.CheckStatus.PASS
    assert by_id["vcc-decoupling.capacitance"].status is sv.CheckStatus.PASS
    assert by_id["vcc-decoupling.distance"].status is sv.CheckStatus.UNKNOWN
    assert by_id["reg-link.topology"].status is sv.CheckStatus.PASS
    assert by_id["unused-tie.UNUSED"].status is sv.CheckStatus.PASS
    assert by_id["reg-width.routing"].status is sv.CheckStatus.UNKNOWN
    assert not report.is_valid

    child.waive_contract(
        device,
        "vcc-decoupling.distance",
        "placement will be verified after PCB placement",
    )
    child.waive_contract(
        device,
        "reg-width.routing",
        "verified manually in KiCad",
    )
    assert parent.check_contracts().is_valid


def test_decoupling_distance_prefers_explicit_local_candidates():
    requirement = Decoupling(
        id="local-decoupling",
        pin="VCC",
        capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
        max_distance_mm=3,
    )
    child = Design("Child", "CH", ["VCC", "GND"])
    device = child.add_component(ContractDevice((requirement,)))
    capacitor = child.add_component(cmp.Capacitor("100n", 10))
    child.connect(
        [device.pins.by_name("VCC"), capacitor.pins[1], child.port["VCC"]], "VCC"
    )
    child.connect([capacitor.pins[2], child.port["GND"]], "GND")
    child.layout.placement["U1"] = layout.Placement(layout.Position(0, 0, 0))
    child.layout.placement["C1"] = layout.Placement(layout.Position(2, 0, 0))

    parent = Design("Parent")
    module = parent.add_module(child)
    parent.join_net(module.port["VCC"], "P3V3")
    parent.join_net(module.port["GND"], "GND")
    parent.layout.placement["CH1"] = layout.Placement(layout.Position(10, 20, 90))

    unrelated = parent.add_component(cmp.Capacitor("1u", 10))
    parent.join_net(unrelated.pins[1], "P3V3")
    parent.join_net(unrelated.pins[2], "GND")

    checks = {check.check_id: check for check in parent.check_contracts().checks}
    assert checks["local-decoupling.distance"].status is sv.CheckStatus.PASS
    assert (
        "0 candidate placement(s) are unavailable"
        in checks["local-decoupling.distance"].message
    )

    child.layout.placement["C1"] = layout.Placement(layout.Position(4, 0, 0))
    checks = {check.check_id: check for check in parent.check_contracts().checks}
    assert checks["local-decoupling.distance"].status is sv.CheckStatus.FAIL


def test_leave_open_and_strict_validation():
    device = ContractDevice((LeaveOpenIfUnused(id="leave-open", pins=("UNUSED",)),))
    design = Design("Leave open")
    design.add_component(device)
    design.join_net(device.pins.by_name("UNUSED"), "DANGLING")
    assert design.check_contracts().is_valid

    other = design.add_component(cmp.Resistor("1k"))
    design.join_net(other.pins[1], "DANGLING")
    assert design.check_contracts().is_valid  # The pin is now used.

    bad = Design("Bad")
    broken = bad.add_component(
        ContractDevice((SameNet(id="same", pins=("VREG", "VDD")),))
    )
    bad.join_net(broken.pins.by_name("VREG"), "A")
    bad.join_net(broken.pins.by_name("VDD"), "B")
    try:
        bad.validate(skip_footprint_check=True, check_contracts=True)
    except SchematicValidationError as exc:
        assert "same.topology Fail" in str(exc)
    else:
        raise AssertionError("strict contract validation should fail")
