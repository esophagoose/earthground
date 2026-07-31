"""Autocompletable enums for footprints installed with the project's KiCad."""

from pathlib import Path

from earthground.kicad.catalog import ensure_environment_catalog

ensure_environment_catalog(Path(__file__).parent)

from ._generated import *  # noqa: E402,F401,F403
from ._generated import __all__  # noqa: E402,F401
