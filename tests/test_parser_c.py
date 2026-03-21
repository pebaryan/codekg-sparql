"""Tests for the C/C++ parser."""

import os
import pytest

from codekg.parser_c import parse_file

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_c_project")


# --- C tests ---

def test_c_functions():
    info = parse_file(os.path.join(FIXTURES, "main.c"))
    func_names = [f.name for f in info.functions]
    assert "add" in func_names
    assert "main" in func_names


def test_c_function_params():
    info = parse_file(os.path.join(FIXTURES, "main.c"))
    add = [f for f in info.functions if f.name == "add"][0]
    param_names = [p.name for p in add.parameters]
    assert "a" in param_names
    assert "b" in param_names


def test_c_function_calls():
    info = parse_file(os.path.join(FIXTURES, "main.c"))
    main = [f for f in info.functions if f.name == "main"][0]
    assert "add" in main.calls
    assert "printf" in main.calls


def test_c_includes():
    info = parse_file(os.path.join(FIXTURES, "main.c"))
    modules = [imp.module for imp in info.imports]
    assert "stdio.h" in modules
    assert "utils.h" in modules


def test_c_typedef_struct():
    info = parse_file(os.path.join(FIXTURES, "main.c"))
    class_names = [c.name for c in info.classes]
    assert "Point" in class_names


def test_c_struct():
    info = parse_file(os.path.join(FIXTURES, "main.c"))
    class_names = [c.name for c in info.classes]
    assert "Color" in class_names


def test_c_global_variable():
    info = parse_file(os.path.join(FIXTURES, "main.c"))
    var_names = [v.name for v in info.variables]
    assert "global_count" in var_names


# --- C++ tests ---

def test_cpp_classes():
    info = parse_file(os.path.join(FIXTURES, "shapes.cpp"))
    class_names = [c.name for c in info.classes]
    assert "Shape" in class_names
    assert "Circle" in class_names


def test_cpp_inheritance():
    info = parse_file(os.path.join(FIXTURES, "shapes.cpp"))
    circle = [c for c in info.classes if c.name == "Circle"][0]
    assert "Shape" in circle.bases


def test_cpp_class_methods():
    info = parse_file(os.path.join(FIXTURES, "shapes.cpp"))
    shape = [c for c in info.classes if c.name == "Shape"][0]
    method_names = [m.name for m in shape.methods]
    assert "area" in method_names
    assert "describe" in method_names


def test_cpp_namespace():
    info = parse_file(os.path.join(FIXTURES, "shapes.cpp"))
    # Rectangle is inside namespace geometry
    class_names = [c.name for c in info.classes]
    assert "Rectangle" in class_names
    # compute_total is a namespace-level function
    func_names = [f.name for f in info.functions]
    assert "compute_total" in func_names


def test_cpp_includes():
    info = parse_file(os.path.join(FIXTURES, "shapes.cpp"))
    modules = [imp.module for imp in info.imports]
    assert "iostream" in modules
    assert "string" in modules
