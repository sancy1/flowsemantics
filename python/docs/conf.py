"""Sphinx configuration for FlowSemantics API docs."""

# Sphinx configuration for FlowSemantics API docs.
# Generated HTML mirrors the C# XML / Java Javadoc / Go godoc output.

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "FlowSemantics"
copyright = "2026, Alexander (Cyril) Sanchez"
author = "Alexander (Cyril) Sanchez"
release = "0.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
]

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": False,
    "show-inheritance": True,
}

autosummary_generate = True
napoleon_google_docstring = True
napoleon_numpy_docstring = False

html_theme = "alabaster"
html_static_path = []
