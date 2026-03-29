import csv
import pathlib
import re
from typing import Literal

import earthground.schematic as sch_lib

LayerName = Literal["top", "bottom"]

COLUMN_NAMES = ["Designator", "Mid X", "Mid Y", "Rotation", "Layer"]


class JlcPcb:
    """Export component placement for JLCPCB from an earthground design.
    It generates a CSV in with the following columns:
    ```
    Designator,Mid X,Mid Y,Rotation,Layer
    ```
    """

    def __init__(self, design: sch_lib.Design):
        self.design = design

    def generate_bom(
        self,
        output_folder: str = "./generated_outputs/",
        filename: str | None = None,
    ) -> pathlib.Path:
        """Save a JLCPCB-compatible position file for the design.

        Args:
            output_folder: Folder to place the CSV into.
            filename: Optional filename; if omitted, uses
                      `<design.name>_bom.csv`.

        Returns:
            Path to the written CSV file.
        """
        if filename is None:
            safe_name = self.design.name.replace("/", "_")
            filename = f"{safe_name}_bom.csv"
        out_path = pathlib.Path(output_folder) / filename

        with out_path.open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(COLUMN_NAMES)

            # Get flattened layout - this includes all components with their positions
            # already transformed for module components
            flattened_layout = self.design.layout.flatten()

            footprints_data = []

            # Process all components from flattened layout
            for cid, (layout, component) in flattened_layout.items():
                # Skip virtual components (like port symbols)
                if component.virtual:
                    continue

                # Get layout position
                if layout is not None:
                    pos = layout.component
                    x = pos.x
                    y = pos.y
                    angle = pos.angle
                else:
                    # Default position if not in layout
                    x = 0.0
                    y = 0.0
                    angle = 0.0

                # KiCad uses Y increasing downward, but JLCPCB expects Y increasing upward
                # Negate Y to match the golden file format
                y_negated = -y

                # Default to top layer (can be enhanced later to detect from footprint)
                layer = "top"

                # Use cid as designator (includes module prefix for module components)
                footprints_data.append(
                    [cid, f"{x:.6f}", f"{y_negated:.6f}", f"{angle:.6f}", layer]
                )

            # Sort by designator using natural sort (numbers sorted numerically)
            # This matches the golden file order: C2 comes before C10
            def natural_sort_key(designator: str) -> tuple:
                # Split designator into prefix (letters) and number parts
                # e.g., "C2" -> ("C", 2), "R10" -> ("R", 10)
                # Handle module components like "REG1_R1" by splitting on underscore
                parts = designator.split("_", 1)
                if len(parts) == 2:
                    # Module component: use the module prefix and component part
                    module_prefix, comp_part = parts
                    match = re.match(r"([A-Za-z]+)(\d+)", comp_part)
                    if match:
                        prefix, num = match.groups()
                        return (module_prefix, prefix, int(num))
                    return (module_prefix, comp_part, 0)
                else:
                    # Regular component
                    match = re.match(r"([A-Za-z]+)(\d+)", designator)
                    if match:
                        prefix, num = match.groups()
                        return (prefix, int(num))
                    # Fallback for non-standard designators
                    return (designator, 0)

            footprints_data.sort(key=lambda row: natural_sort_key(row[0]))

            # Write sorted rows
            for row in footprints_data:
                writer.writerow(row)
        print(f"Generated BOM: {out_path}")
        return out_path
