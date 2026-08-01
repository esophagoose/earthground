"""Merge Earthground signal-integrity declarations into KiCad project files."""

from __future__ import annotations

import json
import pathlib
from decimal import Decimal

import earthground.signal_integrity as si

BEGIN_MARKER = "# BEGIN EARTHGROUND GENERATED RULES"
END_MARKER = "# END EARTHGROUND GENERATED RULES"


def _mm(value: Decimal) -> str:
    return f"{format(value * Decimal(1000), 'f')}mm"


def _mm_float(value: Decimal) -> float:
    return float(value * Decimal(1000))


def _default_class() -> dict:
    return {
        "bus_width": 12,
        "clearance": 0.2,
        "diff_pair_gap": 0.25,
        "diff_pair_via_gap": 0.25,
        "diff_pair_width": 0.2,
        "line_style": 0,
        "microvia_diameter": 0.3,
        "microvia_drill": 0.1,
        "name": "Default",
        "pcb_color": "rgba(0, 0, 0, 0.000)",
        "priority": 2147483647,
        "schematic_color": "rgba(0, 0, 0, 0.000)",
        "track_width": 0.2,
        "tuning_profile": "",
        "via_diameter": 0.6,
        "via_drill": 0.3,
        "wire_width": 6,
    }


def _project_document(path: pathlib.Path) -> dict:
    if path.is_file():
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError(f"KiCad project must contain a JSON object: {path}")
        return document
    return {
        "meta": {"filename": path.name, "version": 3},
        "net_settings": {
            "classes": [_default_class()],
            "meta": {"version": 5},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [],
        },
    }


def _merged_project(path: pathlib.Path, classes: tuple[si.NetClass, ...]) -> dict:
    document = _project_document(path)
    settings = document.setdefault("net_settings", {})
    existing = settings.setdefault("classes", [])
    default = next(
        (item for item in existing if item.get("name") == "Default"),
        _default_class(),
    )
    if not any(item.get("name") == "Default" for item in existing):
        existing.insert(0, dict(default))
    by_name = {item.get("name"): item for item in existing}
    declared_names = {item.name for item in classes}
    for index, declaration in enumerate(classes):
        current = by_name.get(declaration.name)
        if current is None:
            current = dict(default)
            current["name"] = declaration.name
            current["priority"] = index
            existing.append(current)
        updates = {
            "clearance": declaration.clearance,
            "track_width": declaration.track_width,
            "diff_pair_width": declaration.diff_pair_width,
            "diff_pair_gap": declaration.diff_pair_gap,
        }
        for key, bounds in updates.items():
            if bounds is not None:
                current[key] = _mm_float(bounds.typ)

    patterns = settings.setdefault("netclass_patterns", []) or []
    patterns = [
        pattern for pattern in patterns if pattern.get("netclass") not in declared_names
    ]
    for declaration in classes:
        patterns.extend(
            {"netclass": declaration.name, "pattern": net} for net in declaration.nets
        )
    settings["netclass_patterns"] = patterns
    settings.setdefault("meta", {"version": 5})
    settings.setdefault("net_colors", None)
    settings.setdefault("netclass_assignments", None)
    return document


def _bounds_arguments(bounds, *, minimum=True, optimum=True, maximum=True) -> str:
    arguments = []
    if minimum and bounds.min is not None:
        arguments.append(f"(min {_mm(bounds.min)})")
    if optimum and bounds.typ is not None:
        arguments.append(f"(opt {_mm(bounds.typ)})")
    if maximum and bounds.max is not None:
        arguments.append(f"(max {_mm(bounds.max)})")
    return " ".join(arguments)


def _rule(name: str, condition: str, constraint: str) -> str:
    return "\n".join(
        (
            f'(rule "{name}"',
            f'  (condition "{condition}")',
            f"  (constraint {constraint}))",
        )
    )


def _generated_rules(
    classes: tuple[si.NetClass, ...], pairs: tuple[si.DiffPair, ...]
) -> str:
    rules = []
    for declaration in classes:
        condition = f"A.hasNetclass('{declaration.name}')"
        fields = (
            ("clearance", declaration.clearance, True, False, False),
            ("track width", declaration.track_width, True, True, True),
            ("differential gap", declaration.diff_pair_gap, True, True, True),
        )
        constraints = (
            "clearance",
            "track_width",
            "diff_pair_gap",
        )
        for (label, bounds, use_min, use_opt, use_max), constraint in zip(
            fields, constraints
        ):
            if bounds is None:
                continue
            arguments = _bounds_arguments(
                bounds, minimum=use_min, optimum=use_opt, maximum=use_max
            )
            rules.append(
                _rule(
                    f"Earthground {declaration.name} {label}",
                    condition,
                    f"{constraint} {arguments}",
                )
            )
        if declaration.z_single is not None:
            rules.append(
                f"# {declaration.name} single-ended impedance intent: {declaration.z_single}"
            )
    for pair in pairs:
        positive, negative = pair.nets
        condition = f"A.NetName == '{positive}' || A.NetName == '{negative}'"
        label = f"{positive}-{negative}"
        declaration = next(item for item in classes if item.name == pair.net_class)
        if declaration.diff_pair_width is not None:
            rules.append(
                _rule(
                    f"Earthground {label} differential width",
                    condition,
                    "track_width " + _bounds_arguments(declaration.diff_pair_width),
                )
            )
        if pair.z_diff is not None:
            rules.append(f"# {label} differential impedance intent: {pair.z_diff}")
        if pair.intra_pair_skew is not None:
            rules.append(
                _rule(
                    f"Earthground {label} skew",
                    condition,
                    f"skew (max {_mm(pair.intra_pair_skew.max)})",
                )
            )
        if pair.max_length is not None:
            rules.append(
                _rule(
                    f"Earthground {label} length",
                    condition,
                    f"length (max {_mm(pair.max_length.max)})",
                )
            )
        if pair.max_vias is not None:
            rules.append(
                _rule(
                    f"Earthground {label} vias",
                    condition,
                    f"via_count (max {pair.max_vias})",
                )
            )
        if pair.min_track_angle_deg is not None:
            rules.append(
                _rule(
                    f"Earthground {label} bend angle",
                    condition,
                    f"track_angle (min {pair.min_track_angle_deg}deg)",
                )
            )
    body = "\n\n".join(rules)
    return f"{BEGIN_MARKER}\n{body}\n{END_MARKER}"


def _merge_rules(path: pathlib.Path, generated: str) -> str:
    if not path.is_file():
        return f"(version 1)\n\n{generated}\n"
    current = path.read_text(encoding="utf-8")
    if BEGIN_MARKER in current and END_MARKER in current:
        before, remainder = current.split(BEGIN_MARKER, 1)
        _, after = remainder.split(END_MARKER, 1)
        return before.rstrip() + "\n\n" + generated + after
    return current.rstrip() + "\n\n" + generated + "\n"


def save_constraints(design, output_folder) -> tuple[pathlib.Path, pathlib.Path] | None:
    classes = tuple(design._net_classes.values())
    pairs = tuple(design._diff_pairs)
    if not classes and not pairs:
        return None
    errors = si.validate_design(design)
    if errors:
        raise ValueError("; ".join(errors))
    folder = pathlib.Path(output_folder)
    project_path = folder / f"{design.name}.kicad_pro"
    rules_path = folder / f"{design.name}.kicad_dru"
    document = _merged_project(project_path, classes)
    project_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    rules_path.write_text(
        _merge_rules(rules_path, _generated_rules(classes, pairs)),
        encoding="utf-8",
    )
    return project_path, rules_path
