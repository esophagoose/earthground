Part contracts and analysis
===========================

Earthground components can declare configuration straps, required external
parts, power models, and package thermal data. These checks are opt-in so
legacy component definitions continue to compile while the library is
migrated.

Configuration straps
--------------------

Declare strap metadata in ``Component.strap_pins`` with
``earthground.straps.StrapPin`` and ``StrapLevel``. Board or module generators
state the intended result explicitly::

   design.expect_strap(device, "mode", "VIH", "I2C pull-up selects high")
   report = design.check_straps()

The resolver supports direct ties, floating internal dividers, one external
pull resistor, and a two-resistor divider. More complex networks are reported
as ``Unknown`` rather than guessed. The same report is available from::

   earthground straps .

Required externals
------------------

Populate ``Component.requires`` with requirements from
``earthground.contracts``. Supported requirements cover decoupling and bypass
capacitors, pull resistors, same-net constraints, unused-pin policies, and
routing intent. Contract checks resolve through module boundaries, so a
component inside a module can be satisfied by hardware in its parent design::

   report = design.check_contracts()
   design.validate(check_contracts=True)

Placement and routing clauses without machine-readable evidence remain
``Unknown``. A reviewed exception must target the exact emitted check ID and
include a reason::

   design.waive_contract(
       device,
       "vdd-route.routing",
       "verified in the reviewed KiCad layout",
   )

Thermal reports
---------------

``Component.power`` accepts constant, supply-current, or custom power models.
``Component.thermal`` stores the package thermal metrics. Resistor dissipation
is calculated from resolved terminal voltages, and capacitor steady-state
dissipation defaults to zero::

   report = design.thermal_report()
   report.write_csv("thermal.csv")

Only ``RθJA`` is used to estimate junction temperature from the design's
declared ambient range. Other thermal metrics are reported with their exact
identity but are not treated as ambient-to-junction resistance. The CLI form
is::

   earthground thermal . --output thermal.csv
