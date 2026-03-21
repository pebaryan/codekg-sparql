"""Tests for the TypeScript/JavaScript parser."""

import os

from codekg.parser_ts import parse_file

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_ts_project")


def test_parse_functions():
    info = parse_file(os.path.join(FIXTURES, "config.ts"))
    func_names = [f.name for f in info.functions]
    assert "parseConfig" in func_names
    assert "validateConfig" in func_names


def test_parse_function_params():
    info = parse_file(os.path.join(FIXTURES, "config.ts"))
    parse_fn = next(f for f in info.functions if f.name == "parseConfig")
    param_names = [p.name for p in parse_fn.parameters]
    assert "path" in param_names


def test_parse_function_calls():
    info = parse_file(os.path.join(FIXTURES, "app.ts"))
    create_fn = next(f for f in info.functions if f.name == "createApp")
    assert "parseConfig" in create_fn.calls
    assert "validateConfig" in create_fn.calls


def test_parse_arrow_function():
    info = parse_file(os.path.join(FIXTURES, "app.ts"))
    func_names = [f.name for f in info.functions]
    assert "handleRequest" in func_names


def test_parse_arrow_function_calls():
    info = parse_file(os.path.join(FIXTURES, "app.ts"))
    handle_fn = next(f for f in info.functions if f.name == "handleRequest")
    assert "processAction" in handle_fn.calls


def test_parse_classes():
    info = parse_file(os.path.join(FIXTURES, "models.ts"))
    class_names = [c.name for c in info.classes]
    assert "BaseModel" in class_names
    assert "User" in class_names
    assert "AdminUser" in class_names


def test_parse_interface():
    info = parse_file(os.path.join(FIXTURES, "models.ts"))
    class_names = [c.name for c in info.classes]
    assert "Validatable" in class_names


def test_parse_inheritance():
    info = parse_file(os.path.join(FIXTURES, "models.ts"))
    user_cls = next(c for c in info.classes if c.name == "User")
    assert "BaseModel" in user_cls.bases
    admin_cls = next(c for c in info.classes if c.name == "AdminUser")
    assert "User" in admin_cls.bases


def test_parse_implements():
    info = parse_file(os.path.join(FIXTURES, "models.ts"))
    base_cls = next(c for c in info.classes if c.name == "BaseModel")
    assert "Validatable" in base_cls.bases


def test_parse_methods():
    info = parse_file(os.path.join(FIXTURES, "models.ts"))
    user_cls = next(c for c in info.classes if c.name == "User")
    method_names = [m.name for m in user_cls.methods]
    assert "constructor" in method_names
    assert "greet" in method_names


def test_parse_es_imports():
    info = parse_file(os.path.join(FIXTURES, "app.ts"))
    assert len(info.imports) >= 2
    all_names = []
    for imp in info.imports:
        all_names.extend(imp.names)
    assert "parseConfig" in all_names
    assert "User" in all_names


def test_parse_import_module_source():
    info = parse_file(os.path.join(FIXTURES, "app.ts"))
    modules = [imp.module for imp in info.imports]
    assert "./config" in modules
    assert "./models" in modules


def test_parse_variables():
    info = parse_file(os.path.join(FIXTURES, "config.ts"))
    var_names = [v.name for v in info.variables]
    assert "DEFAULT_PORT" in var_names
    assert "CONFIG_PATH" in var_names
