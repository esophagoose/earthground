# Electrical intent and analysis

Earthground turns datasheet facts and design intent into typed, hierarchy-aware reports. Missing information produces `sv.CheckStatus.UNKNOWN`; do not convert it to a pass or fill it with guessed values.

## Unit-safe bounds and ratings

Use `earthground.standard_values` constructors for checkable intervals:

```python
import earthground.standard_values as sv
from earthground.ratings import Ratings

rail = sv.volts(nominal=3.3, tolerance_pct=5, source="power tree")
absolute_limit = sv.volts(min=sv.UNBOUNDED, max=4.0, source="DS §5.1 p.8")
temperature = sv.celsius(-20, typ=25, max=70, source="system requirement")

part.abs_max = Ratings(vcc=absolute_limit, tj=sv.celsius(max=105))
part.recommended = Ratings(vcc=sv.volts(3.0, typ=3.3, max=3.6), ta=sv.celsius(-40, max=85))
```

`ValueBounds` normalizes compatible SI prefixes, supports interval arithmetic, and carries sources. `None` means unknown; use `sv.UNBOUNDED` only for an explicitly open endpoint. Ratings checks do not treat a typical-only value as a guaranteed limit. Useful constructors include `volts`, `amps`, `ohms`, `farads`, `watts`, `celsius`, `celsius_per_watt`, `ratio`, `weeks`, `millimeters`, and `mils`.

## Typed pins and electrical ERC

Define pin specs in a physical-index-to-spec map:

```python
import earthground.components as cmp

self.pins = cmp.PinContainer.from_dict(
    {
        1: cmp.PowerPinSpec(
            name="VCC",
            role=cmp.PowerRole.INPUT,
            voltage=sv.volts(3.0, typ=3.3, max=3.6),
            abs_max=sv.volts(min=sv.UNBOUNDED, max=4.0),
        ),
        2: cmp.DigitalPinSpec.output(
            name="IRQ",
            drive_style=cmp.DriveStyle.OPEN_DRAIN,
            voltage_operating=sv.volts(0, max=3.6),
        ),
        3: cmp.AnalogPinSpec.input(
            name="ADC",
            ratings=cmp.AnalogPinRatings(
                voltage_operating=sv.volts(0, max=3.3),
            ),
        ),
        4: cmp.NoConnectPinSpec(name="NC"),
        5: cmp.PowerPinSpec(name="GND", role=cmp.PowerRole.GROUND),
    },
    self,
)
```

Use multi-mode `DigitalPinSpec` plus `DigitalMode` for mode-dependent direction/drive behavior. Use `RelativeThreshold(factor, ref)` for thresholds tied to another pin. Put differential membership on pins with `PinInterfaceRef`, and component-level pair facts in `DifferentialInterfaceSpec`; these describe the part interface, while design-level `DiffPair` declarations describe routed nets.

Declare facts supplied by the board environment before checking:

```python
design.declare_rail("P3V3", sv.volts(3.1, typ=3.3, max=3.5))
design.declare_external_drive("UART_RX", sv.volts(0, max=3.3))
design.declare_ambient(sv.celsius(-20, typ=25, max=70))

report = design.check_electrical()
coverage = design.electrical_coverage()
design.validate(check_electrical=True)
```

ERC covers supply compatibility, conflicting drivers, floating inputs, connected no-connect pins, open-drain bias, absolute maximum voltage, and ambient operating range. It is opt-in. Untyped legacy pins affect coverage but do not create fake evidence. For driver contention and source-voltage inference, same-name pins on one component are one logical electrical pin even when a package exposes it on several physical pads. Such pads must resolve to the same flattened net; E8 reports a split logical pin.

Rail and external-drive declarations resolve on flattened physical nets. A
board-level declaration is visible through connected module ports; do not copy
it into every child design. Conflicting declarations on the same resolved net
make its voltage unknown. Parent-level pull resistors are likewise visible to
child pins. Simple high-impedance pull networks and resistor dividers are
resolved conservatively for absolute-maximum and resistor-power analysis;
driven, conflicted, or unsupported networks remain `Unknown`.
`InternalDigitalFeatures(pull_up=True)` or `pull_down=True` supplies valid
floating-input bias. Add `pull_up_to` or `pull_down_to`, resistance bounds, and
a source when that internal termination should also establish a DC pin voltage.
Ordinary open-drain and positive differential lines
require a pull-up to a positive rail; a `PinInterfaceRef` with `NEGATIVE`
polarity requires a pull-down to a non-positive rail.

## Strap pins

Declare sampled configuration behavior on the component with stable IDs:

```python
import earthground.straps as straps

strap_pins = (
    straps.StrapPin(
        id="cfg",
        pin="CFG",
        reference="VCC",
        levels=(
            straps.StrapLevel(name="VIL", ratio=sv.ratio(0, max=0.2), meaning="low"),
            straps.StrapLevel(name="VIM", ratio=sv.ratio(0.4, max=0.6), meaning="middle"),
            straps.StrapLevel(name="VIH", ratio=sv.ratio(0.8, max=1), meaning="high"),
        ),
        internal_pull_up=sv.ohms(100_000, typ=100_000, max=100_000),
        internal_pull_down=sv.ohms(100_000, typ=100_000, max=100_000),
        sampled_on="rising edge of reset",
        source="DS strap table",
    ),
)
```

On the owning design, record the intended result with a reason, then inspect or enforce it:

```python
design.expect_strap(part, "cfg", "VIM", "use datasheet floating default")
report = design.check_straps()
design.validate(check_straps=True)
```

The resolver handles floating internal dividers, direct rail/ground ties, and simple external resistor bias/dividers. More complex branches stay `Unknown`. Check `externally_overridden` and `determining_components` when an I²C pull-up or other support part changes the sampled level. The CLI equivalents are `uv run earthground straps <project>` and `uv run earthground thermal <project> ...`; inspect `--help` for the current project-loading and output arguments.

## Required-external contracts

Set `self.requires` to declarations imported from `earthground.contracts`: `Decoupling`, `Bypass`, `PullResistor`, `SameNet`, `TieIfUnused`, `LeaveOpenIfUnused`, and `RoutingConstraint`. Every requirement needs a stable `id`; include `source` when known.

```python
import earthground.contracts as contracts

self.requires = (
    contracts.Decoupling(
        id="vcc-decoupling",
        pin="VCC",
        capacitance=sv.farads(min="100n", max=sv.UNBOUNDED),
        max_distance_mm=3.0,
        source="DS §9.2",
    ),
    contracts.SameNet(id="reg-link", pins=("VREG", "VDD")),
)

report = design.check_contracts()
design.waive_contract(part, "vcc-decoupling.distance", "verified in board review REV-B")
design.validate(check_contracts=True)
```

Contracts resolve through module boundaries. Topology can pass before placement while distance remains `Unknown`. Decoupling distance is measured between the transformed centres of the named device pad and the capacitor's supply pad, not between component origins. Untyped routing notes are non-blocking advisories; typed width and differential-impedance requirements are checked against declared net classes and differential pairs. Waive the exact generated check ID, locally, with a non-empty reason; do not waive a whole requirement because one aspect lacks evidence.

## Power and thermal reporting

Attach a `thermal.ThermalModel` and either `ConstantPower`, `SupplyCurrentPower`, or `CallablePower` to a component. `SupplyCurrentPower` uses declared/resolved rail voltage and typed current bounds. Resistor power is inferred from resolved terminal rails; capacitor steady-state power is zero; other components without a model stay `Unknown`.

```python
import earthground.thermal as thermal

self.thermal = thermal.ThermalModel(
    r_ja=sv.celsius_per_watt(40, typ=40, max=40, source="DS thermal table"),
)
self.power = thermal.SupplyCurrentPower(
    rails=(thermal.RailCurrent(pin="VCC", current=sv.amps(0.01, typ=0.02, max=0.03)),),
)

design.declare_ambient(sv.celsius(25, typ=25, max=50))
report = design.thermal_report()
report.write_csv("generated_outputs/thermal.csv")
```

Thermal resistance selection is `RθJB`, `RθJC(bottom)`, `RθJC(top)`, then `RθJA`; the report records which metric it used. Junction estimates using `RθJA` require ambient and power bounds. Put `tj` in component `abs_max` when known.

When no defensible ambient exists, use `design.defer_ambient("reason")`. E7 remains `Unknown` but is acknowledged for electrical validation; thermal rows remain unknown and retain the reason rather than fabricating a temperature.

## Provenance and sourcing

Populate component metadata from evidence, not inference:

```python
self.manufacturer = "Vendor"
self.mpn = "PART-123"
self.description = "Function and package"
self.datasheet = "https://vendor.example/PART-123.pdf"
self.datasheet_revision = "Rev C"
self.datasheet_sha256 = "..."  # only when actually computed/recorded
self.lead_time = sv.weeks(typ=8, source="supplier snapshot 2026-07-01")
self.lifecycle = cmp.Lifecycle.ACTIVE
self.alternates = ["PART-123A"]
self.distributor_ids["lcsc"] = "C123456"
```

`lead_time` accepts only week-dimensioned `ValueBounds`; migrate legacy floats/strings instead of supporting them. `Lifecycle` values are `ACTIVE`, `NRND`, `EOL`, `OBSOLETE`, `PREVIEW`, and `UNKNOWN`. An unknown lifecycle reports `Unknown`; known non-active lifecycles fail. `validate(check_sourcing=True)` treats both as blocking.

Set `procurement_mode` and `documentation_mode` to `EvidenceMode.NOT_APPLICABLE` only for fabricated features that genuinely have no purchased part or datasheet. Generic passives default to `RESOLVER`. Register a pure project resolver with `design.register_sourcing_resolver(...)`; it returns `SourcingEvidence` containing the selected MPN, lifecycle, datasheet metadata, and evidence source without mutating the component.

`datasheet_coverage()` categorizes populated components as `provenanced` when a URL plus revision or SHA256 exists, `url_only`, `undocumented`, or `not_applicable`. Resolver evidence feeds the same coverage report.

All check reports expose `.checks`, `.items`, status partitions, and `.is_valid`; the older `.results` and `.rows` names remain available.

## Signal-integrity intent

Declare constraints against existing flattened net names:

```python
import earthground.signal_integrity as si

design.declare_net_class(si.NetClass(
    "DPHY",
    ("CLK_P", "CLK_N"),
    clearance=sv.millimeters(typ=0.15),
    diff_pair_width=sv.millimeters(typ=0.10),
    diff_pair_gap=sv.millimeters(typ=0.12),
    z_single=sv.ohms(nominal=50, tolerance_pct=15),
    source="stack-up calculation",
))
design.declare_diff_pair(si.DiffPair(
    ("CLK_P", "CLK_N"),
    "DPHY",
    z_diff=sv.ohms(nominal=100, tolerance_pct=15),
    intra_pair_skew=sv.mils(max=5),
    max_vias=2,
    max_length=sv.millimeters(max=300),
    min_track_angle_deg=135,
    source="DS layout section",
))
```

Signal-integrity declaration consistency is part of base `validate()`: nets and net classes must exist and pair membership must agree. Geometry fields used as KiCad widths/gaps require a typical value. Impedance is documented intent only; Earthground does not derive trace geometry from impedance or a board stack-up. See the layout reference for `.kicad_pro` and `.kicad_dru` export behavior.
