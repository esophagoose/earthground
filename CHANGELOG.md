# Changelog

All notable changes to Earthground are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.0] - 2026-08-03

### Added

- Migration guide for upgrading Earthground 0.5 projects to 0.9 and adopting
  typed electrical intent, component analysis, sourcing, and KiCad rules.
- Generated project configuration now includes a `project.design_class` stub.

### Changed

- Electrical rule checking now resolves rails, external drives, and resistor
  bias across module boundaries.
- Differential-negative open-drain nets require a pull-down to a non-positive
  rail; ordinary open-drain nets continue to require a positive pull-up.
- Decoupling distance checks prefer relevant local support components and keep
  concrete placement evidence when unrelated parts are unplaced.
- KiCad catalog regeneration preserves non-KiCad project configuration.

### Fixed

- Internal digital pull-ups and pull-downs now satisfy floating-input checks.
- Compile and LCSC configuration failures provide actionable configuration and
  project-root path guidance.
- Removed the D-Sub connector import-time invalid escape warning.

## [0.9.1] - 2026-08-03

### Changed

- Simplified TCA9535 address strapping and migrated its generated design to the
  current port and decoupling APIs.
- Tightened conversion between voltage values and canonical power-net names.

### Removed

- Removed the unused `ElectricalBool` and obsolete geometry helpers from
  `earthground.utils`.

## [0.9.0] - 2026-08-01

### Added

- Datasheet provenance coverage and typed component sourcing metadata.
- Lifecycle validation, distributor identifiers, alternates, and unit-safe lead
  times.
- Typed passive ratings with strict constructor arguments.
- Declarative signal-integrity net classes and differential-pair constraints.
- KiCad project and design-rule export for signal-integrity constraints.
- Expanded Earthground skill guidance for typed electrical intent, rule checks,
  straps, required-external contracts, thermal analysis, sourcing, provenance,
  and signal-integrity workflows.

### Changed

- KiCad footprints now include datasheet, lifecycle, and distributor metadata.
- Removed the unused LTspice model field and documented LTspice export as
  unsupported.

## [0.8.1] - 2026-08-01

### Added

- SN65DPHY440SS Tier 2 analysis example.

### Changed

- Moved test and formatting tools out of runtime dependencies.
- Removed abandoned development tools, stale schematic-generation tests, and
  documentation for commands that are not present in the package.
- Removed unused runtime dependencies.

## [0.8.0] - 2026-08-01

### Added

- Tier 2 design analysis with machine-readable and Markdown reports.
- Design contracts for voltage, current, timing, power, and thermal constraints.
- Strap modeling and validation for configurable hardware pins.
- Thermal analysis for components and complete designs.
- `earthground analysis-report` CLI command.
- Documentation and tests for the Tier 2 analysis APIs.

## [0.7.1] - 2026-08-01

### Added

- A bundled Earthground implementation skill covering components, hierarchy,
  layout, export, debugging, and verification workflows.

## [0.7.0] - 2026-07-31

### Added

- Hierarchical `earthground` CLI with project compilation, KiCad export,
  footprint generation and updates, LCSC integration, and skill installation.
- Typed pin hierarchy, electrical ratings, and electrical rule checking.
- Assemblies, connector interfaces, and board-to-board connector support.
- KiCad footprint catalog and populated pads for imported footprints.
- YAML layout import and KiCad IPC placement workflows.
- Rigid modules and optional silkscreen support.

### Changed

- Replaced `kiutils` with `python-kicad` for KiCad parsing and generation.
- Moved footprint placement to native KiCad APIs.
- Encapsulated schematic net registries and strengthened connection validation.
- Improved logging and error messages for invalid connections.
- Changed `SiNumber` internals from floating-point values to `Decimal` values.

### Fixed

- Hierarchical single-connection validation and orphaned design-port nets.
- Net propagation and module net renaming.
- KiCad footprint rotation and reference-designator placement.
- Custom passive packages, footprint registration without silkscreen, and zone
  handling.
- PWM prioritization and non-integer index validation.

## [0.2.0] - 2026-03-29

### Added

- KiCad IPC integration and an accompanying example.
- Initial coding-agent guidelines.

### Fixed

- KiCad IPC startup behavior.

[Unreleased]: https://github.com/esophagoose/earthground/compare/d721788...HEAD
[0.9.0]: https://github.com/esophagoose/earthground/compare/48614be...d721788
[0.8.1]: https://github.com/esophagoose/earthground/compare/f157003...48614be
[0.8.0]: https://github.com/esophagoose/earthground/compare/08419e9...f157003
[0.7.1]: https://github.com/esophagoose/earthground/compare/1261d84...08419e9
[0.7.0]: https://github.com/esophagoose/earthground/compare/72d8976...1261d84
[0.2.0]: https://github.com/esophagoose/earthground/releases/tag/72d8976
