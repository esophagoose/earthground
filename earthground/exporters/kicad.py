import pathlib
from typing import Dict, Optional, Tuple

import kiutils.board
import kiutils.footprint as fp
import kiutils.items.common as base
import pygerber.aperture as ap_lib

import earthground.components as cmp
import earthground.schematic as sch_lib


def to_pos(coordinates):
    return base.Position(X=coordinates[0], Y=coordinates[1])

def shift(position: base.Position, offset: Tuple[float, float]) -> base.Position:
    return base.Position(X=position.X + offset[0], Y=position.Y + offset[1], angle=position.angle)


def _to_kiutil_position(position: sch_lib.Position) -> base.Position:
    if isinstance(position, base.Position):
        return position
    return base.Position(X=position.x, Y=position.y, angle=position.angle)


def aperture_to_shape_size(aperture):
    if isinstance(aperture, ap_lib.ApertureRectangle):
        return "rect", base.Position(aperture.width, aperture.height)
    if isinstance(aperture, ap_lib.ApertureCircle):
        return "circle", base.Position(aperture.diameter, aperture.diameter)
    raise NotImplementedError(f"Unsupported aperture: {aperture}")

def get_index(fp: fp.Footprint) -> Optional[str]:
    return fp.properties.get("Reference", None)


def get_index_fptext(footprint: fp.Footprint) -> Optional[fp.FpText]:
    for item in footprint.graphicItems:
        if isinstance(item, fp.FpText) and item.type == "reference":
            return item


class KicadExporter:
    def __init__(self, schematic: sch_lib.Design):
        """
        A class to export schematic designs to KiCad format.

        :param schematic: The schematic design to be exported.
        :type schematic: sch_lib.Design
        :param positions: Dictionary mapping component refdes to positions or concise layout dicts.
        :type positions: dict
        :type board_path: Optional[pathlib.Path or str]
        """
        self.board = kiutils.board.Board.create_new()
        self.schematic = schematic
        self.assigned_layout: Dict[str, sch_lib.ComponentLayout] = schematic.layout
        self._added_nets: Dict[str, base.Net] = {}
        self._y_offset = 0


    
    def convert_to_kicad(self, schematic: sch_lib.Design):
        x0 = 0
        y0 = self._y_offset * 20
        managed_layout = False
        if schematic in self.schematic.modules and schematic.short_name in self.schematic.layout:
            layout = self.schematic.layout[schematic.short_name]
            x0 = layout.component.x
            y0 = layout.component.y
            managed_layout = True
        net_index_start = len(self.board.nets)
        component_spacing = 5

        # Map existing nets by name
        for i, net in enumerate(schematic.nets.values()):
            kicad_net = base.Net(number=i + net_index_start + 1, name=net.name)
            self.board.nets.append(kicad_net)
            self._added_nets[net.name] = kicad_net
        
        # Process components
        for cid, component in schematic.components.items():
            if component.virtual:
                continue

            # Generate default position for new footprints
            bbox = component.footprint.get_bbox()
            if not managed_layout and cid not in schematic.layout:
                x0 += (bbox.width() + component_spacing)
            f_pos = base.Position(X=x0, Y=y0, angle=0)
            id_pos = base.Position(X=0, Y=0, angle=0)
    
            # Check if component has a set position
            if cid in schematic.layout:
                layout = schematic.layout[cid]
                f_pos = shift(_to_kiutil_position(layout.component), (x0, y0))
                id_pos = _to_kiutil_position(layout.id if layout.id else id_pos)
            footprint = self.parse_footprint(component, f_pos, id_pos, schematic)
            self.board.footprints.append(footprint)

    
    def parse_footprint(self, component: cmp.Component, position: base.Position, id_position: base.Position, schematic: sch_lib.Design) -> fp.Footprint:
        footprint = fp.Footprint.create_new(
            library_id=component.name,
            value=component.footprint.name,
            reference=component.refdes,
        )
        for index, pad in component.footprint.pads.items():
            shape, size = aperture_to_shape_size(pad.aperture)
            pin = component.pins[index]
            net = schematic.pin_to_net.get(pin)
            kicad_net = None
            if net:
                kicad_net = self._added_nets[net.name]
            hole = getattr(pad.aperture, "hole", None)
            layer = "*" if hole else "F"
            footprint.pads.append(
                fp.Pad(
                    number=str(index),
                    type="thru_hole" if hole else "smd",
                    shape=shape,
                    position=to_pos(pad.location),
                    size=size,
                    drill=fp.DrillDefinition(diameter=hole) if hole else None,
                    layers=[f"{layer}.Cu", f"{layer}.Mask"],
                    net=kicad_net,
                )
            )
        # Add silk layer information to the footprint
        footprint.graphicItems.append(
            fp.FpText(
                type="reference",
                text=component.refdes,
                position=id_position,
                layer="F.SilkS",
            )
        )
        for polysilk in component.footprint.silk:
            for i in range(len(polysilk) - 1):
                previous, current = polysilk[i : i + 2]
                line = fp.FpLine(to_pos(previous), to_pos(current), "F.SilkS")
                footprint.graphicItems.append(line)
        footprint.position = position
        return footprint


    
    def save(self, output_folder="./generated_outputs/", overwrite=False):
        """
        Saves design as `kicad_pcb` file

        :param output_folder: Folder to export the KiCad layout to (used if board_path is None)
        :type output_folder: str
        :param board_path: Optional path to save the board file. If None, uses output_folder and schematic name.
        :type board_path: Optional[pathlib.Path or str]
        :return: None
        """
        path = pathlib.Path(output_folder) / f"{self.schematic.name}.kicad_pcb"
        if overwrite:
            current_board = kiutils.board.Board.from_file(path)
            for fp in current_board.footprints:
                text = get_index_fptext(fp)
                self.assigned_layout[get_index(fp)] = sch_lib.ComponentLayout(
                    component=fp.position,
                    id=text.position if text else base.Position(X=0, Y=0, angle=0),
                )
        self.convert_to_kicad(self.schematic)
        for module in self.schematic.modules:
            self._y_offset += 1
            self.convert_to_kicad(module)
        self.board.to_file(path)
        print(f"{"Overwrote" if overwrite else "Wrote"} board file: {path}")
