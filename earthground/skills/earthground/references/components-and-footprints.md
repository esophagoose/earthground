# Components, library parts, and footprints

## Define a fixed component

Follow the nearest library part and use package/datasheet pin numbers exactly:

```python
import earthground.components as cmp
import earthground.footprints.tssop as tssop

class ExampleIc(cmp.Component):
    def __init__(self):
        super().__init__(refdes_prefix="U")
        self.name = "EXAMPLE_IC"
        self.mpn = "EXAMPLE-123"
        self.pins = cmp.PinContainer.from_dict(
            {"VCC": 1, "SDA": 2, "SCL": 3, "GND": 4}, self
        )
        self.footprint = tssop.Tssop(pin_count=4)  # match the actual local API
```

Confirm the footprint constructor from source rather than copying this illustrative call. Set `name`, `mpn`, semantic pins, and a pad-compatible footprint. Add aliases or protocol properties only when they reduce repeated and error-prone pin selection.

## Pin mapping

- `PinContainer.from_dict` maps logical names to physical indexes.
- Use datasheet pin numbers, including exposed-pad indexes when present.
- Footprint pad indexes and component pin indexes must correspond; KiCad export indexes `component.pins[index]` for each pad.
- Do not assume named pins are unique. Use the existing multi-pin convention for repeated ground/supply pins.
- Expose protocol buses with the shared bus named-tuple type used elsewhere in the repository, not a new lookalike class.

## Part behavior

Good abstractions turn datasheet facts into checked intent:

- `gpio(index)` converts a logical GPIO number to vendor bank/pin naming.
- Address/configuration setters validate ranges and wire strap pins.
- `generate_design` adds recommended passives and publishes semantic ports.
- `validate` detects illegal configurations, missing required wiring, or unsupported operating points.

Keep physical part facts on the component and reusable application circuitry in a generated `Design`. Search the relevant library family before choosing which layer owns behavior.

## Passives and SI values

- `Resistor(value)` accepts numeric or SI strings such as `"4.7k"`.
- `Capacitor(value, voltage)` always needs the voltage rating.
- `Inductor(value)` accepts numeric or SI strings.
- Earthground normalizes values through `SiNumber`; compare normalized values in tests rather than input spelling.
- Passives receive a footprint upon addition to a design unless one is already set. Set `package_size` on the part or `default_passive_size` on the design.

Use helpers in `standard_values.py` for E-series selection, ratios, dividers, and bounds rather than hand-rolling rounding. Confirm whether a helper returns `SiNumber`, a tuple, or scalar before composing it.

## Native and imported footprints

Earthground supports:

- Native footprints built from `footprint_types.BaseFootprint`, pad apertures, coordinates, and silk geometry.
- Imported KiCad `.kicad_mod` footprints through `earthground.importers.kicad.KicadFootprint`.

**IMPORTANT**: KiCad footprints are strongly preferred over custom footprints because they are validated already

Native pad aperture support in the KiCad exporter is currently rectangle and circle. Through-hole pads are inferred from an aperture `hole`. Imported footprints retain their geometry while pad nets, board side, reference text, and placement are remapped.

When adding a footprint:

1. Check the existing footprint family (`qfn`, `soic`, `sot`, `tssop`, headers, passives).
2. Validate allowed pin counts/dimensions and units.
3. Ensure every numbered footprint pad has a matching component pin.
4. Test bounding box, pad geometry/count, rotation, and bottom-side behavior where relevant.
5. Add or reuse manufacturer-specific footprints only when the generic geometry cannot express the package correctly.

## Library hygiene

- Use absolute `earthground.*` imports.
- Keep package `__init__.py` imports consistent with the existing family.
- Do not copy stale examples that import `common`, top-level `library`, or `earthground.library.headers`.
- Use positive/negative rail naming `P<voltage>` or `N<voltage>` with `V` as decimal, for example `P5V0`, `P3V3`, `N1V2`.
- Test the library import sweep after adding a module: `uv run pytest tests/test_library_imports.py`.

