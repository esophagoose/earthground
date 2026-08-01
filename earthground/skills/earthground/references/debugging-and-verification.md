# Debugging and verification

## Diagnose from the owning layer

1. Reproduce with the narrowest test or a minimal `Design`.
2. Inspect the exact source method and its closest tests.
3. Print `design.components`, `design.nets`, and `design.pin_to_net` identities when connectivity is surprising.
4. For hierarchy, inspect the module both before and after `add_module`, then inspect `layout.flatten()` or schematic `flatten(...)` output.
5. For exporter bugs, distinguish schematic connectivity, layout flattening, footprint conversion, and file serialization before patching.

## Frequent AI mistakes

| Symptom | Likely cause | Corrective action |
|---|---|---|
| Import error for `common` or `library` | Copied stale docs | Use absolute `earthground.*` imports and verify with import tests. |
| Component already in design | Reused the same mutable instance | Construct a fresh component/module for every placement. |
| Capacitor constructor error | Voltage argument omitted | Pass both value and voltage rating. |
| Pin lookup changes between runs | Iterated the frozenset-backed pin container | Use `by_name`, `by_index`, or explicit indexes. |
| Unexpected module net names | `add_module` scopes non-GND nets and mutates `short_name` | Connect through declared ports and inspect after addition. |
| VCC rails from two modules are isolated | Only GND is globally unscoped | Publish VCC as a port and connect it in the parent. |
| Missing footprint at validation/export | Part lacks footprint or invalid passive size | Set a footprint/package size; do not hide it with validation flags. |
| Placement not applied | Used `component.refdes` instead of design map key | Capture the key from `design.components` or known insertion refdes. |
| Exporter rejects `positions=` | README API is stale | Populate `design.layout.placement`. |
| Output write fails | Export directory does not exist | Create a narrow, explicit output directory first. |
| Wrong JLCPCB bottom layer | Current exporter hardcodes `top` | Implement layer mapping with a regression test or report limitation. |
| Bus assertion | Bus objects have different named-tuple types | Use the shared protocol bus type and matching fields. |

## Validation matrix

Choose checks based on the change:

- Design script: run the script/module, `design.validate`, and inspect the requested export.
- Component/library part: test constructor metadata, every pin mapping, helpers/config bounds, validator, and library import.
- Generated module: test defaults, each meaningful option, port connectivity, support passives, and multiple instances in one parent.
- Footprint: test pad count/indexes, dimensions/bounds, aperture/hole, rotation, and KiCad conversion.
- Hierarchy: run `tests/test_module_net_names.py`, layout flattening tests, and an exporter test.
- Layout/YAML: run `tests/test_layout_yaml.py`, bottom-layer tests when relevant, and parse the emitted board.
- KiCad exporter: run focused schematic/PCB exporter tests plus `tests/test_kicad.py`.
- Standard values: test boundary/tie cases and normalized SI results.

Repository commands:

```bash
uv run pytest tests/test_components.py
uv run pytest tests/test_module_net_names.py tests/test_layout_yaml.py
uv run pytest
uv run black --check earthground/path.py tests/test_path.py
```

Use `uv run pytest -k <term>` for narrow iteration. Do not format the whole repository when unrelated user changes are present.

## Review generated artifacts

- Confirm the file exists at the expected path and parse it when a parser is available.
- Check refdes, pad-to-net mappings, module prefixes, footprint sides/angles, and board outline.
- For CSV, inspect headers, designator ordering, coordinates, side, DNP policy, and whether the file is BOM or placement data.
- For visual/interactive workflows, supplement but never replace structural assertions with screenshots.

## Known code/documentation hazards

Always re-check these against current source:

- README/examples can lag renamed packages and methods.
- Exporter docstrings can describe removed arguments.
- `overwrite` may not enforce overwrite protection.
- `pcb_path` update behavior may not initialize all exporter attributes.
- Layout fields can exist without a complete export implementation.
- A helper's docstring may not match its return value or current name.

When a task touches one of these areas, prefer a focused regression test that expresses desired behavior rather than perpetuating the mismatch in skill-generated code.
