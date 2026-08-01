import pytest
import pygerber.aperture as ap_lib
import pykicad.models.pcb as pcb

import earthground.components as cmp
import earthground.exporters.kicad as kicad
import earthground.footprint_types as ft
from earthground.importers.kicad import KicadFootprint
from earthground.schematic import Design

PAD_SHAPES = """
(footprint "PadShapes"
  (version 20240108)
  (generator "test")
  (layer "F.Cu")
  (pad "1" smd rect (at -2 -3 30) (size 2 1)
    (layers "F.Cu" "F.Mask" "F.Paste"))
  (pad "2" smd circle (at 0 0) (size 1 1)
    (layers "F.Cu" "F.Mask" "F.Paste"))
  (pad "3" smd roundrect (at 2 0 90) (size 2 1)
    (layers "F.Cu" "F.Mask" "F.Paste") (roundrect_rratio 0.25))
  (pad "A1" smd oval (at 4 0 45) (size 2 1)
    (layers "F.Cu" "F.Mask" "F.Paste"))
  (pad "4" smd trapezoid (at 6 0 15) (size 2 1) (rect_delta 0.2 0.1)
    (layers "F.Cu" "F.Mask" "F.Paste"))
  (pad "5" thru_hole circle (at 8 0) (size 2 2) (drill 1)
    (layers "*.Cu" "*.Mask"))
  (pad "" smd rect (at 10 0) (size 3 3) (layers "F.Paste"))
  (pad "M1" np_thru_hole circle (at 12 0) (size 3 3) (drill 3)
    (layers "*.Cu" "*.Mask"))
)
""".strip()


SOIC_8 = """
(footprint "SOIC-8_3.9x4.9mm_P1.27mm"
  (version 20240108)
  (generator "test")
  (layer "F.Cu")
  (pad "1" smd roundrect (at -2.475 -1.905) (size 1.95 0.6)
    (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "2" smd roundrect (at -2.475 -0.635) (size 1.95 0.6)
    (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "3" smd roundrect (at -2.475 0.635) (size 1.95 0.6)
    (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "4" smd roundrect (at -2.475 1.905) (size 1.95 0.6)
    (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "5" smd roundrect (at 2.475 1.905) (size 1.95 0.6)
    (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "6" smd roundrect (at 2.475 0.635) (size 1.95 0.6)
    (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "7" smd roundrect (at 2.475 -0.635) (size 1.95 0.6)
    (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
  (pad "8" smd roundrect (at 2.475 -1.905) (size 1.95 0.6)
    (layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.25))
)
""".strip()


def test_kicad_footprint_populates_pads_and_maps_shapes():
    footprint = KicadFootprint("Test", "PadShapes", PAD_SHAPES)

    assert list(footprint.pads) == ["1", "2", "3", "A1", "4", "5"]

    rect = footprint.pads["1"]
    assert rect.location == [-2, -3]
    assert isinstance(rect.aperture, ap_lib.ApertureRectangle)
    assert rect.aperture.width == 2
    assert rect.aperture.height == 1
    assert rect.aperture.rotation == 30

    circle = footprint.pads["2"].aperture
    assert isinstance(circle, ap_lib.ApertureCircle)
    assert circle.diameter == 1

    roundrect = footprint.pads["3"].aperture
    assert isinstance(roundrect, ap_lib.ApertureRectangle)
    assert roundrect.radius == 0.25
    assert roundrect.rotation == 90

    oval = footprint.pads["A1"].aperture
    assert isinstance(oval, ap_lib.ApertureRectangle)
    assert oval.radius == 0.5
    assert oval.rotation == 45

    approximated_trapezoid = footprint.pads["4"].aperture
    assert isinstance(approximated_trapezoid, ap_lib.ApertureRectangle)
    assert approximated_trapezoid.width == 2
    assert approximated_trapezoid.height == 1
    assert approximated_trapezoid.rotation == 15

    through_hole = footprint.pads["5"].aperture
    assert isinstance(through_hole, ap_lib.ApertureCircle)
    assert through_hole.diameter == 2


def test_duplicate_pad_number_uses_last_source_occurrence():
    footprint = KicadFootprint(
        "Test",
        "DuplicatePadNumber",
        """
        (footprint "DuplicatePadNumber"
          (version 20240108)
          (generator "test")
          (layer "F.Cu")
          (pad "1" smd rect (at -1 0) (size 1 1)
            (layers "F.Cu" "F.Mask"))
          (pad "1" smd rect (at 1 0) (size 1 1)
            (layers "F.Cu" "F.Mask")))
        """.strip(),
    )

    assert list(footprint.pads) == ["1"]
    assert footprint.pads["1"].location == [1, 0]


def test_soic_8_exposes_expected_pad_map_and_bbox():
    footprint = KicadFootprint(
        "Package_SO",
        "SOIC-8_3.9x4.9mm_P1.27mm",
        SOIC_8,
    )

    assert list(footprint.pads) == [str(index) for index in range(1, 9)]
    assert footprint.pads["1"].location == [-2.475, -1.905]
    assert footprint.pads["8"].location == [2.475, -1.905]
    assert footprint.pads["1"].aperture.width == 1.95
    assert footprint.pads["1"].aperture.height == 0.6
    assert footprint.get_bbox() == ft.BoundingBox(
        x1=-3.45,
        y1=-2.205,
        x2=3.45,
        y2=2.205,
    )


def test_padless_footprint_keeps_conservative_bbox():
    footprint = KicadFootprint(
        "Test",
        "Padless",
        """
        (footprint "Padless"
          (version 20240108)
          (generator "test")
          (layer "F.Cu"))
        """.strip(),
    )

    assert footprint.pads == {}
    assert footprint.get_bbox() == ft.BoundingBox(-0.5, -0.5, 0.5, 0.5)


def test_malformed_sexpression_fails_during_construction():
    with pytest.raises(ValueError, match="Unclosed"):
        KicadFootprint("Test", "Malformed", '(footprint "Malformed"')


def test_imported_export_uses_original_sexpression_geometry():
    source_sexp = """
    (footprint "ImportedTrapezoid"
      (version 20240108)
      (generator "test")
      (layer "F.Cu")
      (pad "1" smd trapezoid (at 6 2 15) (size 2 1) (rect_delta 0.2 0.1)
        (layers "F.Cu" "F.Mask" "F.Paste")))
    """.strip()
    component = cmp.Component("U")
    component.name = "ImportedTrapezoid"
    component.pins = cmp.PinContainer.from_dict({1: "P1"}, component)
    component.footprint = KicadFootprint(
        "Test",
        "ImportedTrapezoid",
        source_sexp,
    )

    # Make the informational geometry intentionally disagree with the source.
    component.footprint.pads["1"] = ft.Pad(
        location=[99, 99],
        aperture=ap_lib.ApertureCircle(diameter=20),
    )

    design = Design("TEST")
    design.add_component(component)
    exported = kicad.KicadExporter(design).parse_footprint(design, component)

    assert component.footprint.sexp == source_sexp
    assert exported.pads[0].shape == "trapezoid"
    assert exported.pads[0].at == pcb.Position(x=6, y=2, angle=15)
    assert exported.pads[0].size.width == 2
    assert exported.pads[0].size.height == 1
