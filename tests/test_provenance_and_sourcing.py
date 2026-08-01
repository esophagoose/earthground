from decimal import Decimal

import pytest

import earthground.components as cmp
import earthground.standard_values as sv
from earthground.schematic import Design, SchematicValidationError


def test_component_metadata_defaults_and_strict_lead_time_type():
    component = cmp.Component()

    assert component.datasheet == ""
    assert component.datasheet_revision == ""
    assert component.datasheet_sha256 == ""
    assert component.lifecycle is cmp.Lifecycle.UNKNOWN
    assert component.alternates == []
    assert component.distributor_ids == {}
    assert component.lead_time is None
    assert not hasattr(component, "ltspice_model")

    component.lead_time = sv.weeks(typ=6)
    assert component.lead_time.units == "week"
    assert component.lead_time.typ == Decimal("6")

    with pytest.raises(TypeError, match="ValueBounds in weeks"):
        component.lead_time = "6 week(s)"
    with pytest.raises(TypeError, match="ValueBounds in weeks"):
        component.lead_time = 6.0
    with pytest.raises(TypeError, match="Lifecycle"):
        component.lifecycle = "Active"


def test_datasheet_coverage_is_recursive_and_ignores_dnp():
    design = Design("Parent")
    provenanced = design.add_component(cmp.Component())
    provenanced.datasheet = "https://example.test/a.pdf"
    provenanced.datasheet_revision = "Rev B"

    child = Design("Child", "CH")
    url_only = child.add_component(cmp.Component())
    url_only.datasheet = "https://example.test/b.pdf"
    child.add_component(cmp.Component())
    ignored = child.add_component(cmp.Component())
    ignored.dnp = True
    design.add_module(child)

    assert design.datasheet_coverage() == {
        "provenanced": ("U1",),
        "url_only": ("CH1_U1",),
        "undocumented": ("CH1_U2",),
    }


def test_sourcing_report_and_opt_in_validation_are_strict():
    design = Design("Sourcing")
    active = design.add_component(cmp.Component())
    active.mpn = "ACTIVE123"
    active.lifecycle = cmp.Lifecycle.ACTIVE
    unknown = design.add_component(cmp.Component())
    unknown.mpn = "UNKNOWN123"

    report = design.sourcing_report()
    assert [check.refdes for check in report.passes] == ["U1"]
    assert [check.refdes for check in report.failures] == ["U2"]
    assert design.validate(skip_footprint_check=True)

    with pytest.raises(
        SchematicValidationError, match="UNKNOWN123 lifecycle is Unknown"
    ):
        design.validate(skip_footprint_check=True, check_sourcing=True)

    unknown.dnp = True
    assert design.validate(skip_footprint_check=True, check_sourcing=True)


def test_passive_ratings_are_typed_and_unknown_keywords_fail():
    tolerance = sv.ratio(min=-0.01, typ=0, max=0.01)
    resistor = cmp.Resistor(
        "10k",
        tolerance=tolerance,
        power_rating=sv.watts(typ=0.125, max=0.125),
        package_size="0603",
    )
    capacitor = cmp.Capacitor("100n", 10, tolerance=tolerance, dielectric="X7R")
    inductor = cmp.Inductor(
        "4.7u",
        current=sv.amps(max=2),
        dcr=sv.ohms(max=0.1),
        tolerance=tolerance,
    )

    assert resistor.power_rating.units == "W"
    assert capacitor.dielectric == "X7R"
    assert inductor.current.units == "A"
    assert inductor.dcr.units == "Ω"
    with pytest.raises(TypeError, match="curent"):
        cmp.Inductor("4.7u", curent=sv.amps(max=2))
    with pytest.raises(ValueError, match="power_rating must use W"):
        cmp.Resistor("1k", power_rating=sv.volts(max=5))


def test_length_and_week_helpers_use_canonical_units():
    assert sv.weeks(typ=6).units == "week"
    assert sv.millimeters(max=300).units == "m"
    assert sv.millimeters(max=300).max == Decimal("0.300")
    assert sv.mils(max=5).max == Decimal("0.0001270")
