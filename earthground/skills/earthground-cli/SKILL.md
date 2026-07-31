---
name: earthground-cli
description: Earthground is a Python toolkit for defining, validating, and producing electrical designs in code, with KiCad and LCSC integrations. Use this skill to route Earthground CLI requests to the correct command and specialized skill.
---
# Earthground CLI

Earthground defines, validates, and produces electrical designs in Python, with
KiCad and LCSC integrations. Route each request to the narrowest command and
specialized skill.

## CLI command map


| CLI command                           | Function                             | Use when                                                                                              | Skill file                                                                              |
| ------------------------------------- | ------------------------------------ | ----------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `earthground`                         | Top-level command hierarchy.         | Starting any Earthground CLI task or discovering available integrations.                              | [Earthground CLI](./SKILL.md)                                                           |
| `earthground compile`                 | Load and validate a design project.  | The project design class must be constructed and checked for schematic errors.                        | [Earthground CLI](./SKILL.md)                                                           |
| `earthground export`                  | Select project export commands.      | A validated Earthground design must be converted to another design format.                            | [Earthground Export](../earthground-export/SKILL.md)                                    |
| `earthground export kicad`            | Export a validated KiCad PCB file.   | A Python file containing an Earthground design must produce a `.kicad_pcb` file.                      | [Earthground Export](../earthground-export/SKILL.md)                                    |
| `earthground kicad`                   | Select KiCad integration commands.   | The request involves KiCad data, configuration, export, or tooling.                                   | [Earthground KiCad catalog](../earthground-kicad-catalog/SKILL.md) for catalog requests |
| `earthground kicad catalog`           | Select footprint catalog operations. | The request involves installed footprint libraries, catalog enums, descriptions, or catalog health.   | [Earthground KiCad catalog](../earthground-kicad-catalog/SKILL.md) for catalog requests |
| `earthground kicad update-footprints` | Update PCB footprint definitions.    | There's been a footprint change in the Earthground design that should propagate to the Kicad PCB file | [Earthground CLI](./SKILL.md)                                                           |
| `earthground lcsc`                    | Select LCSC database operations.     | The request involves mapping manufacturer part numbers to LCSC parts.                                 | [Earthground LCSC](../earthground-lcsc/SKILL.md)                                        |
| `earthground lcsc lookup`             | Look up C-prefixed LCSC IDs by MPN.  | A manufacturer part number must be resolved against the configured local LCSC database.               | [Earthground LCSC](../earthground-lcsc/SKILL.md)                                        |
| `earthground skills`                  | Select agent skill commands.         | Earthground's packaged agent skills must be added to a Claude project.                                | [Earthground CLI](./SKILL.md)                                                           |
| `earthground skills add`              | Add packaged skills to Claude.       | Copy Earthground skills into the current project's `.claude/skills` after explicit confirmation.      | [Earthground CLI](./SKILL.md)                                                           |


## Handle failures

- For `compile`, read `project.design_class` from `.earthground/config.yaml`.
  Require the `python.module:DesignClass` form and a zero-argument
  `earthground.schematic.Design` subclass.
- For `export kicad`, pass a Python design file and write the board under the
  discovered project root's `generated_outputs/` only after validation succeeds.
- For `kicad update-footprints`, require a Python design file and an existing
  `.kicad_pcb`. Refuse to write unless component counts and reference
  designators match exactly.
- For `skills add`, show the source, destination, skill names, and overwrite
  behavior. Make no filesystem changes unless the user explicitly confirms.
- If project discovery selects the wrong directory, rerun the leaf command with
  `--project-root PATH`.
