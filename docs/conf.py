# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Add the project root (the folder that contains `src/`) to sys.path
sys.path.insert(0, os.path.abspath(".."))
# src/ directory (so `import compliance` works)
sys.path.insert(0, os.path.abspath("../src"))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "Compliance"
copyright = "2026, Elliott Bache"
author = "Elliott Bache"
release = "0.1.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
]

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Generate autosummary stub pages automatically on build
autosummary_generate = True

# Ensure module pages include their members (functions, classes, etc.)
autodoc_default_options = {
    "members": True,
    # "undoc-members": True,  # avoid error in dataclass where members are documented twice
    "show-inheritance": True,
}

# Explicitly show default values in the argument list
autodoc_preserve_defaults = True

# Show defaults in Args list
typehints_defaults = "comma"

# make header anchors be automatically created from headers
myst_heading_anchors = 3

# This tells MyST: if it looks like a path, just leave it alone
# helps resolve warnings where myst can't find reference but link still works
myst_all_links_external = True

# If you use Google/NumPy docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

# html_theme = 'alabaster'
html_theme = "sphinx_rtd_theme"

html_static_path = ["_static"]
