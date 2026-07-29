import pytest
import pygerber.aperture as ap_lib

import earthground.footprint_types as ft


def test_quad_side_locations():
    count = 12
    width = 10.0
    pitch = 2.5
    pad = ap_lib.ApertureRectangle(1.0, 0.5, radius=0.1)
    result = list(ft.get_quad_side_locations(count, width, pitch, pad))

    expected_locations = {
        1: ([-5.0, -2.5], 1.0, 0.5, 0),
        2: ([-5.0, 0.0], 1.0, 0.5, 0),
        3: ([-5.0, 2.5], 1.0, 0.5, 0),
        4: ([-2.5, 5.0], 0.5, 1.0, 90),
        5: ([0.0, 5.0], 0.5, 1.0, 90),
        6: ([2.5, 5.0], 0.5, 1.0, 90),
        7: ([5.0, 2.5], 1.0, 0.5, 0),
        8: ([5.0, -0.0], 1.0, 0.5, 0),
        9: ([5.0, -2.5], 1.0, 0.5, 0),
        10: ([2.5, -5.0], 0.5, 1.0, 90),
        11: ([-0.0, -5.0], 0.5, 1.0, 90),
        12: ([-2.5, -5.0], 0.5, 1.0, 90),
    }
    for index, generated_pad in result:
        location, width, height, rotation = expected_locations[index]
        assert generated_pad.location == location
        assert generated_pad.aperture.width == width
        assert generated_pad.aperture.height == height
        assert generated_pad.aperture.rotation == rotation


def test_get_dual_side_locations():
    count = 12
    width = 10.0
    pitch = 2.5
    expected_locations = [
        (1, -5.0, -6.25),
        (2, -5.0, -3.75),
        (3, -5.0, -1.25),
        (4, -5.0, 1.25),
        (5, -5.0, 3.75),
        (6, -5.0, 6.25),
        (7, 5.0, 6.25),
        (8, 5.0, 3.75),
        (9, 5.0, 1.25),
        (10, 5.0, -1.25),
        (11, 5.0, -3.75),
        (12, 5.0, -6.25),
    ]
    result = list(ft.get_dual_side_locations(count, width, pitch))
    assert result == expected_locations


def test_get_bbox_accounts_for_rotation_and_negative_coordinates():
    footprint = ft.BaseFootprint()
    footprint.pads = {
        "1": ft.Pad(
            location=[-10, -10],
            aperture=ap_lib.ApertureRectangle(
                width=4,
                height=2,
                rotation=90,
            ),
        )
    }

    bbox = footprint.get_bbox()

    assert bbox.x1 == pytest.approx(-11)
    assert bbox.y1 == pytest.approx(-12)
    assert bbox.x2 == pytest.approx(-9)
    assert bbox.y2 == pytest.approx(-8)
