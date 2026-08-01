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

An omitted placement makes the component float into deterministic fallback placement with a warning. This is convenient for early export, not production board layout.

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

Do not pass the old `positions=` argument shown in some README versions. Populate `design.layout.placement` instead. `save` writes `<design.name>.kicad_pcb`; ensure the directory exists. Despite its name, `overwrite` currently affects the printed verb only, so perform an explicit existence check before calling `save` when preserving files matters.

Constructing with `pcb_path=` loads a board, but inspect the current constructor carefully before relying on update-in-place behavior: state initialization differs from the new-board branch.

Bottom-side export mirrors geometry, swaps F/B layer names, mirrors reference justification, and negates footprint angle. Cover imported and native footprints in tests when changing it.

## JLCPCB

`earthground.exporters.jlcpcb.JlcPcb(design).generate_bom(...)` currently writes a placement/position CSV despite the method/filename using “bom”. It flattens module layouts and negates Y. Current code emits `top` for all parts, so do not claim correct bottom-side output without implementing and testing it.

The output directory must exist. DNP filtering and a procurement BOM are not inherent in this path; inspect current exporter behavior for the requested artifact.

## LTspice

```python
from earthground.exporters.ltspice import LTspiceExporter

content = LTspiceExporter(design).export()       # return string
LTspiceExporter(design).export("circuit.asc")   # write file
```

Resistors and capacitors have explicit symbol mappings. Other parts need compatible symbol/model attributes or fall back to class names. Treat the exporter as schematic approximation and inspect generated `.asc` content in tests.

## Interactive KiCad placement

Repository tools include `place_with_kicad` and `get_kicad_layout`. These depend on KiCad/IPC and local application state. Read their current CLI and tests before invocation. Do not launch or modify an interactive KiCad session merely to answer or diagnose unless the user asks for that workflow.
