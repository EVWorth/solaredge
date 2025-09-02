"""Configuration file for the Sphinx documentation builder."""

import os
import sys
from datetime import datetime
from importlib.metadata import version

# Add project root to sys.path so autodoc works
sys.path.insert(0, os.path.abspath(".."))

# -- Project information -----------------------------------------------------
project = "solaredge"
author = "Elliot Worth"
release = version("solaredge")
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
