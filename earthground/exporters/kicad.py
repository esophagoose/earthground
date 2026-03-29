import logging
import pathlib
from typing import Dict, Optional, Tuple

import kiutils.board
import kiutils.footprint as fp
import kiutils.items.brditems as kibrditems
import kiutils.items.common as base
import kiutils.items.zones as kizones
import kiutils.utils.sexpr as sexpr_utils
import pygerber.aperture as ap_lib

import earthground.components as cmp
import earthground.layout as layout_lib
import earthground.schematic as sch_lib
from earthground.importers.kicad import KicadFootprint


def to_pos(coordinates, angle=0):
    return base.Position(X=coordinates[0], Y=coordinates[1], angle=angle)


def to_position(coordinates, angle=None):
    return base.Position(X=coordinates[0], Y=coordinates[1], angle=angle)


def shift(position: base.Position, offset: Tuple[float, float]) -> base.Position:
    return base.Position(X=position.X + offset[0], Y=position.Y + offset[1], angle=position.angle)


def _to_kiutil_position(position: layout_lib.Position) -> base.Position:
    if isinstance(position, base.Position):
        return position
    return base.Position(X=position.x, Y=position.y, angle=position.angle)


def _is_bottom_layer(layer: layout_lib.Layer) -> bool:
    return layer == layout_lib.Layer.BOTTOM


def _side_prefix(layer: layout_lib.Layer) -> str:
    return "B" if _is_bottom_layer(layer) else "F"


def _map_side_layer_name(layer_name: str, target_prefix: str) -> str:
    if layer_name.startswith("F.") or layer_name.startswith("B."):
        return f"{target_prefix}.{layer_name.split('.', 1)[1]}"
    return layer_name


def _map_pad_layers(layers: list[str], target_prefix: str) -> list[str]:
    mapped_layers = []
    for layer_name in layers:
        if layer_name.startswith("*."):
            mapped_layers.append(layer_name)
        else:
            mapped_layers.append(_map_side_layer_name(layer_name, target_prefix))
    return mapped_layers


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


def _ensure_kicad_net(
    exporter: "KicadExporter",
    schematic: sch_lib.Design,
    net_name: str,
) -> base.Net:
    if net_name in exporter._added_nets:
        return exporter._added_nets[net_name]
    kicad_net = base.Net(number=len(exporter.board.nets) + 1, name=net_name)
    exporter.board.nets.append(kicad_net)
    exporter._added_nets[net_name] = kicad_net
    return kicad_net


def _mirror_position_across_y_axis(position: base.Position) -> base.Position:
    angle = None if position.angle is None else -position.angle
    return base.Position(
        X=-position.X,
        Y=position.Y,
        angle=angle,
        unlocked=position.unlocked,
    )


def _mirror_graphic_item_across_y_axis(item) -> None:
    for attribute in ("position", "start", "end", "center", "mid"):
        value = getattr(item, attribute, None)
        if isinstance(value, base.Position):
            setattr(item, attribute, _mirror_position_across_y_axis(value))

    coordinates = getattr(item, "coordinates", None)
    if coordinates is not None:
        setattr(
            item,
            "coordinates",
            [
                _mirror_position_across_y_axis(position)
                if isinstance(position, base.Position)
                else position
                for position in coordinates
            ],
        )


def _mirror_footprint_geometry_across_y_axis(footprint: fp.Footprint) -> None:
    for item in footprint.graphicItems:
        _mirror_graphic_item_across_y_axis(item)
    for pad in footprint.pads:
        pad.position = _mirror_position_across_y_axis(pad.position)


def _apply_footprint_side(footprint: fp.Footprint, layer: layout_lib.Layer) -> None:
    layer_prefix = _side_prefix(layer)
    footprint.layer = f"{layer_prefix}.Cu"
    for item in footprint.graphicItems:
        if hasattr(item, "layer") and item.layer is not None:
            item.layer = _map_side_layer_name(item.layer, layer_prefix)
        if isinstance(item, fp.FpText):
            if item.effects is None:
                item.effects = base.Effects()
            if item.effects.justify is None:
                item.effects.justify = base.Justify()
            item.effects.justify.mirror = _is_bottom_layer(layer)


class KicadExporter:
    def __init__(self, schematic: sch_lib.Design, pcb_path: Optional[pathlib.Path] = None):
        """
        A class to export schematic designs to KiCad format.

        :param schematic: The schematic design to be exported.
        :type schematic: sch_lib.Design
        :param positions: Dictionary mapping component refdes to positions or concise layout dicts.
        :type positions: dict
        :type board_path: Optional[pathlib.Path or str]
        """
        if pcb_path:
            self.board = kiutils.board.Board.from_file(pcb_path)
        else:
            self.board = kiutils.board.Board.create_new()
            self.schematic = schematic
            self.assigned_layout: Dict[str, layout_lib.ComponentLayout] = schematic.layout.placement
            self._added_nets: Dict[str, base.Net] = {}
            inner_layers = list(range(self.schematic.layout.layer_count - 2))
            self._layer_map = ["F.Cu"] + [f"In{i+2}.Cu" for i in inner_layers] + ["B.Cu"]
            for i in inner_layers:
                self.board.layers.append(kibrditems.LayerToken(ordinal=2*i+4, name=f"In{i+2}.Cu"))
    
    def _collect_all_nets(self, schematic: sch_lib.Design) -> Dict[str, cmp.Net]:
        """
        Collect all nets from the design and all its modules recursively.

        Returns:
            Dictionary mapping net names to Net objects
        """
        all_nets = {}
        # Collect nets from this design
        for net_name, net in schematic.nets.items():
            all_nets[net_name] = net
        # Collect nets from all modules recursively
        for module in schematic.modules:
            module_nets = self._collect_all_nets(module)
            all_nets.update(module_nets)
        return all_nets

    def convert_to_kicad(self, schematic: sch_lib.Design):
        net_index_start = len(self.board.nets)
        flattened_layout = schematic.layout.flatten()

        all_nets = self._collect_all_nets(schematic)
        for i, net in enumerate(all_nets.values()):
            kicad_net = base.Net(number=i + net_index_start + 1, name=net.name)
            self.board.nets.append(kicad_net)
            self._added_nets[net.name] = kicad_net
        
        for cid, (layout, component) in flattened_layout.items():
            if component.virtual:
                continue
            f_pos = _to_kiutil_position(layout.component)
            id_pos = _to_kiutil_position(layout.id)
            
            footprint = self.parse_footprint(
                cid,
                component,
                f_pos,
                id_pos,
                component.parent,
                layout.id_orientation,
                layout.layer,
            )
            self.board.footprints.append(footprint)

        # Process pours and vias from the main schematic
        for pour in schematic.layout.pours:
            self.add_pours(pour)

        for via in schematic.layout.vias:
            logging.info("Adding via: ", via)
            self.add_via(via)
    
    def parse_footprint(
        self,
        cid: str | sch_lib.Design,
        component: cmp.Component,
        component_position: Optional[base.Position] = None,
        id_position: Optional[base.Position] = None,
        schematic: Optional[sch_lib.Design] = None,
        id_orientation: layout_lib.Orientation = layout_lib.Orientation.CENTER,
        layer: layout_lib.Layer = layout_lib.Layer.TOP,
    ) -> fp.Footprint:
        """
        Convert an earthground footprint into a KiCad footprint.

        Supports both native earthground footprints (ft.BaseFootprint) and
        imported KiCad footprints (importers.kicad.KicadFootprint).
        """
        if isinstance(cid, sch_lib.Design):
            schematic = cid
            cid = next(
                (
                    design_cid
                    for design_cid, design_component in schematic.components.items()
                    if design_component is component
                ),
                component.refdes,
            )
        if component_position is None:
            component_position = base.Position(X=0, Y=0, angle=0)
        if id_position is None:
            id_position = base.Position(X=0, Y=0, angle=0)
        if schematic is None:
            schematic = component.parent
        if schematic is None:
            raise ValueError("schematic is required to parse a footprint")

        self._validate_component(component)
        layer_prefix = _side_prefix(layer)

        # Determine reference text justification once
        justify_options = {}
        if id_orientation == layout_lib.Orientation.TOP:
            justify_options["vertically"] = "bottom"
        elif id_orientation == layout_lib.Orientation.BOTTOM:
            justify_options["vertically"] = "top"
        elif id_orientation == layout_lib.Orientation.LEFT:
            justify_options["horizontally"] = "right"
        elif id_orientation == layout_lib.Orientation.RIGHT:
            justify_options["horizontally"] = "left"
        if _is_bottom_layer(layer):
            justify_options["mirror"] = True

        # Case 1: Footprint imported directly from a KiCad .kicad_mod
        if isinstance(component.footprint, KicadFootprint):
            parsed = sexpr_utils.parse_sexp(component.footprint.sexp)
            footprint = fp.Footprint.from_sexpr(parsed)
            _apply_footprint_side(footprint, layer)

            # Re-map pad nets based on the schematic connectivity.
            for pad in footprint.pads:
                try:
                    index = int(pad.number)
                except (ValueError, TypeError):
                    continue
                pin = component.pins[index]
                net = schematic.pin_to_net.get(pin)
                if net:
                    pad.net = _ensure_kicad_net(self, schematic, net.name)
                pad.layers = _map_pad_layers(pad.layers, layer_prefix)

            # Update or add the reference text to match cid and id_position.
            ref_text = get_index_fptext(footprint)
            if ref_text is not None:
                ref_text.text = cid
                ref_text.position = id_position
                ref_text.layer = f"{layer_prefix}.SilkS"
                ref_text.effects.justify = base.Justify(**justify_options)
            else:
                footprint.graphicItems.append(
                    fp.FpText(
                        type="reference",
                        text=cid,
                        position=id_position,
                        layer=f"{layer_prefix}.SilkS",
                        effects=base.Effects(
                            font=base.Font(height=0.75, width=0.75, thickness=0.12),
                            justify=base.Justify(**justify_options),
                        ),
                    )
                )

            # If the component is rotated by 90° or 270°, swap pad width/height.
            # This matches how earthground's native footprints behave and keeps
            # pad dimensions consistent with the visual rotation.
            angle = component_position.angle
            if abs(angle) % 180 == 90:
                for pad in footprint.pads:
                    size = pad.size
                    pad.size = base.Position(X=size.Y, Y=size.X)
        else:
            # Case 2: Native earthground footprint definition
            footprint = fp.Footprint.create_new(
                library_id=component.name,
                value=component.footprint.name,
                reference=cid,
            )
            _apply_footprint_side(footprint, layer)
            for index, pad in component.footprint.pads.items():
                shape, size = aperture_to_shape_size(pad.aperture)
                pin = component.pins[index]
                net = schematic.pin_to_net.get(pin)
                kicad_net = None
                if net:
                    kicad_net = _ensure_kicad_net(self, schematic, net.name)
                hole = getattr(pad.aperture, "hole", None)
                pad_layer_prefix = "*" if hole else layer_prefix
                pad_layers = [f"{pad_layer_prefix}.Cu", f"{pad_layer_prefix}.Mask"]
                if not hole:
                    pad_layers.append(f"{pad_layer_prefix}.Paste")
                footprint.pads.append(
                    fp.Pad(
                        number=str(index),
                        type="thru_hole" if hole else "smd",
                        shape=shape,
                        position=to_pos(pad.location, angle=component_position.angle),
                        size=size,
                        drill=fp.DrillDefinition(diameter=hole) if hole else None,
                        layers=pad_layers,
                        net=kicad_net,
                    )
                )

            ref_text = get_index_fptext(footprint)
            if ref_text is not None:
                ref_text.text = cid
                ref_text.position = id_position
                ref_text.layer = f"{layer_prefix}.SilkS"
                ref_text.effects.justify = base.Justify(**justify_options)
            else:
                footprint.graphicItems.append(
                    fp.FpText(
                        type="reference",
                        text=cid,
                        position=id_position,
                        layer=f"{layer_prefix}.SilkS",
                        effects=base.Effects(
                            font=base.Font(height=0.75, width=0.75, thickness=0.12),
                            justify=base.Justify(**justify_options),
                        ),
                    )
                )
            for polysilk in component.footprint.silk:
                for i in range(len(polysilk) - 1):
                    previous, current = polysilk[i : i + 2]
                    line = fp.FpLine(
                        to_pos(previous),
                        to_pos(current),
                        f"{layer_prefix}.SilkS",
                    )
                    footprint.graphicItems.append(line)

        if _is_bottom_layer(layer):
            _mirror_footprint_geometry_across_y_axis(footprint)

        # Place and orient the footprint on the board.
        footprint.position = component_position
        footprint.position.angle = -component_position.angle
        return footprint

    def _validate_component(self, component: cmp.Component):
        if not component.footprint:
            raise RuntimeError(f"No footprint defined for: {component.name}")

    def draw_board_outline(self):
        outline = self.schematic.layout.outline
        self.board.graphicItems.append(fp.GrRect(
            start=to_pos((outline.x1, outline.y1)),
            end=to_pos((outline.x2, outline.y2)),
            layer="Edge.Cuts",
        ))

    def add_pours(self, config: layout_lib.PourLayer):
        outline = self.schematic.layout.outline
        polygon = kizones.ZonePolygon(coordinates=[to_pos((outline.x1, outline.y1)), to_pos((outline.x2, outline.y1)), to_pos((outline.x2, outline.y2)), to_pos((outline.x1, outline.y2))])
        self.board.zones.append(kizones.Zone(
            net=self._added_nets[config.net_name].number,
            layers=[self._layer_map[config.layer - 1]],
            hatch=kizones.Hatch(style='edge', pitch=0.5),
            clearance=0.5,
            minThickness=0.25,
            polygons=[polygon])
        )

    def add_via(self, config: layout_lib.ViaConfig):
        self.board.traceItems.append(kibrditems.Via(
            position=to_pos(config.location),
            size=config.hole_size,
            drill=config.drill_size,
            layers=["F.Cu", "B.Cu"],
            net=self._added_nets[config.net_name].number,
        ))

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
        self.convert_to_kicad(self.schematic)
        self.draw_board_outline()
        self.board.to_file(path)
        print(f"{"Overwrote" if overwrite else "Wrote"} board file: {path}")
