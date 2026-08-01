---
name: earthground
description: Create, modify, debug, validate, and export software-defined electronic designs with the Earthground Python package. Use for Earthground schematics, components and part libraries, hierarchical modules and ports, buses and nets, footprints, PCB layout and placement YAML, KiCad/JLCPCB/LTspice export, or changes to the Earthground repository itself.
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
- Read [layout-and-export.md](references/layout-and-export.md) for placement, YAML, board geometry, KiCad, JLCPCB, LTspice, and generated files.
- Read [debugging-and-verification.md](references/debugging-and-verification.md) when repairing code, interpreting validation/export errors, or deciding which checks to run.

Read every reference implicated by the task before editing. Search the repository for a close existing implementation and its tests; Earthground conventions are more reliable than generic EDA assumptions.

## Implement a design

1. Create `earthground.schematic.Design` and set `default_passive_size` before adding passives or modules.
2. Instantiate a library component or `generate_design(...)` module. Add each object exactly once with `add_component` or `add_module`, retaining the returned object.
3. Connect pins through the owning design. Use `join_net(pin, name)` for one pin, `connect([...], name)` for several pins, and `connect_bus([...])` only for equal named-tuple bus types.
4. Use component pin helpers or `pins.by_name(...)` where semantic names exist. Integer indexing is physical and one-based; never assume iteration order.
5. Add placements through `design.layout`, then set outline/layers/pours/vias/fab data as required.
6. Call `design.validate(...)` before export. Inspect or print connectivity when correctness is uncertain.
7. Export to a dedicated output directory that already exists. Do not overwrite user artifacts unless requested.

## Extend the library

Follow the nearest analogous part or footprint. Encode datasheet constraints in constructors, setters, `generate_design`, or `validate` rather than repeating them at call sites. Give power pins project-standard names such as `P5V0` and `N1V2`. Add focused tests covering pin mapping, configuration bounds, generated connectivity, footprint pad mapping, and export behavior.

Avoid mutable component instances as default arguments in new APIs. Avoid reusing a component or generated module instance in multiple designs because placement mutates ownership state.

## Verify proportionately

- Run the narrowest affected tests first: `uv run pytest tests/test_<area>.py`.
- Run `uv run pytest` after cross-cutting schematic, component, hierarchy, layout, or exporter changes.
- Run the actual example/module or export path for user-facing generated artifacts.
- Use `uv run black --check <changed-python-paths>` for Python changes; format only files in scope.
- Report generated files and any validation options intentionally relaxed.
