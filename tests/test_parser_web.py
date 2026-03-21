"""Tests for the HTML/CSS parser."""

import os
import pytest

from codekg.parser_web import parse_file

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_web")


# --- HTML tests ---

def test_html_linked_stylesheet():
    info = parse_file(os.path.join(FIXTURES, "index.html"))
    modules = [imp.module for imp in info.imports]
    assert "style.css" in modules


def test_html_script_src():
    info = parse_file(os.path.join(FIXTURES, "index.html"))
    modules = [imp.module for imp in info.imports]
    assert "app.js" in modules


def test_html_ids():
    info = parse_file(os.path.join(FIXTURES, "index.html"))
    var_names = [v.name for v in info.variables]
    assert "#main" in var_names
    assert "#sidebar" in var_names


# --- CSS tests ---

def test_css_imports():
    info = parse_file(os.path.join(FIXTURES, "style.css"))
    modules = [imp.module for imp in info.imports]
    assert "base.css" in modules
    assert "theme.css" in modules


def test_css_selectors():
    info = parse_file(os.path.join(FIXTURES, "style.css"))
    selector_names = [c.name for c in info.classes]
    assert "body" in selector_names
    assert ".container" in selector_names
    assert "#header" in selector_names


def test_css_pseudo_selector():
    info = parse_file(os.path.join(FIXTURES, "style.css"))
    selector_names = [c.name for c in info.classes]
    assert ".btn:hover" in selector_names
