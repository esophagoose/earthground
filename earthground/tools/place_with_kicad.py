#!/usr/bin/env python3
"""
Interactive placement tool: run a design script, open KiCad, and write a
YAML placement file as the user arranges footprints.

Usage:
    place_with_kicad <script.py> [--output placements.yaml]
                                 [--poll-interval 1.0]
"""

import argparse
import dataclasses
import importlib.util
import math
import pathlib
import platform
import subprocess
import sys
import time
from collections.abc import Mapping

import yaml

import earthground.components as cmp
import earthground.exporters.kicad as kicad_exporter
import earthground.layout as layout_lib
import earthground.schematic as sch_lib


@dataclasses.dataclass(frozen=True)
class ModulePlacementSpec:
    refdes: str
    description: str
    child_layouts: dict[str, layout_lib.ComponentLayout]


@dataclasses.dataclass
class PlaceWithKicad:
    script_path: pathlib.Path
    yaml_path: pathlib.Path | None = None
    poll_interval: float = 1.0
    no_open: bool = False
    design: sch_lib.Design | None = dataclasses.field(default=None, init=False)
    descriptions: dict[str, str] = dataclasses.field(default_factory=dict, init=False)
    pcb_path: pathlib.Path | None = dataclasses.field(default=None, init=False)
    module_specs: dict[str, ModulePlacementSpec] = dataclasses.field(default_factory=dict, init=False)
    module_child_refdes: set[str] = dataclasses.field(default_factory=set, init=False)
    child_to_module: dict[str, str] = dataclasses.field(default_factory=dict, init=False)

    def __post_init__(self):
        self.script_path = pathlib.Path(self.script_path).resolve()
        if self.yaml_path is None:
            self.yaml_path = self.script_path.with_suffix(".yaml")
        else:
            self.yaml_path = pathlib.Path(self.yaml_path).resolve()

    @staticmethod
    def load_design_from_script(script_path: str | pathlib.Path) -> sch_lib.Design:
        path = pathlib.Path(script_path).resolve()
        if not path.exists():
            sys.exit(f"Error: script not found: {path}")

        spec = importlib.util.spec_from_file_location("_user_design", str(path))
        module = importlib.util.module_from_spec(spec)

        sys.path.insert(0, str(path.parent))
        spec.loader.exec_module(module)

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

    @staticmethod
    def build_description_map(design: sch_lib.Design) -> dict[str, str]:
        descriptions = {}

        def walk(current_design: sch_lib.Design, prefix: str = ""):
            for cid, component in current_design.components.items():
                refdes = f"{prefix}{cid}"
                if isinstance(component, cmp.ModuleComponent):
                    descriptions[refdes] = component.parent.name
                    walk(component.parent, prefix=f"{refdes}_")
                elif not component.virtual:
                    descriptions[refdes] = getattr(component, "description", "") or component.name

        walk(design)
        return descriptions

    @staticmethod
    def open_kicad(pcb_path: pathlib.Path):
        system = platform.system()
        if system == "Darwin":
            subprocess.Popen(["open", str(pcb_path)])
        elif system == "Windows":
            subprocess.Popen(["start", "", str(pcb_path)], shell=True)
        else:
            subprocess.Popen(["pcbnew", str(pcb_path)])

    @staticmethod
    def connect_ipc(design: sch_lib.Design, retries: int = 30, delay: float = 2.0):
        from earthground.ipc.kicad_ipc import KicadIpc

        for attempt in range(1, retries + 1):
            try:
                return KicadIpc(design)
            except Exception:
                if attempt == retries:
                    sys.exit(
                        "Error: could not connect to KiCad API. "
                        "Make sure KiCad is running with the API enabled "
                        "(Preferences > Plugins > Enable KiCad API)."
                    )
                print(f"  Waiting for KiCad API... (attempt {attempt}/{retries})")
                time.sleep(delay)

    @staticmethod
    def layer_name(layer_str: str) -> str:
        if "B." in layer_str or "Back" in layer_str:
            return "BOTTOM"
        return "TOP"

    @staticmethod
    def round_to_right_angle(angle: float) -> float:
        return float((round(angle / 90.0) * 90) % 360)

    @staticmethod
    def angle_error(actual: float, expected: float) -> float:
        return abs(((actual - expected + 180) % 360) - 180)

    @staticmethod
    def rotate_point(x: float, y: float, angle: float) -> tuple[float, float]:
        radians = math.radians(angle)
        cos_a = math.cos(radians)
        sin_a = math.sin(radians)
        return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)

    @staticmethod
    def build_module_specs(design: sch_lib.Design) -> dict[str, ModulePlacementSpec]:
        specs = {}
        for refdes, component in design.components.items():
            if not isinstance(component, cmp.ModuleComponent):
                continue
            child_layouts = {}
            for child_refdes, (component_layout, _child_component) in component.parent.layout.flatten().items():
                child_layouts[f"{refdes}_{child_refdes}"] = component_layout
            specs[refdes] = ModulePlacementSpec(
                refdes=refdes,
                description=component.parent.name,
                child_layouts=child_layouts,
            )
        return specs

    @staticmethod
    def build_module_metadata(
        design: sch_lib.Design,
    ) -> tuple[dict[str, ModulePlacementSpec], set[str], dict[str, str]]:
        module_specs = PlaceWithKicad.build_module_specs(design)
        module_child_refdes = {
            child_refdes
            for spec in module_specs.values()
            for child_refdes in spec.child_layouts
        }
        child_to_module = {
            child_refdes: module_refdes
            for module_refdes, spec in module_specs.items()
            for child_refdes in spec.child_layouts
        }
        return module_specs, module_child_refdes, child_to_module

    @classmethod
    def infer_module_yaml_entry(
        cls,
        spec: ModulePlacementSpec,
        positions: dict,
        *,
        preferred_child_refdes: str | None = None,
    ) -> dict:
        if not spec.child_layouts:
            raise ValueError(f"Module {spec.refdes} has no child footprints to infer placement from")

        child_refdes = preferred_child_refdes
        if child_refdes is None or child_refdes not in spec.child_layouts:
            child_refdes = next(iter(spec.child_layouts))
        if child_refdes not in positions:
            raise ValueError(f"Module {spec.refdes} is missing child footprint {child_refdes}")

        component_layout = spec.child_layouts[child_refdes]
        current = positions[child_refdes]
        inferred_rotation = cls.round_to_right_angle(
            current.angle_deg - component_layout.component.angle
        )
        if cls.angle_error(
            current.angle_deg,
            component_layout.component.angle + inferred_rotation,
        ) > 0.2:
            raise ValueError(
                f"Module {spec.refdes} child {child_refdes} rotation is not a rigid 90-degree transform"
            )

        local_layer = "BOTTOM" if component_layout.layer == layout_lib.Layer.BOTTOM else "TOP"
        current_layer = cls.layer_name(current.layer)
        inferred_layer = "TOP" if current_layer == local_layer else "BOTTOM"

        rotated_x, rotated_y = cls.rotate_point(
            component_layout.component.x,
            component_layout.component.y,
            inferred_rotation,
        )
        translation = (current.x_mm - rotated_x, current.y_mm - rotated_y)

        return {
            "description": spec.description,
            "layer": inferred_layer,
            "x": round(translation[0], 3),
            "y": round(translation[1], 3),
            "rotation": round(inferred_rotation, 1),
        }

    @classmethod
    def positions_to_yaml_dict(
        cls,
        positions: dict,
        descriptions: dict[str, str],
        *,
        design: sch_lib.Design | None = None,
        module_specs: dict[str, ModulePlacementSpec] | None = None,
        module_child_refdes: set[str] | None = None,
        preferred_children_by_module: dict[str, str] | None = None,
    ) -> dict:
        if design is not None:
            return cls.module_positions_to_yaml_dict(
                positions,
                descriptions,
                design=design,
                module_specs=module_specs,
                module_child_refdes=module_child_refdes,
                preferred_children_by_module=preferred_children_by_module,
            )

        result = {}
        for refdes in sorted(positions):
            result[refdes] = cls.position_to_yaml_entry(refdes, positions[refdes], descriptions)
        return result

    @classmethod
    def module_positions_to_yaml_dict(
        cls,
        positions: dict,
        descriptions: dict[str, str],
        *,
        design: sch_lib.Design,
        module_specs: dict[str, ModulePlacementSpec] | None = None,
        module_child_refdes: set[str] | None = None,
        preferred_children_by_module: dict[str, str] | None = None,
    ) -> dict:
        result = {}
        if module_specs is None or module_child_refdes is None:
            module_specs, module_child_refdes, _child_to_module = cls.build_module_metadata(design)

        for refdes in sorted(positions):
            if refdes in module_child_refdes:
                continue
            result[refdes] = cls.position_to_yaml_entry(refdes, positions[refdes], descriptions)

        for refdes in sorted(module_specs):
            result[refdes] = cls.infer_module_yaml_entry(
                module_specs[refdes],
                positions,
                preferred_child_refdes=None if preferred_children_by_module is None else preferred_children_by_module.get(refdes),
            )
        return result

    @classmethod
    def changed_yaml_keys(
        cls,
        changed_refs: list[str],
        *,
        design: sch_lib.Design | None = None,
        child_to_module: dict[str, str] | None = None,
    ) -> set[str]:
        if child_to_module is None:
            if design is None:
                raise ValueError("design or child_to_module is required")
            _module_specs, _module_child_refdes, child_to_module = cls.build_module_metadata(design)

        return {child_to_module.get(refdes, refdes) for refdes in changed_refs}

    @staticmethod
    def preferred_children_by_module(
        changed_refs: list[str],
        *,
        child_to_module: dict[str, str],
    ) -> dict[str, str]:
        preferred = {}
        for refdes in changed_refs:
            module_refdes = child_to_module.get(refdes)
            if module_refdes is not None and module_refdes not in preferred:
                preferred[module_refdes] = refdes
        return preferred

    @classmethod
    def position_to_yaml_entry(cls, refdes: str, pos, descriptions: dict[str, str]) -> dict:
        return {
            "description": descriptions.get(refdes, ""),
            "layer": cls.layer_name(pos.layer),
            "x": round(pos.x_mm, 3),
            "y": round(pos.y_mm, 3),
            "rotation": round(pos.angle_deg, 1),
        }

    @staticmethod
    def write_yaml(yaml_path: pathlib.Path, data: dict):
        with open(yaml_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    @staticmethod
    def read_yaml(yaml_path: pathlib.Path) -> dict:
        if not yaml_path.exists():
            return {}
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, Mapping):
            raise ValueError(f"Expected top-level mapping in {yaml_path}")
        return dict(data)

    @staticmethod
    def merge_yaml_changes(existing_data: dict, snapshot_data: dict, changed_keys: set[str]) -> dict:
        merged = dict(existing_data)
        for refdes in sorted(changed_keys):
            if refdes in snapshot_data:
                merged[refdes] = snapshot_data[refdes]
        return merged

    @classmethod
    def prune_module_child_entries(
        cls,
        data: dict,
        *,
        design: sch_lib.Design | None = None,
        module_child_refdes: set[str] | None = None,
    ) -> dict:
        if module_child_refdes is None:
            if design is None:
                raise ValueError("design or module_child_refdes is required")
            _module_specs, module_child_refdes, _child_to_module = cls.build_module_metadata(design)
        return {
            refdes: value
            for refdes, value in data.items()
            if refdes not in module_child_refdes
        }

    @staticmethod
    def position_changed(old_pos, new_pos) -> bool:
        return (
            abs(old_pos.x_mm - new_pos.x_mm) > 0.001
            or abs(old_pos.y_mm - new_pos.y_mm) > 0.001
            or abs(old_pos.angle_deg - new_pos.angle_deg) > 0.05
            or old_pos.layer != new_pos.layer
        )

    @classmethod
    def changed_refs(cls, old: dict, new: dict) -> list[str]:
        changed = []
        for refdes in new:
            if refdes not in old or cls.position_changed(old[refdes], new[refdes]):
                changed.append(refdes)
        return changed

    @classmethod
    def positions_changed(cls, old: dict, new: dict) -> bool:
        if set(old.keys()) != set(new.keys()):
            return True
        for refdes in old:
            if cls.position_changed(old[refdes], new[refdes]):
                return True
        return False

    def load_design(self) -> sch_lib.Design:
        print(f"Loading design from {self.script_path}...")
        self.design = self.load_design_from_script(self.script_path)
        self.descriptions = self.build_description_map(self.design)
        self.module_specs, self.module_child_refdes, self.child_to_module = self.build_module_metadata(
            self.design
        )
        print(f"  Design: {self.design.name}")
        print(f"  Components: {len(self.descriptions)}")
        return self.design

    def export_board(self) -> pathlib.Path:
        if self.design is None:
            raise ValueError("design must be loaded before exporting the board")
        pcb_dir = self.script_path.parent
        kicad_exporter.KicadExporter(self.design).save(output_folder=str(pcb_dir))
        self.pcb_path = pcb_dir / f"{self.design.name}.kicad_pcb"
        return self.pcb_path

    def poll_loop(self, ipc):
        if self.design is None:
            raise ValueError("design must be loaded before polling")

        last_positions = {}
        yaml_data = self.prune_module_child_entries(
            self.read_yaml(self.yaml_path),
            module_child_refdes=self.module_child_refdes,
        )
        print(f"\nPolling KiCad for placement changes (every {self.poll_interval}s)...")
        print(f"YAML output: {self.yaml_path}")
        print("Press Ctrl-C to stop.\n")

        try:
            while True:
                try:
                    current = ipc.get_all_positions()
                except Exception as exc:
                    print(f"  IPC error: {exc} — retrying...")
                    time.sleep(self.poll_interval)
                    try:
                        ipc.refresh_board()
                    except Exception:
                        pass
                    continue

                if self.positions_changed(last_positions, current):
                    changed = self.changed_refs(last_positions, current)

                    if last_positions:
                        try:
                            preferred_children_by_module = self.preferred_children_by_module(
                                changed,
                                child_to_module=self.child_to_module,
                            )
                            snapshot_data = self.positions_to_yaml_dict(
                                current,
                                self.descriptions,
                                design=self.design,
                                module_specs=self.module_specs,
                                module_child_refdes=self.module_child_refdes,
                                preferred_children_by_module=preferred_children_by_module,
                            )
                        except ValueError as exc:
                            print(f"  Placement validation failed: {exc}")
                            time.sleep(self.poll_interval)
                            continue
                        changed_keys = self.changed_yaml_keys(
                            changed,
                            child_to_module=self.child_to_module,
                        )
                        yaml_data = self.merge_yaml_changes(yaml_data, snapshot_data, changed_keys)
                        yaml_data = self.prune_module_child_entries(
                            yaml_data,
                            module_child_refdes=self.module_child_refdes,
                        )
                        self.write_yaml(self.yaml_path, yaml_data)

                        for ref in changed:
                            p = current[ref]
                            print(
                                f"  {ref}: ({p.x_mm:.2f}, {p.y_mm:.2f}) "
                                f"{p.angle_deg:.0f}° {self.layer_name(p.layer)}"
                            )
                    else:
                        print(f"  Initial snapshot: {len(current)} footprints")

                    last_positions = current

                time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            if yaml_data:
                self.write_yaml(self.yaml_path, yaml_data)
            print(f"\nSaved final placements to {self.yaml_path}")

    def run(self):
        design = self.load_design()
        pcb_path = self.export_board()

        if not self.no_open:
            print(f"Opening KiCad with {pcb_path}...")
            self.open_kicad(pcb_path)

        print("Connecting to KiCad API...")
        ipc = self.connect_ipc(design)
        print("  Connected!")
        self.poll_loop(ipc)


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

    PlaceWithKicad(
        script_path=pathlib.Path(args.script),
        yaml_path=pathlib.Path(args.output) if args.output else None,
        poll_interval=args.poll_interval,
        no_open=args.no_open,
    ).run()


if __name__ == "__main__":
    main()
