# Hierarchy and reusable modules

## Build a reusable module

```python
import earthground.components as cmp
import earthground.schematic as sch

def make_filter() -> sch.Design:
    module = sch.Design("Input Filter", short_name="FLT", ports=["IN", "OUT", "GND"])
    r = module.add_component(cmp.Resistor("100"))
    c = module.add_component(cmp.Capacitor("100n", "16V"))
    module.connect([module.port.IN, r.pins[1]], "IN")
    module.connect([r.pins[2], c.pins[1], module.port.OUT], "OUT")
    module.connect([c.pins[2], module.port.GND], "GND")
    return module

parent = sch.Design("Board")
flt = parent.add_module(make_filter())
parent.join_net(flt.port.IN, "RAW_IN")
parent.join_net(flt.port.OUT, "FILTERED")
parent.join_net(flt.port.GND, "GND")
```

Create a fresh module per instance. `add_module` mutates its `short_name`, nets, passive footprints, and port symbol ownership.

## Ports are connections, not assignable fields

- Declare all names in `Design(..., ports=[...])`.
- Access ports as `module.port.OUT` or `module.port["OUT"]`.
- Connect a port inside the module to define its internal electrical node.
- Connect that same port from the parent to expose it externally.
- Do not assign `module.port.OUT = pin` or `module.port["OUT"] = pin`; direct setting is prohibited.
- `set_ports({...})` accepts net-name strings or pins after construction.

The port symbol is virtual. It exists in the parent component map for hierarchy/layout bookkeeping but is skipped as a physical footprint.

## Net scoping surprises

When added, a module gets a numbered short name (`FLT1`, `FLT2`). Existing non-GND module nets are renamed with that prefix. Already-prefixed nets are not prefixed twice.

Connecting a module port to a parent net can rename the port-connected internal net. During schematic flattening, port-connected internal nodes merge into the parent node. Non-port internal nets remain distinct/scoped according to the current flattening path. Inspect the current `flatten` implementation and `tests/test_module_net_names.py` before changing this behavior.

Only `GND` is inherently global. Names such as `VCC`, `P3V3`, or `VBUS` are scoped unless exposed through a port and connected by the parent.

## Reference design generators

Use `generate_design(...)` when a part needs recommended support circuitry or configuration abstraction:

- Validate ranges before constructing the design.
- Return a `Design` with a stable, short refdes prefix and semantic ports.
- Add the central IC and recommended passives inside it.
- Encode address straps, pull-ups, feedback networks, and optional circuitry from arguments.
- Make optional support parts explicit with `None` or a boolean.
- Instantiate default components inside the function. Do not use `cmp.Capacitor(...)` or another mutable component as a default argument in new code.

Study `tca9535pwr.generate_design`, `lm317.LM317AMDTX.generate_design`, and another part in the same family before adding a generator.

## Nested placement

The parent places the virtual module refdes (for example `FLT1`). The child layout holds internal placements. `Layout.flatten()` rotates/translates child positions and composes board side:

- top parent + child side keeps the child side;
- bottom parent flips the child side;
- flattened designators use `<module-refdes>_<child-refdes>`.

Give reusable modules a complete internal layout if they are intended as standardized PCB blocks. Otherwise their internal parts float using default placement.

## Hierarchy-aware analysis

Electrical, strap, contract, thermal, provenance, and sourcing reports use `DesignAnalysis` to resolve flattened refdes, nets, components, and explicit placements without mutating the design. Declare expectations or waivers on the `Design` that directly owns the component; parent-level reports still see them through the hierarchy. Required-external contracts may be satisfied by circuitry in a parent design. Placement-dependent checks remain `Unknown` until both the module and the relevant internal/support parts have explicit placements.
