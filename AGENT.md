# Agent Guidelines

## Project Overview

Earthground is a Python library for creating software-defined electrical designs (schematics, PCB layouts). It exports to KiCad and uses `kiutils`, `pykicad`, and other dependencies defined in `pyproject.toml`.

## Environment

- Use `uv` for all package management and script execution. Do not use `pip` or `python` directly.
- If you must invoke the Python interpreter, use `python3` (never `python`).
- Run tests: `uv run pytest`
- Run a module: `uv run -m <module.path>`
- Install dependencies: `uv sync`
- Note: `pykicad` is a local dependency at `../pykicad` (see `[tool.uv.sources]` in `pyproject.toml`).

## Code Style

- Format with `black`: `uv run black .`
- Python 3.10+ is required.

## Testing

- Tests live in `tests/`.
- Run the full suite with `uv run pytest`.
- Run a single test file: `uv run pytest tests/test_<name>.py`

## Breaking Changes

- Do not create fallback options or backwards-compatibility shims.
- If a change breaks backwards compatibility, flag it to the user but proceed with the change.
