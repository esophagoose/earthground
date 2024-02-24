import math


class ElectricalBool:
    def __init__(self, logic_high_name="VCC", logic_low_name="GND"):
        self.high = logic_high_name
        self.low = logic_low_name

    def to_int(self, net_name: str) -> bool:
        if self.high == net_name:
            return 1
        elif self.low == net_name:
            return 0
        else:
            raise ValueError(f"Undefined value for net: {net_name}")

    def to_net(self, value: bool) -> str:
        return self.high if value else self.low


def add(tuple1, tuple2):
    assert len(tuple1) == len(tuple2), "Mismatched sized tuples!"
    return tuple([t + tuple2[i] for i, t in enumerate(tuple1)])


def rotate(location, origin, angle):
    x, y = location
    ox, oy = origin
    angle = math.radians(angle)
    new_x = ox + math.cos(angle) * (x - ox) - math.sin(angle) * (y - oy)
    new_y = oy + math.sin(angle) * (x - ox) + math.cos(angle) * (y - oy)
    return new_x, new_y


def scale(data, scalar):
    return tuple([d / scalar for d in data])


def four_corner_rect(x0, y0, x1, y1):
    center_x = (x0 + x1) / 2
    center_y = (y0 + y1) / 2
    width = abs(x1 - x0)
    height = abs(y1 - y0)
    return (center_x, center_y), width, height
