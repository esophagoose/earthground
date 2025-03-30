import kiutils.board
import kiutils.footprint as fp
import kiutils.items.brditems as brditems
import kiutils.items.common as base
import pygerber.aperture as ap_lib

import earthground.components as cmp
import earthground.exporters.kicad as kicad
import earthground.schematic as sch_lib


class Layout:
    def __init__(self, schematic: sch_lib.Design, layer_count: int) -> None:
        self.components = {}
        self.schematic = schematic
        self.traces = []
        self.layer_count = layer_count

    def find(self, refdes: str) -> cmp.Component:
        for component in self.schematic.components.values():
            if component.refdes == refdes:
                return component
        raise ValueError(f"{refdes} not found!")

    def move(self, refdes, x, y, rotation=0):
        self.components[refdes] = base.Position(x, y, rotation)

    def auto_route(self, exceptions=[]):
        for name, net in self.schematic.nets.items():
            if name in exceptions:
                continue
            print(f"{name} ==========================")
            self._auto_route_net(net)
            print("==================================")

    def _auto_route_net(self, net: cmp.Net):
        # Assuming net.connections is a list of tuples (x, y) representing pin locations
        # Sort connections to minimize the total distance traveled
        locations = []
        for pin in net.connections:
            component = pin.parent
            position = self.components.get(component.refdes)
            if position:
                x, y = component.footprint.pads[pin.index].location
                pad = base.Position(x, y, angle=position.angle)
                locations.append((position.X + pad.X, position.Y + pad.Y))
        connections = sorted(locations, key=lambda x: (x[0], x[1]))

        # Create segments between sorted pins using 45 deg angles
        segments = []
        for i in range(len(connections) - 1):
            start = connections[i]
            end = connections[i + 1]
            dx = end[0] - start[0]
            dy = end[1] - start[1]

            if abs(dx) > abs(dy):
                # Move diagonally, then horizontally
                intermediate_point = (start[0] + dy, start[1] + dy)
            else:
                # Move diagonally, then vertically
                intermediate_point = (start[0] + dx, start[1] + dx)

            # Create segments: start to intermediate, intermediate to end
            segments.append((start, intermediate_point))
            segments.append((intermediate_point, end))
            self.traces.append(
                brditems.Segment(kicad.to_pos(start), kicad.to_pos(intermediate_point))
            )
            self.traces.append(
                brditems.Segment(kicad.to_pos(intermediate_point), kicad.to_pos(end))
            )
        print(segments)

    def export(self, output_location):
        k = kicad.KicadExporter(self.schematic, self.components)
        k.board.traceItems.extend(self.traces)
        k.save(output_location)
