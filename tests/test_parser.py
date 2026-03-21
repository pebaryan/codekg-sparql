"""Tests for the Tree-sitter Python parser."""

import os

from codekg.parser import parse_file

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


def test_parse_functions():
    info = parse_file(os.path.join(FIXTURES, "config.py"))
    func_names = [f.name for f in info.functions]
    assert "parse_config" in func_names
    assert "validate_config" in func_names


def test_parse_function_details():
    info = parse_file(os.path.join(FIXTURES, "config.py"))
    parse_fn = next(f for f in info.functions if f.name == "parse_config")
    assert parse_fn.start_line > 0
    assert parse_fn.end_line >= parse_fn.start_line
    assert parse_fn.docstring == "Parse a configuration file and return settings."
    param_names = [p.name for p in parse_fn.parameters]
    assert "path" in param_names


def test_parse_classes():
    info = parse_file(os.path.join(FIXTURES, "models.py"))
    class_names = [c.name for c in info.classes]
    assert "BaseModel" in class_names
    assert "User" in class_names
    assert "AdminUser" in class_names


def test_parse_inheritance():
    info = parse_file(os.path.join(FIXTURES, "models.py"))
    user_cls = next(c for c in info.classes if c.name == "User")
    assert "BaseModel" in user_cls.bases
    admin_cls = next(c for c in info.classes if c.name == "AdminUser")
    assert "User" in admin_cls.bases


def test_parse_methods():
    info = parse_file(os.path.join(FIXTURES, "models.py"))
    user_cls = next(c for c in info.classes if c.name == "User")
    method_names = [m.name for m in user_cls.methods]
    assert "__init__" in method_names
    assert "greet" in method_names


def test_parse_calls():
    info = parse_file(os.path.join(FIXTURES, "app.py"))
    create_fn = next(f for f in info.functions if f.name == "create_app")
    assert "parse_config" in create_fn.calls
    assert "validate_config" in create_fn.calls


def test_parse_imports():
    info = parse_file(os.path.join(FIXTURES, "app.py"))
    assert len(info.imports) > 0
    all_names = []
    for imp in info.imports:
        all_names.extend(imp.names)
    assert "parse_config" in all_names
    assert "User" in all_names


def test_parse_variables():
    info = parse_file(os.path.join(FIXTURES, "config.py"))
    var_names = [v.name for v in info.variables]
    assert "DEFAULT_PORT" in var_names
    assert "CONFIG_PATH" in var_names
