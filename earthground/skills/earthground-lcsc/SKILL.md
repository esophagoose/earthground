---
name: earthground-lcsc
description: Query Earthground's configured read-only LCSC SQLite database by exact manufacturer part number and return C-prefixed LCSC IDs, packages, descriptions, or JSON. Use when resolving MPNs to current LCSC parts, checking existing LCSC assignments, or retrieving supplier metadata for electrical components.
---
# Earthground LCSC

Use the configured local database as the source of truth for LCSC identifiers.
Run commands from the Earthground project or pass `--project-root PATH`.

## Configure the database

Define the SQLite database in `.earthground/config.yaml`:

```yaml
lcsc:
  db: toolchain/jlcdb/jlcpcb_db.sqlite3
```

The path may be absolute or relative to the Earthground project root (the
directory containing `.earthground`). If that root is `repo/electrical`, do not
prefix the relative value with `electrical/`; doing so resolves to a duplicated
`repo/electrical/electrical/...` path.

## Look up parts

Return human-readable matches:

```bash
earthground lcsc lookup FUSB302BVMPX
```

Return only C-prefixed identifiers:

```bash
earthground lcsc lookup --id-only FUSB302BVMPX
```

Return structured results for one or more MPNs:

```bash
earthground lcsc lookup --json FUSB302BVMPX CH334R
```

Prefer `uv run earthground` in a source checkout when the installed command is
unavailable or stale.

## Interpret results

- Treat matching as exact and case-insensitive.
- Return every database match; one MPN can map to multiple LCSC IDs.
- Preserve the leading `C` in every identifier.
- For JSON, read `results`, then each query's `matches`. Each match contains
`lcsc_id`, `mpn`, `package`, and `description`.
- Treat an empty `matches` list or exit status 1 as not found.
- Treat exit status 2 as a configuration or database error.

Do not copy an LCSC ID from source code or memory when the user asked for a
database lookup; query the configured database because assignments can change.

## Handle errors

- If project discovery is wrong, add `--project-root PATH`.
- If configuration is missing, add the `lcsc.db` entry.
- If the database cannot be opened, verify that the configured path exists and
points to the expected SQLite component database.
- Keep queries read-only and parameterized; do not modify or migrate the
component database during lookup tasks.
