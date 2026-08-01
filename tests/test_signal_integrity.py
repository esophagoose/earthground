import json

import pytest

import earthground.signal_integrity as si
import earthground.standard_values as sv
from earthground.exporters.kicad_project import (
    BEGIN_MARKER,
    END_MARKER,
    save_constraints,
)
from earthground.library.integrated_circuits.transceivers.sn65dphy440ss import (
    generate_design,
)
from earthground.schematic import Design, SchematicValidationError


def _constrained_design():
    design = Design("SI Board")
    for name in ("CLK_P", "CLK_N", "STATUS"):
        design.add_net(name)
    design.declare_net_class(
        si.NetClass(
            "DPHY",
            ("CLK_P", "CLK_N"),
            clearance=sv.millimeters(min=0.12, typ=0.15),
            track_width=sv.millimeters(min=0.09, typ=0.1, max=0.11),
            diff_pair_width=sv.millimeters(min=0.09, typ=0.1, max=0.11),
            diff_pair_gap=sv.millimeters(min=0.1, typ=0.12, max=0.14),
            z_single=sv.ohms(nominal=50, tolerance_pct=15),
        )
    )
    design.declare_diff_pair(
        si.DiffPair(
            ("CLK_P", "CLK_N"),
            "DPHY",
            z_diff=sv.ohms(nominal=100, tolerance_pct=15),
            intra_pair_skew=sv.mils(max=5),
            max_vias=2,
            max_length=sv.millimeters(max=300),
            min_track_angle_deg=135,
        )
    )
    return design


def test_declarations_validate_types_duplicates_and_membership():
    design = _constrained_design()
    assert design.validate(skip_footprint_check=True) == []

    with pytest.raises(ValueError, match="already declared"):
        design.declare_net_class(si.NetClass("DPHY", ("CLK_P",)))
    with pytest.raises(ValueError, match="already declared"):
        design.declare_diff_pair(si.DiffPair(("CLK_N", "CLK_P"), "DPHY"))
    with pytest.raises(ValueError, match="typical value"):
        si.NetClass("BAD", ("CLK_P",), track_width=sv.millimeters(min=0.1))

    invalid = Design("Invalid")
    invalid.add_net("A_P")
    invalid.declare_net_class(si.NetClass("FAST", ("A_P", "A_N")))
    with pytest.raises(SchematicValidationError, match="unknown nets: A_N"):
        invalid.validate(skip_footprint_check=True)


def test_kicad_project_merge_preserves_unrelated_settings(tmp_path):
    design = _constrained_design()
    project = tmp_path / "SI Board.kicad_pro"
    project.write_text(
        json.dumps(
            {
                "custom": {"preserve": True},
                "net_settings": {
                    "classes": [
                        {"name": "Default", "track_width": 0.25},
                        {"name": "MANUAL", "track_width": 0.5},
                    ],
                    "netclass_patterns": [
                        {"netclass": "MANUAL", "pattern": "STATUS"},
                        {"netclass": "DPHY", "pattern": "STALE"},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    rules = tmp_path / "SI Board.kicad_dru"
    rules.write_text(
        '(version 1)\n\n(rule "Manual" (constraint clearance (min 0.2mm)))\n',
        encoding="utf-8",
    )

    save_constraints(design, tmp_path)
    document = json.loads(project.read_text(encoding="utf-8"))
    classes = {item["name"]: item for item in document["net_settings"]["classes"]}
    patterns = document["net_settings"]["netclass_patterns"]

    assert document["custom"] == {"preserve": True}
    assert classes["MANUAL"]["track_width"] == 0.5
    assert classes["DPHY"]["track_width"] == 0.1
    assert {tuple(item.values()) for item in patterns} == {
        ("MANUAL", "STATUS"),
        ("DPHY", "CLK_P"),
        ("DPHY", "CLK_N"),
    }

    generated = rules.read_text(encoding="utf-8")
    assert '(rule "Manual"' in generated
    assert generated.count(BEGIN_MARKER) == 1
    assert generated.count(END_MARKER) == 1
    assert "(constraint skew (max 0.1270000mm))" in generated
    assert "(constraint via_count (max 2))" in generated
    assert "(constraint track_angle (min 135deg))" in generated

    save_constraints(design, tmp_path)
    assert rules.read_text(encoding="utf-8").count(BEGIN_MARKER) == 1


def test_dphy_reference_declares_all_ten_pairs_without_geometry_guessing():
    design = generate_design()

    assert tuple(design._net_classes) == ("DPHY",)
    assert len(design._diff_pairs) == 10
    assert design._net_classes["DPHY"].track_width is None
    assert design._diff_pairs[0].intra_pair_skew.max == sv.mils(max=5).max
    assert design._diff_pairs[0].max_length.max == sv.millimeters(max=300).max
