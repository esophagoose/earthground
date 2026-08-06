from types import SimpleNamespace

from kipy.proto.board.board_types_pb2 import BoardLayer
from kipy.geometry import Vector2

import earthground.layout as layout_lib
from earthground.ipc.kicad_ipc import KicadIpc


def _net(name):
    return SimpleNamespace(name=name)


def test_ipc_converts_straight_and_arc_tracks_to_layout_geometry():
    segment = SimpleNamespace(
        start=Vector2.from_xy_mm(1, 2),
        end=Vector2.from_xy_mm(3, 4),
        width=250_000,
        layer=BoardLayer.Value("BL_F_Cu"),
        net=_net("GND"),
        locked=False,
    )
    arc = SimpleNamespace(
        start=Vector2.from_xy_mm(3, 4),
        mid=Vector2.from_xy_mm(4, 5),
        end=Vector2.from_xy_mm(5, 4),
        width=150_000,
        layer=BoardLayer.Value("BL_B_Cu"),
        net=_net("SIG"),
        locked=True,
    )

    converted_segment = KicadIpc._track(segment)
    converted_arc = KicadIpc._track(arc)

    assert converted_segment == layout_lib.TrackSegment(
        start=layout_lib.LayoutPoint(1, 2),
        end=layout_lib.LayoutPoint(3, 4),
        width=0.25,
        layer="F.Cu",
        net_name="GND",
    )
    assert isinstance(converted_arc, layout_lib.TrackArc)
    assert converted_arc.mid == layout_lib.LayoutPoint(4, 5)
    assert converted_arc.layer == "B.Cu"
    assert converted_arc.locked is True


def test_ipc_converts_single_layer_zone_source_outline():
    points = [
        Vector2.from_xy_mm(0, 0),
        Vector2.from_xy_mm(10, 0),
        Vector2.from_xy_mm(10, 10),
        Vector2.from_xy_mm(0, 0),
    ]
    zone = SimpleNamespace(
        is_rule_area=lambda: False,
        layers=[BoardLayer.Value("BL_B_Cu")],
        outline=SimpleNamespace(
            outline=[SimpleNamespace(has_point=True, point=point) for point in points],
            holes=[],
        ),
        net=_net("GND"),
        name="Ground plane",
        clearance=500_000,
        min_thickness=250_000,
        priority=2,
        filled=True,
        locked=False,
    )

    converted = KicadIpc._zone(zone)

    assert converted.layers == ("B.Cu",)
    assert converted.outline == (
        layout_lib.LayoutPoint(0, 0),
        layout_lib.LayoutPoint(10, 0),
        layout_lib.LayoutPoint(10, 10),
    )
    assert converted.clearance == 0.5
    assert converted.priority == 2


def test_ipc_converts_through_via():
    via = SimpleNamespace(
        type=1,
        position=Vector2.from_xy_mm(3, 4),
        net=_net("GND"),
        diameter=800_000,
        drill_diameter=400_000,
    )

    assert KicadIpc._via(via) == layout_lib.ViaConfig(
        layout_lib.Position(3, 4, 0), "GND", 0.8, 0.4
    )
