"""
LTspice exporter for converting Design schematics to .asc format.
"""

import logging
import math
from typing import Dict, List, Optional, Tuple

import earthground.components as cmp
import earthground.schematic as sch

NEW_SECTION_COMMANDS = ["SYMATTR", "TEXT"]
log = logging.getLogger(__name__)


class LTspiceExporter:
    """Exports a Design schematic to LTspice .asc format."""

    # Component type to LTspice symbol mapping
    SYMBOL_MAP = {
        cmp.Resistor: "Res",
        cmp.Capacitor: "Cap",
    }

    # Grid spacing for component placement
    GRID_X = 80
    GRID_Y = 80
    START_X = 160
    START_Y = 400

    def __init__(self, design: sch.Design):
        """
        Initialize the LTspice exporter.

        :param design: The schematic design to export.
        :type design: sch.Design
        """
        self.design = design
        self.lines: List[str] = []
        self.component_positions: Dict[cmp.Component, Tuple[int, int]] = {}
        self.pin_positions: Dict[cmp.Pin, Tuple[int, int]] = {}
        self.net_segments: Dict[str, List[Tuple[int, int]]] = {}

    def export(self, filename: Optional[str] = None) -> str:
        """
        Export the design to LTspice .asc format.

        :param filename: Optional filename to write to. If None, returns the content as string.
        :type filename: Optional[str]
        :return: The .asc file content as a string.
        :rtype: str
        """
        self.lines = []
        self.component_positions = {}
        self.pin_positions = {}
        self.net_segments = {}

        self._write_header()
        self._place_components()
        self._draw_wires()
        self._write_flags()
        self._write_symbols()

        content = "\n".join(self.lines)
        if filename:
            with open(filename, "w") as f:
                f.write(content)
            log.info("Exported LTspice schematic to %s", filename)
        return content

    def _write_header(self):
        """Write the LTspice file header."""
        self.lines.append("Version 4")
        self.lines.append("SHEET 1 880 680")

    def _place_components(self):
        """Place components on a grid and store their positions."""
        components = [c for c in self.design.components.values() if not c.virtual]
        # Also include components from modules
        for module in self.design.modules:
            components.extend([c for c in module.components.values() if not c.virtual])

        for idx, component in enumerate(components):
            x = self.START_X + (idx % 4) * self.GRID_X
            y = self.START_Y + (idx // 4) * self.GRID_Y
            self.component_positions[component] = (x, y)

            # Place pins around the component
            pin_count = len(component.pins)
            if pin_count == 2:
                # For 2-pin components, place pins on left and right
                # Pins are indexed starting from 1
                try:
                    pin1 = component.pins[1]
                    pin2 = component.pins[2]
                    self.pin_positions[pin1] = (x - 32, y)
                    self.pin_positions[pin2] = (x + 32, y)
                except (ValueError, KeyError):
                    # Fallback: use first two pins from iterator
                    pins_list = list(component.pins)
                    if len(pins_list) >= 2:
                        self.pin_positions[pins_list[0]] = (x - 32, y)
                        self.pin_positions[pins_list[1]] = (x + 32, y)
            else:
                # For multi-pin components, arrange pins in a circle
                radius = 40
                pins_list = list(component.pins)
                for i, pin in enumerate(pins_list):
                    angle = 2 * math.pi * i / pin_count
                    pin_x = int(x + radius * math.cos(angle))
                    pin_y = int(y + radius * math.sin(angle))
                    self.pin_positions[pin] = (pin_x, pin_y)

    def _get_symbol_name(self, component: cmp.Component) -> str:
        """Get the LTspice symbol name for a component."""
        comp_type = type(component)
        if comp_type in self.SYMBOL_MAP:
            return self.SYMBOL_MAP[comp_type]
        # For other components, try to use the component name
        # or default to a generic symbol
        if hasattr(component, "ltspice_symbol"):
            return component.ltspice_symbol
        # Default fallback - use component type name
        return comp_type.__name__

    def _get_component_value(self, component: cmp.Component) -> Optional[str]:
        """Get the value string for a component."""
        if isinstance(component, cmp.Resistor):
            # Format: "1k" or "10µ" etc.
            value_str = str(component.value)
            # Remove unit suffix for LTspice (it uses standard units)
            if value_str.endswith("Ω"):
                return value_str[:-1]
            return value_str
        elif isinstance(component, cmp.Capacitor):
            value_str = str(component.value)
            # LTspice uses µ for micro, u for micro in some contexts
            # Format: "10µ" or "1u" etc.
            if value_str.endswith("F"):
                return value_str[:-1]
            return value_str
        return None

    def _draw_wires(self):
        """Generate WIRE commands for all net connections."""
        # Build net segments - use pin_to_net mapping for accurate connections
        processed_wires = set()

        def add_wire_if_new(pos1, pos2):
            """Add wire only if not already processed."""
            wire_key = tuple(sorted([pos1, pos2]))
            if wire_key in processed_wires:
                return
            processed_wires.add(wire_key)
            self._add_wire(pos1, pos2)

        # Process nets from design
        for net_name, net in self.design.nets.items():
            if net_name == "GND":
                continue  # Ground is handled separately with FLAG
            pins = list(net.connections)
            if len(pins) < 2:
                continue

            # Get positions for all pins in this net
            pin_positions = []
            for pin in pins:
                if pin in self.pin_positions:
                    pin_positions.append(self.pin_positions[pin])

            if len(pin_positions) < 2:
                continue

            # Create a star topology: connect first pin to all others
            start_pos = pin_positions[0]
            for end_pos in pin_positions[1:]:
                add_wire_if_new(start_pos, end_pos)

        # Also handle nets from modules
        for module in self.design.modules:
            for net_name, net in module.nets.items():
                if "GND" in net_name or net_name.startswith("_"):
                    continue
                pins = list(net.connections)
                if len(pins) < 2:
                    continue

                pin_positions = []
                for pin in pins:
                    if pin in self.pin_positions:
                        pin_positions.append(self.pin_positions[pin])

                if len(pin_positions) < 2:
                    continue

                start_pos = pin_positions[0]
                for end_pos in pin_positions[1:]:
                    add_wire_if_new(start_pos, end_pos)

    def _add_wire(self, pos1: Tuple[int, int], pos2: Tuple[int, int]):
        """Add a WIRE command between two positions."""
        x1, y1 = pos1
        x2, y2 = pos2
        # Simple routing: horizontal then vertical (L-shaped)
        if x1 != x2 and y1 != y2:
            # Create L-shaped wire: horizontal first, then vertical
            self.lines.append(f"WIRE {x1} {y1} {x2} {y1}")
            self.lines.append(f"WIRE {x2} {y1} {x2} {y2}")
        elif x1 != x2:
            # Horizontal wire
            self.lines.append(f"WIRE {x1} {y1} {x2} {y2}")
        elif y1 != y2:
            # Vertical wire
            self.lines.append(f"WIRE {x1} {y1} {x2} {y2}")

    def _write_flags(self):
        """Write FLAG commands for ground nets."""
        # Find all pins connected to ground
        ground_net = self.design.nets.get("GND")
        if ground_net:
            for pin in ground_net.connections:
                if pin in self.pin_positions:
                    x, y = self.pin_positions[pin]
                    self.lines.append(f"FLAG {x} {y} 0")

        # Also check modules
        for module in self.design.modules:
            for net_name, net in module.nets.items():
                if "GND" in net_name:
                    for pin in net.connections:
                        if pin in self.pin_positions:
                            x, y = self.pin_positions[pin]
                            self.lines.append(f"FLAG {x} {y} 0")

    def _write_symbols(self):
        """Write SYMBOL commands for all components."""
        components = [c for c in self.design.components.values() if not c.virtual]
        for module in self.design.modules:
            components.extend([c for c in module.components.values() if not c.virtual])

        for component in components:
            if component not in self.component_positions:
                continue

            x, y = self.component_positions[component]
            symbol_name = self._get_symbol_name(component)
            rotation = "R0"  # Default rotation

            # Determine rotation based on pin positions for 2-pin components
            if len(component.pins) == 2:
                pin1 = None
                pin2 = None
                try:
                    pin1 = component.pins[1]
                    pin2 = component.pins[2]
                except (ValueError, KeyError):
                    pins_list = list(component.pins)
                    if len(pins_list) >= 2:
                        pin1 = pins_list[0]
                        pin2 = pins_list[1]

                if pin1 and pin2:
                    pin1_pos = self.pin_positions.get(pin1)
                    pin2_pos = self.pin_positions.get(pin2)
                    if pin1_pos and pin2_pos:
                        if pin1_pos[0] < pin2_pos[0]:
                            rotation = "R0"  # Horizontal, pin1 left
                        else:
                            rotation = "R180"  # Horizontal, reversed
                        if abs(pin1_pos[1] - pin2_pos[1]) > abs(
                            pin1_pos[0] - pin2_pos[0]
                        ):
                            # Vertical orientation
                            if pin1_pos[1] < pin2_pos[1]:
                                rotation = "R90"
                            else:
                                rotation = "R270"

            self.lines.append(f"SYMBOL {symbol_name} {x} {y} {rotation}")

            # Add WINDOW commands for certain component types (like resistors)
            if isinstance(component, (cmp.Resistor, cmp.Capacitor)):
                self.lines.append("WINDOW 0 0 56 Bottom 2")
                self.lines.append("WINDOW 3 32 56 Top 2")

            # Write instance name
            self.lines.append(f"SYMATTR InstName {component.refdes}")

            # Write value if applicable
            value = self._get_component_value(component)
            if value:
                self.lines.append(f"SYMATTR Value {value}")

    def _write_attributes(self):
        """Write additional attributes (currently handled in _write_symbols)."""
        # Attributes are now written together with symbols for better organization


def export_to_ltspice(design: sch.Design, filename: str) -> str:
    """
    Convenience function to export a design to LTspice format.

    :param design: The schematic design to export.
    :type design: sch.Design
    :param filename: The output filename.
    :type filename: str
    :return: The .asc file content as a string.
    :rtype: str
    """
    exporter = LTspiceExporter(design)
    return exporter.export(filename)
