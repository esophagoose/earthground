# Migrating an Earthground 0.5 project to 0.9

Migrate incrementally: first restore the existing design on 0.9, then add typed
intent and enable strict checks in reviewable batches. Legacy string pin
declarations remain supported, and the new checks are opt-in.

## 1. Preserve a baseline

Before changing dependencies, run the existing tests and save known-good
connectivity, KiCad, BOM, and placement artifacts. Search for likely migration
points:

```bash
rg -n "kiutils|pykicad|ltspice_model|lead_time|\.nets\[|pin_to_net\[|KicadExporter" .
```

Do not overwrite a known-good board during the first 0.9 export.

## 2. Upgrade the environment

Earthground 0.9 requires Python newer than 3.10. For an index dependency, pin
the migration to the 0.9 line:

```toml
[project]
requires-python = ">3.10"
dependencies = ["earthground>=0.9,<0.10"]
```

For a local or Git checkout, use a source override rather than a version range:

```toml
[project]
dependencies = ["earthground"]

[tool.uv.sources]
earthground = { path = "../earthground", editable = true }
```

Refresh and verify the environment:

```bash
uv lock
uv sync
uv run python3 -c "from importlib.metadata import version; print(version('earthground'))"
```

Earthground uses `python-kicad`, imported as `pykicad`, and the separate
`kicad-python`, imported as `kipy`. Do not remove `kicad-python`; the obsolete
distribution is the one literally named `pykicad` on PyPI. If a partial install
causes `cannot import name 'BoardSide' from 'pykicad'`, repair it with:

```bash
uv sync --reinstall-package python-kicad
```

## 3. Restore construction and footprints

Use package-qualified imports:

```python
import earthground.components as cmp
import earthground.schematic as sch
import earthground.standard_values as sv
```

`design.nets` and `design.pin_to_net` are read-only. Use `add_net`, `join_net`,
`connect`, `change_net_name`, and `merge_nets` instead of direct mutation.
Physical pin maps remain index-to-name/spec mappings:

```python
self.pins = cmp.PinContainer.from_dict({1: "VCC", 2: "IRQ", 3: "GND"}, self)
```

Use `pins.by_index(1)` for physical package pins and `pins.by_name("VCC")` for
semantic roles. Create a fresh component or module for every placement.

Imported footprints must use modern `.kicad_mod` syntax. KiCad 5 and some
easyeda2kicad files start with `(module ...)`, producing:

```text
Unsupported KiCad document root 'module'. Supported roots: export, footprint,
kicad_pcb, kicad_sch.
```

Open and resave these files in a current KiCad Footprint Editor. Replacing only
the root token does not convert legacy pad and layer syntax.

Verify every component pin maps to a footprint pad, including exposed and shell
pads:

```python
component_indexes = {str(pin.index) for pin in component.pins}
footprint_indexes = {str(index) for index in component.footprint.pads}
assert not component_indexes - footprint_indexes
```

Review footprint-only mechanical pads separately rather than inventing
electrical pin numbers for them.

Passives now reject unknown keyword attributes. Use typed fields and unit-safe
bounds:

```python
cmp.Resistor(
    "10k",
    tolerance=sv.ratio(min=-0.01, typ=0, max=0.01),
    power_rating=sv.watts(max=0.125),
    package_size="0603",
)
cmp.Capacitor("100n", "16V", dielectric="X7R", package_size="0603")
```

## 4. Configure and compile

Generate KiCad configuration with:

```bash
uv run earthground kicad catalog generate
```

A new configuration contains this stub:

```yaml
project:
  design_class: null
```

Set it to one zero-argument `Design` subclass:

```yaml
project:
  design_class: my_project.designs:MainBoard
```

`earthground compile` intentionally selects one design. In a multi-board
repository, export each design file separately:

```bash
uv run earthground export kicad designs/controller.py
uv run earthground export kicad designs/sensor.py
```

Relative paths in `.earthground/config.yaml` resolve from the project root—the
directory containing `.earthground`. For example:

```yaml
lcsc:
  db: toolchain/jlcdb/jlcpcb_db.sqlite3
```

Do not prefix that value with the project directory name; doing so duplicates
the directory during resolution.

## 5. Add typed electrical intent

Migrate one component family at a time to `DigitalPinSpec`, `AnalogPinSpec`,
`PowerPinSpec`, `PassivePinSpec`, and `NoConnectPinSpec`. Plain string pins do
not supply ERC evidence.

Declare board facts before checking:

```python
design.declare_rail("P3V3", sv.volts(3.1, typ=3.3, max=3.5))
design.declare_external_drive("UART_RX", sv.volts(0, max=3.3))
report = design.check_electrical()
```

ERC resolves physical nets across the module hierarchy. Board rail declarations
and parent pull resistors are visible through connected module ports. Conflicting
declarations on one resolved net produce `Unknown`.

Declared internal pull-ups and pull-downs satisfy floating-input checks.
Ordinary open-drain and positive differential lines require a resistor pull-up
to a positive rail. Negative differential open-drain lines require a pull-down
to a non-positive rail.

## 6. Contracts, hierarchy, and export

Required-external contracts resolve through module boundaries. Placement checks
compose explicitly placed parent modules and child components. Unrelated
unplaced support parts do not erase known local distance evidence.

Flattened refdes preserve every hierarchy segment. Adjacent modules with the
same short name can intentionally produce a refdes such as
`LINK1_LINK1_C1`. Choose distinct short names when shorter output is desired;
do not strip a repeated segment because it represents a real module boundary.

Export to a comparison directory first and verify refdes, pad-to-net mappings,
geometry, placement, side, and rotation before replacing a board.

`save_constraints` updates `.kicad_pro` and `.kicad_dru` only when at least one
net class or differential pair is declared. With no constraints it returns
without writing either file.

## Completion checklist

- Existing tests pass on Earthground 0.9.
- KiCad dependencies import and legacy footprints have been resaved.
- Every used imported footprint has a verified pin-to-pad mapping.
- `project.design_class` is configured and relative paths are project-root
  relative.
- Multi-board repositories export each design explicitly.
- Rail declarations resolve through module ports without duplication or
  conflicts.
- Strict reports are reviewed before their validation flags are enabled.
- Flattened refdes and generated KiCad output match the intended hierarchy.
