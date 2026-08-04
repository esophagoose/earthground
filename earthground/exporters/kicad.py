import logging
import pathlib
from typing import Dict, Optional

import pygerber.aperture as ap_lib
from pykicad import (
    BoardSide,
    FootprintBuilder,
    Pcb,
    PcbBuilder,
    read_from_file,
    text_effects,
    write_to_file,
)
from pykicad.models.base import Point
import pykicad.models.pcb as pcb

import earthground.components as cmp
import earthground.layout as layout_lib
import earthground.schematic as sch_lib
import earthground.signal_integrity as signal_integrity
from earthground.exporters.kicad_project import save_constraints
from earthground.importers.kicad import KicadFootprint

log = logging.getLogger(__name__)


def _to_kicad_position(position: layout_lib.Position | pcb.Position) -> pcb.Position:
    if isinstance(position, pcb.Position):
        return position
    return pcb.Position(x=position.x, y=position.y, angle=position.angle)


def _is_bottom_layer(layer: layout_lib.Layer) -> bool:
    return layer == layout_lib.Layer.BOTTOM


def _board_side(layer: layout_lib.Layer) -> BoardSide:
    return BoardSide.BACK if _is_bottom_layer(layer) else BoardSide.FRONT


def aperture_to_shape_size(aperture):
    if isinstance(aperture, ap_lib.ApertureRectangle):
        return "rect", pcb.Size(width=aperture.width, height=aperture.height)
    if isinstance(aperture, ap_lib.ApertureCircle):
        return "circle", pcb.Size(
            width=aperture.diameter,
            height=aperture.diameter,
        )
    raise NotImplementedError(f"Unsupported aperture: {aperture}")


def _reference_justify(
    orientation: layout_lib.Orientation,
    layer: layout_lib.Layer,
) -> pcb.Justify:
    horizontal = None
    vertical = None
    if orientation == layout_lib.Orientation.TOP:
        vertical = "bottom"
    elif orientation == layout_lib.Orientation.BOTTOM:
        vertical = "top"
    elif orientation == layout_lib.Orientation.LEFT:
        horizontal = "right"
    elif orientation == layout_lib.Orientation.RIGHT:
        horizontal = "left"
    return pcb.Justify(
        horizontal=horizontal,
        vertical=vertical,
        mirror=_is_bottom_layer(layer),
    )


def get_index(footprint: pcb.Footprint) -> Optional[str]:
    reference = FootprintBuilder(footprint).reference
    return reference.value if reference is not None else None


def get_index_fptext(
    footprint: pcb.Footprint,
) -> Optional[pcb.Property | pcb.FpText]:
    return FootprintBuilder(footprint).reference


def _set_text_hidden(item: pcb.Property | pcb.FpText, hidden: bool) -> None:
    if isinstance(item, pcb.Property):
        item.hide = hidden
        return
    if item.effects is None:
        item.effects = text_effects()
    item.effects.hide = hidden


def _hide_text_on_layer(footprint: pcb.Footprint, suffix: str) -> None:
    for item in FootprintBuilder(footprint).iter_text():
        if item.layer and item.layer.endswith(suffix):
            _set_text_hidden(item, True)


class KicadExporter:
    def __init__(
        self,
        schematic: sch_lib.Design,
        pcb_path: Optional[pathlib.Path] = None,
        add_silkscreen_text: bool = True,
        add_fab_text: bool = True,
    ):
        self.schematic = schematic
        self.add_silkscreen_text = add_silkscreen_text
        self.add_fab_text = add_fab_text
        self.assigned_layout: Dict[str, layout_lib.ComponentLayout] = (
            schematic.layout.placement
        )

        if pcb_path:
            board = read_from_file(pcb_path).model
            if not isinstance(board, Pcb):
                raise TypeError(f"Expected a KiCad PCB document: {pcb_path}")
            self.builder = PcbBuilder(board)
        else:
            self.builder = PcbBuilder.create(
                generator="earthground",
                copper_layer_count=self.schematic.layout.layer_count,
            )
        self.board = self.builder.model

    def _collect_all_nets(self, schematic: sch_lib.Design) -> Dict[str, cmp.Net]:
        all_nets = dict(schematic.nets)
        for module in schematic.modules:
            all_nets.update(self._collect_all_nets(module))
        return all_nets

    def convert_to_kicad(self, schematic: sch_lib.Design):
        flattened_layout = schematic.layout.flatten()

        for net in self._collect_all_nets(schematic).values():
            self.builder.ensure_net(net.name)

        for cid, (component_layout, component) in flattened_layout.items():
            if component.virtual:
                continue
            footprint = self.parse_footprint(
                cid,
                component,
                _to_kicad_position(component_layout.component),
                _to_kicad_position(component_layout.id),
                component.parent,
                component_layout.id_orientation,
                component_layout.layer,
                add_silkscreen_text=self.add_silkscreen_text,
                add_fab_text=self.add_fab_text,
            )
            self.builder.add_footprint(footprint)

        for pour in schematic.layout.pours:
            self.add_pours(pour)

        for via in schematic.layout.vias:
            log.info("Adding via: %s", via)
            self.add_via(via)

    def parse_footprint(
        self,
        cid: str | sch_lib.Design,
        component: cmp.Component,
        component_position: Optional[pcb.Position] = None,
        id_position: Optional[pcb.Position] = None,
        schematic: Optional[sch_lib.Design] = None,
        id_orientation: layout_lib.Orientation = layout_lib.Orientation.CENTER,
        layer: layout_lib.Layer = layout_lib.Layer.TOP,
        add_silkscreen_text: bool = True,
        add_fab_text: bool = True,
    ) -> pcb.Footprint:
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
        component_position = component_position or pcb.Position(x=0, y=0, angle=0)
        id_position = id_position or pcb.Position(x=0, y=0, angle=0)
        schematic = schematic or component.parent
        if schematic is None:
            raise ValueError("schematic is required to parse a footprint")

        self._validate_component(component)
        reference_justify = _reference_justify(id_orientation, layer)

        if isinstance(component.footprint, KicadFootprint):
            footprint_builder = FootprintBuilder(
                component.footprint.footprint
            ).instantiate(
                reference=str(cid),
                at=pcb.Position(
                    x=component_position.x,
                    y=component_position.y,
                    angle=-component_position.angle,
                ),
                side=_board_side(layer),
                reference_at=id_position,
                reference_layer="F.SilkS",
                reference_effects=text_effects(justify=reference_justify),
            )
            footprint = footprint_builder.model
            if component.mpn:
                footprint.description = component.mpn

            for pad in footprint.pads:
                if pad.pad_type == "np_thru_hole":
                    continue
                try:
                    index = int(pad.number)
                except (ValueError, TypeError):
                    index = pad.number
                try:
                    pin = component.pins[index]
                except (KeyError, TypeError, ValueError):
                    # PinContainer.by_index raises ValueError for an unknown
                    # index. Pads with no matching pin are normal KiCad
                    # geometry, including unnumbered paste apertures and
                    # mechanical or shield pads; preserve them without a net.
                    continue
                net = schematic.pin_to_net.get(pin)
                if net:
                    pad.net = self.builder.ensure_net(net.name)

            if abs(component_position.angle) % 180 == 90:
                for pad in footprint.pads:
                    if pad.size is not None:
                        pad.size = pcb.Size(
                            width=pad.size.height,
                            height=pad.size.width,
                        )
        else:
            footprint_builder = FootprintBuilder.create(
                component.name,
                description=component.mpn or None,
            )
            footprint_builder.set_reference(
                str(cid),
                at=id_position,
                layer="F.SilkS",
                effects=text_effects(justify=reference_justify),
            )
            footprint_builder.set_property(
                "Value",
                component.footprint.name,
                at=pcb.Position(x=0, y=0),
                layer="F.Fab",
                hide=not add_fab_text,
            )

            for index, pad in component.footprint.pads.items():
                shape, size = aperture_to_shape_size(pad.aperture)
                pin = component.pins[index]
                net = schematic.pin_to_net.get(pin)
                net_ref = self.builder.ensure_net(net.name) if net else None
                hole = getattr(pad.aperture, "hole", None)
                pad_layer_prefix = "*" if hole else "F"
                pad_layers = [f"{pad_layer_prefix}.Cu", f"{pad_layer_prefix}.Mask"]
                if not hole:
                    pad_layers.append(f"{pad_layer_prefix}.Paste")
                footprint_builder.add_pad(
                    str(index),
                    pad_type="thru_hole" if hole else "smd",
                    shape=shape,
                    at=pcb.Position(
                        x=pad.location[0],
                        y=pad.location[1],
                        angle=component_position.angle,
                    ),
                    size=size,
                    drill=pcb.PadDrill(diameter=hole) if hole else None,
                    layers=pad_layers,
                    net=net_ref,
                )

            for polysilk in component.footprint.silk:
                for index in range(len(polysilk) - 1):
                    previous, current = polysilk[index : index + 2]
                    footprint_builder.add_line(
                        Point(x=previous[0], y=previous[1]),
                        Point(x=current[0], y=current[1]),
                        layer="F.SilkS",
                    )

        reference = footprint_builder.reference
        if reference is not None:
            _set_text_hidden(reference, not add_silkscreen_text)
        if not add_silkscreen_text:
            _hide_text_on_layer(footprint_builder.model, ".SilkS")
        if not add_fab_text:
            _hide_text_on_layer(footprint_builder.model, ".Fab")

        footprint_builder.set_property(
            "MPN",
            component.mpn or "",
            at=pcb.Position(x=0, y=0),
            layer=f"{'B' if _is_bottom_layer(layer) else 'F'}.Fab",
            hide=True,
        )
        footprint_builder.set_property(
            "Manufacturer",
            component.manufacturer or "",
            at=pcb.Position(x=0, y=0),
            layer=f"{'B' if _is_bottom_layer(layer) else 'F'}.Fab",
            hide=True,
        )
        metadata = {
            "Datasheet": component.datasheet,
            "Datasheet Revision": component.datasheet_revision,
            "Datasheet SHA256": component.datasheet_sha256,
            "Lifecycle": component.lifecycle.value,
        }
        metadata.update(
            {
                f"Distributor:{name.lower()}": identifier
                for name, identifier in sorted(component.distributor_ids.items())
            }
        )
        for name, value in metadata.items():
            footprint_builder.set_property(
                name,
                value or "",
                at=pcb.Position(x=0, y=0),
                layer=f"{'B' if _is_bottom_layer(layer) else 'F'}.Fab",
                hide=True,
            )
        if not isinstance(component.footprint, KicadFootprint):
            footprint_builder.place(
                pcb.Position(
                    x=component_position.x,
                    y=component_position.y,
                    angle=-component_position.angle,
                ),
                side=_board_side(layer),
            )
        return footprint_builder.model

    def _validate_component(self, component: cmp.Component):
        if not component.footprint:
            raise RuntimeError(f"No footprint defined for: {component.name}")

    def draw_board_outline(self):
        outline = self.schematic.layout.outline
        self.builder.add_graphic_rect(
            Point(x=outline.x1, y=outline.y1),
            Point(x=outline.x2, y=outline.y2),
            layer="Edge.Cuts",
        )

    def draw_fab_lines(self):
        for item in self.schematic.layout.flatten_fab():
            if isinstance(item, layout_lib.FabLine):
                self.builder.add_graphic_line(
                    Point(x=item.start.x, y=item.start.y),
                    Point(x=item.end.x, y=item.end.y),
                    layer=f"{'B' if _is_bottom_layer(item.layer) else 'F'}.Fab",
                )
            elif isinstance(item, layout_lib.FabText):
                self.builder.add_graphic_text(
                    item.text,
                    pcb.Position(
                        x=item.position.x,
                        y=item.position.y,
                        angle=item.position.angle,
                    ),
                    layer=f"{'B' if _is_bottom_layer(item.layer) else 'F'}.Fab",
                    effects=text_effects(
                        width=item.width,
                        height=item.height,
                        thickness=item.thickness,
                    ),
                )
            else:
                raise TypeError(f"Unsupported fab item: {type(item)}")

    def draw_silkscreen_lines(self):
        for item in self.schematic.layout.flatten_silk():
            self.builder.add_graphic_line(
                Point(x=item.start.x, y=item.start.y),
                Point(x=item.end.x, y=item.end.y),
                layer=f"{'B' if _is_bottom_layer(item.layer) else 'F'}.SilkS",
            )

    def add_pours(self, config: layout_lib.PourLayer):
        outline = self.schematic.layout.outline
        net_name = cmp.validate_net_name(config.net_name, owner="add_pours()")
        self.builder.add_zone(
            [
                Point(x=outline.x1, y=outline.y1),
                Point(x=outline.x2, y=outline.y1),
                Point(x=outline.x2, y=outline.y2),
                Point(x=outline.x1, y=outline.y2),
            ],
            layer=self.builder.copper_layer(config.layer).name,
            net=net_name,
        )

    def add_via(self, config: layout_lib.ViaConfig):
        net_name = cmp.validate_net_name(config.net_name, owner="add_via()")
        self.builder.add_via(
            pcb.Position(x=config.location[0], y=config.location[1]),
            size=config.hole_size,
            drill=config.drill_size,
            net=net_name,
        )

    def save(self, output_folder="./generated_outputs/", overwrite=False):
        path = pathlib.Path(output_folder) / f"{self.schematic.name}.kicad_pcb"
        constraint_errors = signal_integrity.validate_design(self.schematic)
        if constraint_errors:
            raise ValueError("; ".join(constraint_errors))
        self.convert_to_kicad(self.schematic)
        self.draw_board_outline()
        self.draw_fab_lines()
        self.draw_silkscreen_lines()
        write_to_file(self.board, path)
        save_constraints(self.schematic, output_folder)
        print(f"{'Overwrote' if overwrite else 'Wrote'} board file: {path}")
