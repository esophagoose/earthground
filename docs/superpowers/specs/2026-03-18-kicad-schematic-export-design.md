# KiCad Schematic Export Design

## Goal

Add a KiCad schematic exporter for `earthground.schematic.Design` that produces a valid hierarchical KiCad schematic file set, reuses KiCad's built-in passive symbols, generates embedded symbols for non-passive components, and preserves `Design.modules` as child schematic pages.

## Requirements And Decisions

- Export a root `earthground.schematic.Design` to a root `kiutils.schematic.Schematic`.
- Write one child `.kicad_sch` file per module instance in `Design.modules`.
- Represent module instances in the parent page as `kiutils.items.schitems.HierarchicalSheet`.
- Represent module ports in the child page as `HierarchicalLabel` records and in the parent page as matching `HierarchicalPin` records.
- Reuse KiCad built-in library symbols `device:R`, `device:C`, and `device:L` for standard passives.
- Generate embedded `kiutils.symbol.Symbol` records for non-passive components.
- Reuse `earthground/exporters/schematic_generation/symbols/pin_sort.py` for pin-side assignment.
- Use a hybrid net rendering policy:
  - direct wires for simple local point-to-point nets
  - short wire stubs plus `LocalLabel` for multi-drop or awkward local nets
  - built-in KiCad power symbols for recognized power and ground rails
- Draw every emitted wire segment orthogonally. When a routed connection needs bends, use a horizontal-then-vertical-then-horizontal dogleg with the vertical trunk placed at the X midpoint between endpoints.
- Prefer built-in KiCad power symbols only when the net name maps cleanly to a known power symbol. Otherwise fall back to labeled stubs.
- Keep the public conversion boundary in `kicad_schematic.py`; use a separate helper/writer to emit the full file set.

## Proposed File Structure

- `earthground/exporters/schematic_generation/kicad_schematic.py`
  Orchestrates conversion of a root `Design` into the root `kiutils.schematic.Schematic`, recursively builds child page schematics, and assembles page metadata required for writing the hierarchy.
- `earthground/exporters/schematic_generation/symbols/kicad_symbol.py`
  Converts one `earthground.components.Component` into either a built-in KiCad library reference for passives or an embedded `kiutils.symbol.Symbol` for non-passives.
- `earthground/exporters/schematic_generation/autoplace.py`
  Produces deterministic placement for symbols, hierarchical sheets, labels, and sheet pins.
- `earthground/exporters/schematic_generation/writer.py`
  Assigns deterministic file names and writes the full hierarchy of `.kicad_sch` files to disk.
- `earthground/exporters/schematic_generation/models.py`
  Holds internal dataclasses for page context, symbol references, layout results, filenames, and hierarchy metadata.
- `earthground/exporters/schematic_generation/power_symbols.py`
  Maps known power and ground net names to built-in KiCad power library identifiers and placement helpers.

The exact support-file split may vary slightly during implementation, but the boundaries above should be preserved: symbol generation stays separate from hierarchy orchestration and separate from placement heuristics.

## Architecture

### Root Export Orchestrator

`kicad_schematic.py` is responsible for the recursive traversal of the `Design` tree.

For each design page it must:

- create a page context containing page UUID, page number, output filename, and sheet-instance path
- convert local non-virtual components into placed KiCad symbols
- recursively export every module instance into a child page context
- place a `HierarchicalSheet` for every child module in the parent page
- emit local connectivity for normal nets and parent-side sheet connectivity for module ports
- attach all per-page symbol and sheet instance metadata required by KiCad

The primary public API should return the root-page `kiutils.schematic.Schematic`. A secondary helper should expose the generated child schematics and write the complete hierarchy to disk.

### Symbol Generation

`symbols/kicad_symbol.py` should expose a small API that answers two questions for a component:

- what library identifier should the placed schematic symbol use
- does this component require an embedded `kiutils.symbol.Symbol`

Rules:

- `Resistor`, `Capacitor`, and `Inductor` use `device:R`, `device:C`, and `device:L`
- all other components produce an embedded symbol under an `earthground` library nickname
- embedded symbol pin positions should be derived from `PinHierarchy.side_groups()`
- symbol body dimensions should remain deterministic and based on pin count and pin-name lengths

The generated symbols should be reusable within one page export when multiple components share the same symbol shape contract, but correctness is more important than deduplication in the first version.

### Placement

`autoplace.py` should provide deterministic placement primitives for:

- local components on a page
- hierarchical sheet rectangles on a page
- sheet pins along sheet edges
- labels, power symbols, and wire stubs

The initial heuristic should prioritize readability and determinism over compactness. A top-to-bottom page flow is acceptable for v1, as long as:

- repeated exports produce the same coordinates
- symbols do not overlap
- sheet rectangles have stable sizes and pin order
- direct-wire routing stays simple enough to avoid self-intersections in common cases
- all drawn wires remain orthogonal, using a shared midpoint dogleg rule for bent connections

## Data Flow

### Per-Page Conversion

For each `Design`, export should follow this sequence:

1. Create a page context with filename, UUID, page number, instance path, and a fresh `kiutils.schematic.Schematic`.
2. Convert local non-virtual components to placed KiCad symbols.
3. Recursively export each module instance into its own child page context.
4. Place one `HierarchicalSheet` in the parent page for each child module instance.
5. Emit connectivity for local nets, sheet pins, and child-page hierarchical labels.
6. Finalize `sheetInstances`, `symbolInstances`, local `libSymbols`, and page metadata.

### Component Conversion

For each entry in `design.components.values()`:

- skip virtual components that exist only to model ports or internal structure
- skip module port symbols as ordinary components because they are represented by hierarchical sheets instead
- place standard passives using built-in KiCad library symbols
- place non-passive components using generated embedded symbols
- emit `Reference`, `Value`, `Footprint`, and `Datasheet` properties on the placed `SchematicSymbol`

### Module Conversion

For each module in `design.modules`:

- recursively build a child page schematic
- assign a deterministic child filename derived from the module instance path or scoped `short_name`
- create a parent-page `HierarchicalSheet`
- set sheet name from the module name or stable instance label
- set sheet file to the generated child filename
- add one `HierarchicalPin` for each exported module port
- add child-page `HierarchicalLabel` entries with matching names

This aligns the exporter with KiCad's hierarchical contract: the child page defines hierarchical labels and the parent page exposes matching sheet pins.

## Connectivity Policy

### Local Nets

Use the hybrid connectivity policy selected during design review:

- For simple two-pin nets on the same page, prefer direct wires.
- For multi-drop nets or awkward routes, prefer short wire stubs plus `LocalLabel` with the shared net name.
- If a direct-wire attempt would require complex routing, degrade to labeled stubs instead of failing export.
- Every actual wire that is drawn must use orthogonal segments only.
- The default bend rule for routed connections is horizontal-then-vertical-then-horizontal, with the vertical segment at the X midpoint between the two endpoints.

The first version does not need a general-purpose schematic router. It only needs deterministic, readable output for common designs.

### Cross-Sheet Nets

Cross-sheet connectivity must use hierarchical constructs only:

- `HierarchicalPin` on the parent sheet symbol
- matching `HierarchicalLabel` in the child schematic page

Do not use `GlobalLabel` as the default mechanism for module-to-parent connections.

### Power And Ground Nets

Power-like nets should use built-in KiCad power symbols when the net name maps cleanly to a known symbol.

Examples include:

- `GND`
- common positive rails such as `VCC`, `VDD`, `VIN`, `VBUS`, `VBAT`, and `VSYS`

The existing `pin_sort.PinHierarchy` power and ground classification should guide which pins and nets are treated as power-oriented.

If a net is power-like but no clear built-in KiCad power symbol exists, the exporter should fall back to the local labeled-stub strategy rather than generating a custom power symbol in v1.

### Naming Constraints

The exporter must avoid assigning multiple different labels to the same net segment on one page because KiCad will flag that as an ERC problem. Net naming must be stable and deterministic across repeated exports.

## Output Model

### Public API

`kicad_schematic.py` should provide:

- a function that converts a root `Design` into the root `kiutils.schematic.Schematic`
- a helper that returns or stores the full set of child page schematics
- a writer entry point that emits the full hierarchy of `.kicad_sch` files

The main conversion API remains root-schematic-first, as requested during design review.

### File Set

Export should produce:

- one root `.kicad_sch`
- one child `.kicad_sch` per module instance

Filenames must be deterministic and collision-safe. Repeated module instances should not share a child file. The generated file set should not depend on traversal order beyond the stable order already present in the `Design`.

## Error Handling

The exporter should fail fast on structural problems that would make the file set invalid:

- unsupported non-passive symbol generation
- duplicate or conflicting hierarchical port names in one sheet
- missing filename assignment for a child sheet
- inconsistent page-instance metadata
- impossible pin-placement state caused by exporter logic bugs

The exporter should not fail on layout inconvenience alone. When routing becomes awkward, it should fall back from direct wires to labeled stubs.

## Testing Strategy

### Symbol Tests

Add tests that verify:

- passives resolve to built-in `device:R`, `device:C`, and `device:L`
- non-passive components generate embedded symbols
- embedded symbol pins preserve expected numbers, names, and left/right placement derived from `PinHierarchy`

### Placement Tests

Add tests that verify:

- autoplace is deterministic
- components do not overlap in simple page examples
- hierarchical sheets receive stable size and position
- sheet pins are placed along the correct sheet edge in a deterministic order

### Schematic Export Tests

Add tests that verify:

- a single-page design exports valid local symbols and connectivity
- a hierarchical design exports one child page per module instance
- parent pages contain `HierarchicalSheet` records with matching `HierarchicalPin` entries
- child pages contain matching `HierarchicalLabel` entries for exported ports
- simple two-pin nets use direct wires
- multi-drop or awkward nets use labeled stubs
- recognized power and ground rails use built-in power symbols

### Writer Tests

Add tests that verify:

- the writer emits the full file set
- parent sheet file references point to the expected generated child filenames
- repeated exports produce stable filenames and stable page linkage

## Out Of Scope For V1

- custom generated power symbols
- full automatic schematic routing for arbitrary net topologies
- shared child-sheet file reuse across repeated module instances
- importing or synchronizing against an existing KiCad schematic project

## Implementation Notes

- Reuse the existing SVG exporter pin-layout logic where it is already correct rather than duplicating pin classification rules.
- Keep compatibility with `kiutils==1.4.8`, which is already declared in the project.
- Preserve deterministic ordering anywhere the source model uses dictionaries or sets by sorting where necessary during export.
- Avoid changing the semantics of `earthground.schematic.Design` unless implementation exposes a concrete mismatch that cannot be handled inside the exporter.
