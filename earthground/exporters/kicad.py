import pathlib

import kiutils.board
import kiutils.footprint as fp
import kiutils.items.common as base
import pygerber.aperture as ap_lib

import earthground.components as cmp
import earthground.layout as layout_lib
import earthground.schematic as sch_lib


def to_pos(coordinates):
    return base.Position(X=coordinates[0], Y=coordinates[1])


def _layer_prefix(layer: layout_lib.Layer) -> str:
    """Convert a layout Layer to a KiCad layer prefix."""
    if layer == layout_lib.Layer.BOTTOM:
        return "B"
    return "F"


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

        Uses ``schematic.layout`` for component placement if available.

        :param schematic: The schematic design to be exported.
        :type schematic: sch_lib.Design
        """
        self.board = kiutils.board.Board.create_new()
        self.schematic = schematic
        self._added_nets = {}
        layout = getattr(schematic, "layout", None)
        net_counter = 1

        for y, module in enumerate(schematic.modules + [schematic]):
            self._added_nets[module.name] = {}
            for net in module.nets.values():
                kicad_net = base.Net(number=net_counter, name=net.name)
                net_counter += 1
                self._added_nets[module.name][net.name] = kicad_net
                self.board.nets.append(kicad_net)
            for x, component in enumerate(module.components.values()):
                if component.virtual:
                    continue
                placement = layout.placement.get(component.refdes) if layout else None
                layer = layout_lib.Layer.TOP
                if placement:
                    layer = placement.layer
                footprint = self.parse_footprint(module, component, layer)
                if placement:
                    footprint.position = base.Position(
                        X=placement.position.x,
                        Y=placement.position.y,
                    )
                    footprint.position.angle = placement.rotation
                else:
                    footprint.position = base.Position(X=10 * (x + 1),
                                                       Y=50 * (y + 1))
                self.board.footprints.append(footprint)

    def parse_footprint(self, design: sch_lib.Design,
                        component: cmp.Component,
                        layer: layout_lib.Layer = layout_lib.Layer.TOP) -> fp.Footprint:
        lp = _layer_prefix(layer)
        footprint = fp.Footprint.create_new(
            library_id=component.name,
            value=component.footprint.name,
            reference=component.refdes,
        )
        if layer == layout_lib.Layer.BOTTOM:
            footprint.layer = "B.Cu"
        for index, pad in component.footprint.pads.items():
            shape, size = aperture_to_shape_size(pad.aperture)
            pin = component.pins[index]
            net = design.pin_to_net.get(pin)
            kicad_net = None
            if net:
                kicad_net = self._added_nets[design.name][net.name]
            hole = getattr(pad.aperture, "hole", None)
            pad_layer = "*" if hole else lp
            footprint.pads.append(
                fp.Pad(
                    number=str(index),
                    type="thru_hole" if hole else "smd",
                    shape=shape,
                    position=to_pos(pad.location),
                    size=size,
                    drill=fp.DrillDefinition(diameter=hole) if hole else hole,
                    layers=[f"{pad_layer}.Cu", f"{pad_layer}.Mask"],
                    net=kicad_net,
                ))
        # Add silk layer information to the footprint
        silk_layer = f"{lp}.SilkS"
        footprint.graphicItems.append(
            fp.FpText(
                type="reference",
                text=component.refdes,
                position=base.Position(X=0, Y=0),
                layer=silk_layer,
            ))
        for polysilk in component.footprint.silk:
            for i in range(len(polysilk) - 1):
                print(polysilk[i:i + 2])
                previous, current = polysilk[i:i + 2]
                line = fp.FpLine(to_pos(previous), to_pos(current), silk_layer)
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