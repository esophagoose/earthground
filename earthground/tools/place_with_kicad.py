#!/usr/bin/env python3
"""
Interactive placement tool: run a design script, open KiCad, and write a
YAML placement file as the user arranges footprints.

Usage:
    python -m earthground.tools.place_with_kicad <script.py> [--output placements.yaml]
                                                              [--poll-interval 1.0]

The script must produce an ``earthground.schematic.Design`` object.  The tool
finds it by looking for a module-level variable named ``design`` (or
``schematic``), or—if neither exists—the first Design instance in the
module namespace.

Flow:
    1. Execute the user's script to obtain a Design.
    2. Export a .kicad_pcb next to the script.
    3. Open KiCad with that board file.
    4. Wait for KiCad's IPC API to become available.
    5. Poll footprint positions; whenever something moves, update the YAML.
    6. On Ctrl-C, write a final snapshot and exit.
"""

import argparse
import importlib.util
import pathlib
import platform
import subprocess
import sys
import time

import yaml

import earthground.exporters.kicad as kicad_exporter
import earthground.schematic as sch_lib


# ------------------------------------------------------------------
# 1. Load the Design from a user script
# ------------------------------------------------------------------

def _load_design_from_script(script_path: str) -> sch_lib.Design:
    """Execute a Python script and return the Design it creates."""
    path = pathlib.Path(script_path).resolve()
    if not path.exists():
        sys.exit(f"Error: script not found: {path}")

    spec = importlib.util.spec_from_file_location("_user_design", str(path))
    module = importlib.util.module_from_spec(spec)

    # Make sure imports inside the user script work relative to its location
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(module)

    # Look for well-known names first, then fall back to first Design found
    for name in ("design", "schematic"):
        obj = getattr(module, name, None)
        if isinstance(obj, sch_lib.Design):
            return obj

    for obj in vars(module).values():
        if isinstance(obj, sch_lib.Design):
            return obj

    sys.exit(
        "Error: could not find a Design object in the script. "
        "Define a module-level variable named 'design' or 'schematic'."
    )


# ------------------------------------------------------------------
# 2. Build a refdes → description map for the YAML
# ------------------------------------------------------------------

def _build_description_map(design: sch_lib.Design) -> dict:
    descriptions = {}
    for module in design.modules + [design]:
        for component in module.components.values():
            if not component.virtual:
                desc = getattr(component, "description", "") or component.name
                descriptions[component.refdes] = desc
    return descriptions


# ------------------------------------------------------------------
# 3. Open KiCad
# ------------------------------------------------------------------

def _open_kicad(pcb_path: pathlib.Path):
    """Launch KiCad's PCB editor with the board file."""
    system = platform.system()
    if system == "Darwin":
        # macOS: use 'open -a' so it works even if kicad isn't on PATH
        subprocess.Popen(["open", "-a", "KiCad", str(pcb_path)])
    elif system == "Windows":
        # Windows: use start
        subprocess.Popen(["start", "", str(pcb_path)], shell=True)
    else:
        # Linux: try pcbnew directly
        subprocess.Popen(["pcbnew", str(pcb_path)])


# ------------------------------------------------------------------
# 4. Connect to KiCad with retries
# ------------------------------------------------------------------

def _connect_ipc(design: sch_lib.Design, retries: int = 30, delay: float = 2.0):
    """Try to connect to KiCad's IPC API, retrying until it's available."""
    from earthground.ipc.kicad_ipc import KicadIpc

    for attempt in range(1, retries + 1):
        try:
            ipc = KicadIpc(design)
            return ipc
        except Exception:
            if attempt == retries:
                sys.exit(
                    "Error: could not connect to KiCad API. "
                    "Make sure KiCad is running with the API enabled "
                    "(Preferences > Plugins > Enable KiCad API)."
                )
            print(f"  Waiting for KiCad API... (attempt {attempt}/{retries})")
            time.sleep(delay)


# ------------------------------------------------------------------
# 5. YAML writing
# ------------------------------------------------------------------

def _layer_name(layer_str: str) -> str:
    """Convert KiCad layer string to simple TOP/BOTTOM."""
    if "B." in layer_str or "Back" in layer_str:
        return "BOTTOM"
    return "TOP"


def _positions_to_yaml_dict(positions: dict, descriptions: dict) -> dict:
    """Convert FootprintPosition map to YAML-serializable dict."""
    result = {}
    for refdes in sorted(positions):
        pos = positions[refdes]
        result[refdes] = {
            "description": descriptions.get(refdes, ""),
            "layer": _layer_name(pos.layer),
            "x": round(pos.x_mm, 3),
            "y": round(pos.y_mm, 3),
            "rotation": round(pos.angle_deg, 1),
        }
    return result


def _write_yaml(yaml_path: pathlib.Path, data: dict):
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


# ------------------------------------------------------------------
# 6. Poll loop
# ------------------------------------------------------------------

def _positions_changed(old: dict, new: dict) -> bool:
    """Return True if any footprint moved since the last snapshot."""
    if set(old.keys()) != set(new.keys()):
        return True
    for refdes in old:
        o, n = old[refdes], new[refdes]
        if (abs(o.x_mm - n.x_mm) > 0.001
                or abs(o.y_mm - n.y_mm) > 0.001
                or abs(o.angle_deg - n.angle_deg) > 0.05
                or o.layer != n.layer):
            return True
    return False


def _poll_loop(ipc, yaml_path: pathlib.Path, descriptions: dict,
               interval: float = 1.0):
    """Poll KiCad for position changes and update the YAML file."""
    last_positions = {}
    print(f"\nPolling KiCad for placement changes (every {interval}s)...")
    print(f"YAML output: {yaml_path}")
    print("Press Ctrl-C to stop.\n")

    try:
        while True:
            try:
                current = ipc.get_all_positions()
            except Exception as exc:
                print(f"  IPC error: {exc} — retrying...")
                time.sleep(interval)
                try:
                    ipc.refresh_board()
                except Exception:
                    pass
                continue

            if _positions_changed(last_positions, current):
                changed = []
                for ref in current:
                    if ref not in last_positions:
                        changed.append(ref)
                    else:
                        o, n = last_positions[ref], current[ref]
                        if (abs(o.x_mm - n.x_mm) > 0.001
                                or abs(o.y_mm - n.y_mm) > 0.001
                                or abs(o.angle_deg - n.angle_deg) > 0.05
                                or o.layer != n.layer):
                            changed.append(ref)

                yaml_data = _positions_to_yaml_dict(current, descriptions)
                _write_yaml(yaml_path, yaml_data)

                if last_positions:
                    for ref in changed:
                        p = current[ref]
                        print(f"  {ref}: ({p.x_mm:.2f}, {p.y_mm:.2f}) "
                              f"{p.angle_deg:.0f}° {_layer_name(p.layer)}")
                else:
                    print(f"  Initial snapshot: {len(current)} footprints")

                last_positions = current

            time.sleep(interval)

    except KeyboardInterrupt:
        # Final write
        if last_positions:
            yaml_data = _positions_to_yaml_dict(last_positions, descriptions)
            _write_yaml(yaml_path, yaml_data)
        print(f"\nSaved final placements to {yaml_path}")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Run an earthground design script, open KiCad, and "
                    "write a YAML placement file as you arrange footprints.",
    )
    parser.add_argument(
        "script",
        help="Path to a Python script that creates a Design object.",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output YAML path (default: <script_name>.yaml next to the script).",
    )
    parser.add_argument(
        "--poll-interval", "-p",
        type=float,
        default=1.0,
        help="Seconds between position polls (default: 1.0).",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Don't open KiCad automatically (assume it's already running).",
    )
    args = parser.parse_args()

    # 1. Load design
    print(f"Loading design from {args.script}...")
    design = _load_design_from_script(args.script)
    print(f"  Design: {design.name}")

    descriptions = _build_description_map(design)
    print(f"  Components: {len(descriptions)}")

    # 2. Export board
    script_path = pathlib.Path(args.script).resolve()
    pcb_dir = script_path.parent
    kicad_exporter.KicadExporter(design).save(output_folder=str(pcb_dir))
    pcb_path = pcb_dir / f"{design.name}.kicad_pcb"

    # 3. Determine YAML output path
    if args.output:
        yaml_path = pathlib.Path(args.output).resolve()
    else:
        yaml_path = script_path.with_suffix(".yaml")

    # 4. Open KiCad
    if not args.no_open:
        print(f"Opening KiCad with {pcb_path}...")
        _open_kicad(pcb_path)

    # 5. Connect to KiCad IPC
    print("Connecting to KiCad API...")
    ipc = _connect_ipc(design)
    print("  Connected!")

    # 6. Poll and write YAML
    _poll_loop(ipc, yaml_path, descriptions, interval=args.poll_interval)


if __name__ == "__main__":
    main()
