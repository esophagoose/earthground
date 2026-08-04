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
| Wrong physical pin mapping | Used `{name: index}` or iteration position | `from_dict` is `{physical_index: name_or_spec}`; use `by_name`/`by_index`. |
| Electrical validation omits a problem | Pin is a plain string / `UnspecifiedPinSpec`, or check was not enabled | Add evidence-backed typed specs, declare board facts, inspect `electrical_coverage()`, and opt into the check. |
| Strict analysis fails with `Unknown` | A bound, rail, placement, lifecycle, or power model is absent | Inspect the report and add real evidence; do not guess or silently convert `Unknown` to pass. |
| Open-drain input appears floating | Pull-up is absent, DNP, or not tied to a declared positive rail | Connect the resistor and declare the rail; parent pull-ups resolve through connected module ports. Negative differential open-drain lines instead require a pull-down to a non-positive rail. |
| Contract waiver has no effect | Waived the requirement ID instead of its generated aspect ID, or waived on the wrong owning design | Use the report's exact check ID and call `waive_contract` on the component's direct owner with a reason. |
| Sourcing validation rejects an ordinary part | Lifecycle defaults to `UNKNOWN` and sourcing is strict | Set a verified `cmp.Lifecycle` or leave sourcing validation off while reporting the gap. |
| Passive rejects a keyword | Legacy or misspelled free-form attribute | Use the typed constructor keyword and a dimensionally correct `ValueBounds`; migrate, do not add a permissive shim. |
| KiCad rule geometry is missing | Width/gap bounds have no typical value | Supply a stack-up-derived `typ`; impedance alone does not determine geometry. |
| Unexpected module net names | `add_module` scopes non-GND nets and mutates `short_name` | Connect through declared ports and inspect after addition. |
| VCC rails from two modules are isolated | Only GND is globally unscoped | Publish VCC as a port and connect it in the parent. |
| Imported footprint reports root `module` | Legacy KiCad 5/easyeda2kicad format | Open and resave it in a current KiCad Footprint Editor; do not change only the root token. |
| Nested refdes repeats a prefix | Wrapper and child have the same short name | This preserves both hierarchy segments; assign distinct short names if shorter refdes are required. |
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
- Standard values/typed pins/ERC: run `tests/test_standard_values.py`, `tests/test_ratings.py`, `tests/test_pins.py`, and `tests/test_electrical_validation.py` as implicated.
- Contracts, straps, and thermal: search for and run the focused analysis and CLI tests covering those APIs.
- Provenance/sourcing/passive ratings: run `tests/test_provenance_and_sourcing.py` and the library import audit.
- Signal-integrity/KiCad rules: run `tests/test_signal_integrity.py` plus `tests/test_kicad.py`.

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
- For `.kicad_pro`/`.kicad_dru`, confirm manual content survives and only Earthground-owned classes, patterns, and the marked rule block change.
- For CSV, inspect headers, designator ordering, coordinates, side, DNP policy, and whether the file is BOM or placement data.
- For visual/interactive workflows, supplement but never replace structural assertions with screenshots.

## Known code/documentation hazards

Always re-check these against current source:

- README/examples can lag renamed packages and methods.
- Exporter docstrings can describe removed arguments.
- `overwrite` may not enforce overwrite protection.
- `pcb_path` update behavior may not initialize all exporter attributes.
- Layout fields can exist without a complete export implementation.
- LTspice export is incomplete and non-functional; do not treat the module's presence as supported behavior.
- A helper's docstring may not match its return value or current name.

When a task touches one of these areas, prefer a focused regression test that expresses desired behavior rather than perpetuating the mismatch in skill-generated code.
