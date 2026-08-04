---
name: earthground-kicad-catalog
description: Generate, inspect, and query Earthground's project-scoped KiCad footprint catalog through the `earthground kicad catalog` CLI. Use when a user needs installed KiCad library names, footprint names, footprint descriptions or source paths, JSON catalog data, autocomplete enums, catalog freshness, OS-specific KiCad discovery, or custom footprint roots.
---

# Earthground KiCad Catalog

Use the CLI as the source of truth for the KiCad installation and project
configuration. Run commands from the Earthground project or pass
`--project-root PATH`.

## Choose the command

- Generate or refresh autocomplete enums:

  ```bash
  earthground kicad catalog generate
  ```

  This creates `.earthground/config.yaml` when missing, detects standard KiCad
  paths for the OS, and generates the environment catalog. A new config also
  contains `project.design_class: null`; set it before using `compile`.
  Regeneration updates only the `kicad` mapping and preserves `project`, `lcsc`,
  and other project-owned mappings.

- Check configuration and freshness without writing:

  ```bash
  earthground kicad catalog status
  ```

- Return every installed library, footprint, and description:

  ```bash
  earthground kicad catalog get
  ```

- Limit results to one library:

  ```bash
  earthground kicad catalog get Connector_JST
  ```

- Return one exact footprint with description and source path:

  ```bash
  earthground kicad catalog get \
    "Connector_JST:JST_SH_BM02B-SRSS-TB_1x02-1MP_P1.00mm_Vertical"
  ```

Add `--json` to any `get` command when consuming its output programmatically.
Use `uv run earthground` instead of `earthground` when operating from a source
checkout whose installed entry point is unavailable or stale.

## Work with results

For an aggregate JSON response, read:

- `library_count`
- `footprint_count`
- `libraries`, a mapping from each library to objects containing `name` and
  `description`

For a specific-footprint JSON response, read `reference`, `library`,
`footprint`, `description`, and `path`.

Avoid presenting the complete catalog when the user asked for a small set.
Filter JSON by the requested package, connector family, pitch, pin count, or
other name/description terms, then return concise matches.

## Configure custom libraries

After initial generation, edit `.earthground/config.yaml` and add roots that
contain `*.pretty` directories:

```yaml
kicad:
  additional_footprint_roots:
    - ./footprints
```

Run `earthground kicad catalog generate` again after changing roots or KiCad
versions. Do not edit generated modules in `site-packages` directly.

## Handle errors

- Use `--project-root PATH` when the wrong project is detected.
- If KiCad is not detected, inspect `.earthground/config.yaml`, correct
  `executable` and `footprint_root`, then regenerate.
- Preserve exact `Library:Footprint` spelling from `get --json`; enum member
  identifiers normalize punctuation and are not canonical KiCad names.
