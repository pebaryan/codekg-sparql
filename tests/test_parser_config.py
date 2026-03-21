"""Tests for the JSON/YAML/TOML parser."""

import os
import pytest

from codekg.parser_config import parse_file

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_config")


# --- JSON tests ---

def test_json_top_level_keys():
    info = parse_file(os.path.join(FIXTURES, "config.json"))
    var_names = [v.name for v in info.variables]
    assert "name" in var_names
    assert "version" in var_names
    assert "debug" in var_names


def test_json_nested_object_as_class():
    info = parse_file(os.path.join(FIXTURES, "config.json"))
    class_names = [c.name for c in info.classes]
    assert "database" in class_names


def test_json_nested_keys():
    info = parse_file(os.path.join(FIXTURES, "config.json"))
    var_names = [v.name for v in info.variables]
    assert "database.host" in var_names
    assert "database.port" in var_names


# --- YAML tests ---

def test_yaml_top_level_keys():
    info = parse_file(os.path.join(FIXTURES, "config.yaml"))
    var_names = [v.name for v in info.variables]
    assert "name" in var_names
    assert "version" in var_names
    assert "debug" in var_names


def test_yaml_nested_mapping_as_class():
    info = parse_file(os.path.join(FIXTURES, "config.yaml"))
    class_names = [c.name for c in info.classes]
    assert "database" in class_names


def test_yaml_nested_keys():
    info = parse_file(os.path.join(FIXTURES, "config.yaml"))
    var_names = [v.name for v in info.variables]
    assert "database.host" in var_names
    assert "database.port" in var_names


# --- TOML tests ---

def test_toml_tables_as_classes():
    info = parse_file(os.path.join(FIXTURES, "config.toml"))
    class_names = [c.name for c in info.classes]
    assert "package" in class_names
    assert "database" in class_names
    assert "database.options" in class_names


def test_toml_keys():
    info = parse_file(os.path.join(FIXTURES, "config.toml"))
    var_names = [v.name for v in info.variables]
    assert "package.name" in var_names
    assert "package.version" in var_names
    assert "database.host" in var_names
    assert "database.port" in var_names
    assert "database.options.ssl" in var_names
