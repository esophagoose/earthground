---
name: earthground-export
description: Validate and export an Earthground Python design file to a KiCad `.kicad_pcb` board through `earthground export kicad`. Use when creating or refreshing KiCad board output, locating an export, or diagnosing design-file import, selection, validation, and export failures.
---

# Earthground Export

Pass the Python source file containing the Earthground design:

```bash
earthground export kicad path/to/design.py
```

Prefer `uv run earthground` in a source checkout when the installed entry point
is unavailable or stale.

## Resolve the design

In order, use:

1. A module-level `design` containing an `earthground.schematic.Design`.
2. A module-level `schematic` containing a `Design`.
3. The only `Design` subclass defined by the file, instantiated without
   arguments.

If multiple subclasses exist, assign the intended instance to `design`.

Discover the project root upward from the source file. Create
`.earthground/config.yaml` with detected KiCad paths when it is missing. On
success, write:

```text
PROJECT/generated_outputs/{Design.name}.kicad_pcb
```

Treat an existing file as an intentional overwrite. Confirm exit status 0 and
verify the reported path exists before claiming success.

## Handle failures

- Treat exit status 1 as a design construction, validation, or KiCad export
  failure. Report each validation error and do not expect output to be created.
- Treat exit status 2 as an invalid source path, ambiguous design, or Python
  import failure.
- Verify the path points to a `.py` file rather than a project directory.
- Ensure imports resolve from the discovered project root.
