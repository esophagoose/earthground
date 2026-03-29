"""
Mounting hole components for PCB mechanical mounting

Standard mounting holes for M2, M2.5, M3, M4, etc. screws
"""

import pygerber.aperture as ap_lib

import earthground.components as cmp
import earthground.footprint_types as ft


class MountingHoleFootprint(ft.BaseFootprint):
    """
    Generic mounting hole footprint

    Args:
        screw_size: Screw size (e.g., "M3" for 3mm)
        hole_diameter: Hole diameter in mm (clearance hole for screw)
        pad_diameter: Pad diameter in mm (typically 2x hole diameter)
    """

    def __init__(self, screw_size: str, hole_diameter: float, pad_diameter: float):
        super().__init__()
        self.name = f"MountingHole_{screw_size}"
        self.description = f"Mounting hole for {screw_size} screw, {hole_diameter}mm hole, {pad_diameter}mm pad"

        # Create circular pad with hole
        aperture = ap_lib.ApertureCircle(diameter=pad_diameter, hole=hole_diameter)

        # Single pad at origin
        self.pads = {1: ft.Pad(location=[0, 0], aperture=aperture)}


class M3(cmp.Component):
    """
    M3 Mounting Hole

    Standard mounting hole for M3 screws:
    - Hole diameter: 3.2mm (clearance for M3 screw)
    - Pad diameter: 6.4mm (2x hole diameter for good mechanical support)

    Can be connected to GND for grounding or left floating.
    """

    def __init__(self):
        super().__init__(refdes_prefix="MH")
        self.name = "M3_MountingHole"
        self.detailed_description = "Mounting hole for M3 screw, 3.2mm hole, 6.4mm pad"
        self.manufacturer = "Generic"
        self.mpn = "M3_MOUNTING_HOLE"
        self.description = "MOUNTING HOLE M3"

        self.parameters = {
            "Screw Size": "M3",
            "Hole Diameter": "3.2mm",
            "Pad Diameter": "6.4mm",
            "Type": "Through-hole",
            "Purpose": "Mechanical mounting",
        }

        # Single pin for potential grounding connection
        self.pins = cmp.PinContainer.from_dict({1: "MT1"}, self)

        self.footprint = MountingHoleFootprint(
            screw_size="M3", hole_diameter=3.2, pad_diameter=6.4
        )
