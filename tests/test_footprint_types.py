import earthground.footprint_types as ft


def test_quad_side_locations():
    count = 12
    width = 10.0
    pitch = 2.5
    expected_locations = [
        (1, -5.0, -2.5, 0),
        (2, -5.0, 0.0, 0),
        (3, -5.0, 2.5, 0),
        (4, -2.5, 5.0, 90),
        (5, 0.0, 5.0, 90),
        (6, 2.5, 5.0, 90),
        (7, 5.0, 2.5, 0),
        (8, 5.0, -0.0, 0),
        (9, 5.0, -2.5, 0),
        (10, 2.5, -5.0, 90),
        (11, -0.0, -5.0, 90),
        (12, -2.5, -5.0, 90),
    ]
    result = list(ft.get_quad_side_locations(count, width, pitch))
    assert result == expected_locations


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
