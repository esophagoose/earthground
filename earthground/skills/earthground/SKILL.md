---
name: earthground
description: Create, modify, debug, validate, analyze, and export software-defined electronic designs with the Earthground Python package. Use for Earthground schematics, typed pins and unit-safe ratings, electrical ERC, part contracts, strap and thermal analysis, provenance and sourcing, signal-integrity constraints, hierarchical modules, footprints, PCB layout, KiCad/JLCPCB export, or changes to the Earthground repository itself.
---

# Work with Earthground

## Establish the source of truth

1. Locate the active Earthground package and read its `AGENT.md` or `AGENTS.md` files.
2. Inspect the installed/local API before writing code. Prefer, in order: current source, tests, current examples, docs. Treat snippets with `common.*`, `library.*`, `earthground.library.headers`, a `positions=` exporter argument, or `add_decoupling_cap` as potentially stale.
3. Use `uv` for environment and Python commands in the Earthground repository. Run modules with `uv run -m ...` and tests with `uv run pytest ...`.
4. Preserve the project's no-shim policy. Flag breaking changes, but do not add compatibility fallbacks unless explicitly requested.

## Choose the relevant reference

- Read [core-designs.md](references/core-designs.md) to create designs, add parts, connect pins or buses, use helpers, and validate.
- Read [hierarchy-and-modules.md](references/hierarchy-and-modules.md) before creating reusable subcircuits, ports, or nested layouts. Hierarchical net scoping and mutation are easy to misuse.
- Read [components-and-footprints.md](references/components-and-footprints.md) to define a library part, pin container, configurable reference design, or footprint.
- Read [electrical-intent-and-analysis.md](references/electrical-intent-and-analysis.md) for unit-safe ratings, typed-pin ERC, straps, contracts, thermal analysis, provenance, sourcing, and signal-integrity intent.
- Read [layout-and-export.md](references/layout-and-export.md) for placement, YAML, board geometry, KiCad project/rule generation, JLCPCB, and generated files.
- Read [debugging-and-verification.md](references/debugging-and-verification.md) when repairing code, interpreting validation/export errors, or deciding which checks to run.

Read every reference implicated by the task before editing. Search the repository for a close existing implementation and its tests; Earthground conventions are more reliable than generic EDA assumptions.

## Implement a design

1. Create `earthground.schematic.Design` and set `default_passive_size` before adding passives or modules.
2. Instantiate a library component or `generate_design(...)` module. Add each object exactly once with `add_component` or `add_module`, retaining the returned object.
3. Connect pins through the owning design. Use `join_net(pin, name)` for one pin, `connect([...], name)` for several pins, and `connect_bus([...])` only for equal named-tuple bus types.
4. Use component pin helpers or `pins.by_name(...)` where semantic names exist. Integer indexing is physical and normally one-based; do not substitute iteration position for a physical pin number.
5. Declare known rails, ambient range, external drives, strap expectations, and signal-integrity constraints before analysis. Do not invent missing datasheet or stack-up facts.
6. Add placements through `design.layout`, then set outline/layers/pours/vias/fab data as required.
7. Run report APIs first when `Unknown` results need investigation, then call `design.validate(...)` with the electrical, strap, contract, and sourcing checks appropriate to the design. These strict checks are opt-in.
8. Export to a dedicated output directory that already exists. Do not overwrite user artifacts unless requested.

## Extend the library

Follow the nearest analogous part or footprint. Encode datasheet facts as typed pin specs, `Ratings`, stable requirement/strap declarations, thermal and sourcing metadata, or signal-integrity intent instead of leaving them only in prose. Include a `source` where the API supports one. Give power nets project-standard names such as `P5V0` and `N1V2`. Add focused tests covering pin mapping, bounds and provenance, generated connectivity, analysis results, footprint pad mapping, and export behavior.

Avoid mutable component instances as default arguments in new APIs. Avoid reusing a component or generated module instance in multiple designs because placement mutates ownership state.

## Verify proportionately

- Run the narrowest affected tests first: `uv run pytest tests/test_<area>.py`.
- Run `uv run pytest` after cross-cutting schematic, component, hierarchy, layout, or exporter changes.
- Run the actual example/module or export path for user-facing generated artifacts.
- Use `uv run black --check <changed-python-paths>` for Python changes; format only files in scope.
- Report generated files, unresolved `Unknown` results, explicit waivers, and any validation options intentionally relaxed.

Do not present LTspice export as supported. Its implementation is incomplete and non-functional, and the obsolete component model field has been removed. Only touch that path when the user explicitly scopes work to repairing it.
