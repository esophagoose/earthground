import pathlib

import kiutils.board
import kiutils.footprint as fp
import kiutils.items.common as base
import pygerber.aperture as ap_lib

import earthground.components as cmp
import earthground.schematic as sch_lib


def to_pos(coordinates):
    return base.Position(X=coordinates[0], Y=coordinates[1])


def aperture_to_shape_size(aperture):
    if isinstance(aperture, ap_lib.ApertureRectangle):
        return "rect", base.Position(aperture.width, aperture.height)
    if isinstance(aperture, ap_lib.ApertureCircle):
        return "circle", base.Position(aperture.diameter, aperture.diameter)
    raise NotImplementedError(f"Unsupported aperture: {aperture}")


class KicadExporter:

    def __init__(self, schematic: sch_lib.Design):
        """
        A class to export schematic designs to KiCad format.

        :param schematic: The schematic design to be exported.
        :type schematic: sch_lib.Design
        """
        self.board = kiutils.board.Board.create_new()
        self.schematic = schematic
        self._added_nets = {}

        for y, module in enumerate(schematic.modules + [schematic]):
            self._added_nets[module.name] = {}
            for i, net in enumerate(module.nets.values()):
                kicad_net = base.Net(number=i + 1, name=net.name)
                self._added_nets[module.name][net.name] = kicad_net
                self.board.nets.append(kicad_net)
            for x, component in enumerate(module.components.values()):
                if component.virtual:
                    continue
                footprint = self.parse_footprint(module, component)
                footprint.position = base.Position(X=10 * (x + 1),
                                                   Y=50 * (y + 1))
                self.board.footprints.append(footprint)

    def parse_footprint(self, design: sch_lib.Design,
                        component: cmp.Component) -> fp.Footprint:
        footprint = fp.Footprint.create_new(
            library_id=component.name,
            value=component.footprint.name,
            reference=component.refdes,
        )
        for index, pad in component.footprint.pads.items():
            shape, size = aperture_to_shape_size(pad.aperture)
            pin = component.pins[index]
            net = design.pin_to_net.get(pin)
            kicad_net = None
            if net:
                kicad_net = self._added_nets[design.name][net.name]
            hole = getattr(pad.aperture, "hole", None)
            layer = "*" if hole else "F"
            footprint.pads.append(
                fp.Pad(
                    number=str(index),
                    type="thru_hole" if hole else "smd",
                    shape=shape,
                    position=to_pos(pad.location),
                    size=size,
                    drill=fp.DrillDefinition(diameter=hole) if hole else hole,
                    layers=[f"{layer}.Cu", f"{layer}.Mask"],
                    net=kicad_net,
                ))
        # Add silk layer information to the footprint
        footprint.graphicItems.append(
            fp.FpText(
                type="reference",
                text=component.refdes,
                position=base.Position(X=0, Y=0),
                layer="F.SilkS",
            ))
        for polysilk in component.footprint.silk:
            for i in range(len(polysilk) - 1):
                print(polysilk[i:i + 2])
                previous, current = polysilk[i:i + 2]
                line = fp.FpLine(to_pos(previous), to_pos(current), "F.SilkS")
                footprint.graphicItems.append(line)
        return footprint

    def save(self, output_folder="."):
        """
        Saves design as `kicad_pcb` file

        :param output_folder: Folder to export the KiCad layout to
        :type output_folder: str
        :return: None
        """
        path = pathlib.Path(output_folder) / f"{self.schematic.name}.kicad_pcb"
        self.board.to_file(path)
        print(f"Wrote board file: {path}")