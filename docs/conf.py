import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "earthground"
copyright = "2024"
author = "esophagoose"

release = "0.1"
version = "0.1.0"

extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "myst_parser",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}
intersphinx_disabled_domains = ["std"]
autodoc_mock_imports = ["pygerber", "kiutils"]
templates_path = ["_templates"]
html_theme = "sphinx_rtd_theme"
source_suffix = [".rst", ".md"]
