# Layout and export

## Programmatic placement

```python
import earthground.layout as layout

design.layout.placement["U1"] = layout.Placement(
    position=layout.Position(x=25.0, y=40.0, angle=90.0),
    id=layout.Orientation.TOP,
    layer=layout.Layer.TOP,
)
design.layout.outline = BoundingBox(x1=0, y1=0, x2=60, y2=40)
```

Placement keys are design component-map refdes values, not necessarily `component.refdes`. Rotations are degrees. `Position.rotate` only accepts multiples of 90, although raw placement models accept floats.

An omitted placement makes the component float into deterministic fallback placement with a warning. This is convenient for early export, not production board layout. Analysis retains those coordinates as fallback provenance but does not use them to pass placement-dependent checks. Construct `KicadExporter(..., strict_placement=True)` to reject every fallback placement; use `Placement.identity()` when a module is intentionally anchored at its parent origin.

Reference-text orientation is an edge (`TOP`, `BOTTOM`, `LEFT`, `RIGHT`, `CENTER`), not text rotation. The code computes its offset based on footprint bounds and component rotation.

## Placement YAML

```yaml
U1:
  description: optional and ignored
  layer: TOP
  x: 25.0
  y: 40.0
  rotation: 90.0
R1:
  layer: BOTTOM
  x: 12.5
  y: 15.0
  rotation: 0
```

Load with `design.layout.load_placements_from_yaml(path)`. Required fields are `x`, `y`, and `rotation`; layer defaults to `TOP`, is case-normalized, and must be `TOP` or `BOTTOM`. Extra fields are ignored. YAML loading replaces the entire placement map.

For a module, place its virtual module refdes in the parent and its physical parts inside the child design layout. See the hierarchy reference for transform composition.

## Board configuration

- `outline`: `BoundingBox(x1, y1, x2, y2)`; the KiCad exporter emits a rectangular Edge.Cuts item.
- `layer_count`: defaults to 2; extra layers become internal copper layers.
- `pours`: `PourLayer(net_name, layer)` uses a one-based layer index into the generated copper-layer map and fills the board rectangle.
- `vias`: `ViaConfig(location, net_name, hole_size, drill_size)`; the net must exist in exported nets.
- `fab`: `FabLine` or `FabText` items.

Check source and tests before using traces; the layout stores them, but the current KiCad conversion path may not export every stored layout feature.

## KiCad

Current construction is:

```python
exporter = earthground.exporters.kicad.KicadExporter(design)
exporter.save(output_folder="generated_outputs", overwrite=False)
```

Do not pass the old `positions=` argument shown in some README versions. Populate `design.layout.placement` instead. `save` always writes `<design.name>.kicad_pcb`; ensure the directory exists. When signal-integrity net classes or differential pairs are declared, it also merges `<design.name>.kicad_pro` net classes and updates an Earthground-marked block in `<design.name>.kicad_dru`. Unrelated project settings, manual net classes, and rules outside that marked block are preserved. Despite its name, `overwrite` currently affects the printed verb only, so perform an explicit existence check before calling `save` when preserving files matters.

Net-class geometry is exported from typical values; min/max constraints become generated rules where supported. Differential skew, maximum length/via count, and minimum track angle become rules. Impedance values are emitted as intent/comments, not converted into trace width or gap. Never guess geometry without a board stack-up calculation.

KiCad footprints include hidden metadata properties for MPN, manufacturer, datasheet URL/revision/SHA256, lifecycle, and each `Distributor:<name>` ID. Keep this data on the component so board/BOM consumers receive it.

Constructing with `pcb_path=` loads a board, but inspect the current constructor carefully before relying on update-in-place behavior: state initialization differs from the new-board branch.

Bottom-side export mirrors geometry, swaps F/B layer names, mirrors reference justification, and negates footprint angle. Cover imported and native footprints in tests when changing it.

## JLCPCB

`earthground.exporters.jlcpcb.JlcPcb(design).generate_bom(...)` currently writes a placement/position CSV despite the method/filename using “bom”. It flattens module layouts and negates Y. Current code emits `top` for all parts, so do not claim correct bottom-side output without implementing and testing it.

The output directory must exist. DNP filtering and a procurement BOM are not inherent in this path; inspect current exporter behavior for the requested artifact.

## LTspice is unsupported

Do not use or recommend the LTspice exporter for production or analysis. Its implementation is incomplete and non-functional, and `Component.ltspice_model` was removed because nothing consumed it. If a task explicitly asks to repair LTspice support, begin by defining supported output semantics and regression fixtures; do not document the current code path as working.

## Interactive KiCad placement

Repository tools include `place_with_kicad` and `get_kicad_layout`. These depend on KiCad/IPC and local application state. Read their current CLI and tests before invocation. Do not launch or modify an interactive KiCad session merely to answer or diagnose unless the user asks for that workflow.
