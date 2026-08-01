# Core designs and connectivity

## Minimal current pattern

```python
import earthground.components as cmp
import earthground.exporters.kicad as kicad
import earthground.layout as layout
import earthground.schematic as sch

design = sch.Design("Divider")
design.default_passive_size = "0603"

r1 = design.add_component(cmp.Resistor("10k"))
r2 = design.add_component(cmp.Resistor("20k"))
c1 = design.add_component(cmp.Capacitor("100n", "16V"))

design.connect([r1.pins[1], r2.pins[1]], "VIN")
design.connect([r1.pins[2], c1.pins[1]], "VOUT")
design.connect([r2.pins[2], c1.pins[2]], "GND")

design.layout.placement["R1"] = layout.Placement(layout.Position(10, 10, 0))
design.validate()
kicad.KicadExporter(design).save("generated_outputs")
```

`Capacitor` requires both capacitance and voltage. A passive without an explicit footprint receives one when added, using `component.package_size` or `design.default_passive_size`.

## Ownership and identity

- `add_component` mutates the component: assigns its parent and marks it placed. Adding the same object again or to another design raises an error.
- A design's dictionary key (`R1`, `U1`) is assigned per prefix within that design. `component.refdes` is backed by a process-global counter and can differ in long-running/test processes. Use the design dictionary keys for placement and flattened export behavior.
- Retain the object returned by `add_component` and `add_module`.
- Add a component before calling `component.set_pins(...)`, `pin.net`, or pin-level helpers that need a parent design.

## Pins

- `pins[index]` and `pins.by_index(index)` address physical pin indexes, normally integers starting at 1.
- `pins.by_name("VCC")` is preferred for semantic part pins.
- `pins.all_with_name(...)` handles duplicated logical names when a package has several pins with the same role.
- `PinContainer` preserves declaration order, while pin identity is physical index + name + owning object. Typed metadata does not change identity or hashing.
- `pin.net` raises if the pin is not connected; use `design.pin_to_net.get(pin)` when absence is valid.

## Nets

- `join_net(pin, name)` creates the named net if necessary and connects one pin.
- `connect(pins, name=None)` connects multiple pins. With no name, it reuses the first existing net or creates `AutoNet_<first-pin-name>`.
- Connecting a pin already on a different net invokes net renaming/merging behavior. Avoid relying on incidental order when two named nets meet; specify the intended name or call `merge_nets` explicitly.
- `change_net_name` expects an existing old name.
- `merge_nets(source, target, name=None)` removes the source and moves its pins to the target.
- `GND` is created automatically and is the only net treated as globally unscoped in modules.

## Buses

Buses are named tuples (for example an I2C bus) whose fields contain pins:

```python
design.connect_bus([controller.i2c, peripheral.i2c])
```

All buses must have exactly the same Python type. Earthground names nets `<BusType><index>_<FIELD>`, such as `I2C0_SDA`. Pass `bus_index=` to deliberately join an existing indexed bus. Do not connect vaguely similar tuples or individual pin lists with `connect_bus`.

## Circuit helpers

Prefer current method names from `schematic.py`:

- `add_pullup_resistor(pin, ohms, net_name)`
- `add_series_res(pin1, ohms, pin2, net_name=None)`
- `add_voltage_divider(input_pin, output_pin, divider, resistance, ...)`
- `pin.add_decoupling_capacitor(capacitor, net_name=None, ground_net_name="GND")`
- `design.add_decoupling_capacitor(capacitor, net_name=..., ...)`

Beware older examples using `add_decoupling_cap`. For a decoupler tied to a supply pin, the pin-level method is clearest. Pass a fresh capacitor instance, not a shared default object.

## Validation and inspection

```python
design.print()       # connectivity view
design.validate(
    skip_footprint_check=False,
    check_no_single_connections=False,
    check_electrical=False,
    check_straps=False,
    check_contracts=False,
    check_sourcing=False,
)
```

Base validation recursively checks modules, component validators, footprints (unless skipped), optional single-pin nets, and always validates declared signal-integrity references. Electrical ERC, strap resolution, required-external contracts, and sourcing validation are opt-in because library coverage is incomplete. Their strict validation treats both `Fail` and unresolved `Unknown` as errors where applicable; inspect `check_electrical()`, `check_straps()`, `check_contracts()`, or `sourcing_report()` before deciding whether to add evidence or an explicit contract waiver. Do not disable footprint checking merely to make KiCad export proceed: the exporter also requires footprints.

Use `electrical_coverage()` and `datasheet_coverage()` to report migration/evidence coverage. `datasheet_coverage()` returns recursive `provenanced`, `url_only`, and `undocumented` refdes tuples and ignores virtual/DNP components.
