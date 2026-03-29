"""
Demo: LM317 regulator design with layout placement and KiCad IPC sync.

This example shows how to:
1. Generate an LM317 voltage regulator sub-design
2. Compose multiple regulator modules into a top-level design
3. Customize component placement (e.g. move a regulator to the bottom layer)
4. Export to KiCad with layout-aware positioning
5. Use the KiCad IPC interface to move footprints in a live KiCad session
   and pull the updated positions back into the source design
"""

import earthground.exporters.kicad as kicad
import earthground.layout as layout_lib
from earthground.ipc.kicad_ipc import KicadIpc
from earthground.library.integrated_circuits.voltage_regulators import lm317

# ---------------------------------------------------------------------------
# 1. Build the design
# ---------------------------------------------------------------------------
# Top-level 3.3V regulator design
design = lm317.LM317AMDTX.generate_design(3.3)
design.default_passive_size = "0805"

# Add a second 3.3V regulator as a sub-module
design.add_module(lm317.LM317AMDTX.generate_design(3.3))

# ---------------------------------------------------------------------------
# 2. Customize placement
# ---------------------------------------------------------------------------
# Create a layout and move REG1 to the bottom layer
design.layout = layout_lib.Layout(design)

reg1_placement = design.layout.placement["REG1"]
design.layout.placement["REG1"] = layout_lib.Placement(
    id=reg1_placement.id,
    position=reg1_placement.position,
    layer=layout_lib.Layer.BOTTOM,
)

# ---------------------------------------------------------------------------
# 3. Export to KiCad
# ---------------------------------------------------------------------------
kicad.KicadExporter(design).save()
print("Board exported. Open the .kicad_pcb file in KiCad to see the layout.")
print(f"REG1 is on the {design.layout.placement['REG1'].layer.value} layer.")

# ---------------------------------------------------------------------------
# 4. (Optional) Live IPC sync with KiCad
# ---------------------------------------------------------------------------
# Uncomment the block below when KiCad 9+ is running with the API server
# enabled (Preferences > Plugins > Enable KiCad API).
#
# ipc = KicadIpc(design)
#
# # Move U1 to a new position in the live KiCad editor
# update = ipc.move("REG1", x_mm=30.0, y_mm=20.0, angle_deg=0)
# print(f"Moved {update.refdes}: {update.old} -> {update.new}")
#
# # Pull all positions from KiCad back into the design
# positions = ipc.pull_positions()
# for refdes, pos in positions.items():
#     print(f"  {refdes}: ({pos.x_mm:.2f}, {pos.y_mm:.2f}) {pos.angle_deg}° on {pos.layer}")
#
# # The positions are now stored on each component's parameters:
# for comp in design.components.values():
#     if "_position" in comp.parameters:
#         print(f"  {comp.refdes} source position: {comp.parameters['_position']}")


if __name__ == "__main__":
    pass  # The script runs on import; this is here for clarity.
