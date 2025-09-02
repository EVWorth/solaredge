"""Configuration file for the Sphinx documentation builder."""

import os
import sys
import tomllib  # type: ignore[import-untyped]  # Python 3.13+ built-in
from datetime import datetime

# Add project root to sys.path so autodoc works
sys.path.insert(0, os.path.abspath(".."))

# Read version from pyproject.toml
with open("../pyproject.toml", "rb") as f:
    pyproject = tomllib.load(f)

# -- Project information -----------------------------------------------------
project = "solaredge"
author = "Elliot Worth"
release = pyproject["project"]["version"]
copyright = f"{datetime.now().year}, {author}"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",  # for Google/NumPy docstrings
    "sphinx.ext.viewcode",
    "myst_parser",  # markdown support
]

templates_path = ["_templates"]
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
html_theme = "furo"
html_static_path = ["_static"]
