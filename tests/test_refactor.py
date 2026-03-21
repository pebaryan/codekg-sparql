"""Tests for source-level refactoring operations."""

import os
import shutil
import pytest

from codekg.store import CodeStore
from codekg.indexer import index_directory
from codekg import refactor as R

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


def _setup(tmp_path):
    """Copy fixtures to tmp dir, index, return (store, root_path)."""
    dest = str(tmp_path / "project")
    shutil.copytree(FIXTURES, dest)
    store = CodeStore()
    index_directory(dest, store, extensions=(".py",), resolve=False)
    return store, dest


# --- rename_symbol ---

def test_rename_definition(tmp_path):
    """Renaming a function updates its definition."""
    store, root = _setup(tmp_path)
    result = R.rename_symbol(store, root, "parse_config", "load_config")
    assert result["occurrences"] > 0
    assert len(result["files_modified"]) >= 1

    # The function definition should now use the new name
    config_py = os.path.join(root, "config.py")
    source = open(config_py).read()
    assert "def load_config" in source
    assert "def parse_config" not in source


def test_preview_rename(tmp_path):
    """Preview shows diff without modifying files."""
    store, root = _setup(tmp_path)
    result = R.preview_rename(store, root, "parse_config", "load_config")
    assert result["total_occurrences"] > 0
    assert len(result["files"]) >= 1
    assert "parse_config" in result["diff"]
    assert "load_config" in result["diff"]

    # Files should NOT be modified
    config_py = os.path.join(root, "config.py")
    source = open(config_py).read()
    assert "def parse_config" in source  # still the old name


def test_rename_caller(tmp_path):
    """Renaming a function updates call sites in other files."""
    store, root = _setup(tmp_path)
    R.rename_symbol(store, root, "parse_config", "load_config")

    app_py = os.path.join(root, "app.py")
    source = open(app_py).read()
    assert "load_config" in source
    assert "parse_config" not in source


def test_rename_updates_kg(tmp_path):
    """After rename + reindex, KG reflects the new name."""
    store, root = _setup(tmp_path)
    R.rename_symbol(store, root, "parse_config", "load_config", reindex=True)

    results = store.query("""
        PREFIX code: <https://codekg.dev/ontology#>
        SELECT ?name WHERE { ?e code:name "load_config" }
    """)
    assert len(results) > 0

    results = store.query("""
        PREFIX code: <https://codekg.dev/ontology#>
        SELECT ?name WHERE { ?e code:name "parse_config" }
    """)
    assert len(results) == 0


def test_rename_no_match(tmp_path):
    """Renaming a non-existent symbol returns empty result."""
    store, root = _setup(tmp_path)
    result = R.rename_symbol(store, root, "nonexistent_xyz", "new_name")
    assert result["occurrences"] == 0
    assert result["files_modified"] == []


def test_rename_no_substring_match(tmp_path):
    """Rename should not match substrings (e.g. renaming 'get' should not affect 'get_all')."""
    store, root = _setup(tmp_path)
    # Write a file with similar names
    test_file = os.path.join(root, "similar.py")
    with open(test_file, "w") as f:
        f.write("def get():\n    pass\n\ndef get_all():\n    return get()\n")
    index_directory(root, store, extensions=(".py",), resolve=False)

    R.rename_symbol(store, root, "get", "fetch")

    source = open(test_file).read()
    assert "def fetch():" in source
    assert "def get_all():" in source  # not renamed
    assert "return fetch()" in source


# --- insert_code ---

def test_insert_code_after(tmp_path):
    store, root = _setup(tmp_path)
    config_py = os.path.join(root, "config.py")
    R.insert_code(config_py, 1, "# inserted comment")
    lines = open(config_py).readlines()
    assert any("# inserted comment" in l for l in lines)


def test_insert_code_before(tmp_path):
    store, root = _setup(tmp_path)
    config_py = os.path.join(root, "config.py")
    R.insert_code(config_py, 1, "# before first line", position="before")
    lines = open(config_py).readlines()
    assert "# before first line" in lines[0]


# --- replace_lines ---

def test_replace_lines(tmp_path):
    store, root = _setup(tmp_path)
    config_py = os.path.join(root, "config.py")
    original_lines = open(config_py).readlines()
    n = len(original_lines)
    result = R.replace_lines(config_py, 1, 1, "# replaced first line")
    assert result["lines_removed"] == 1
    assert result["lines_added"] == 1
    lines = open(config_py).readlines()
    assert "# replaced first line" in lines[0]


# --- replace_entity ---

def test_replace_entity(tmp_path):
    store, root = _setup(tmp_path)
    new_code = 'def parse_config(path):\n    return {"replaced": True}\n'
    result = R.replace_entity(store, root, "parse_config", new_code)
    assert result["entity"] == "parse_config"
    assert result["lines_removed"] >= 1
    assert result["lines_added"] >= 1

    config_py = os.path.join(root, "config.py")
    source = open(config_py).read()
    assert '{"replaced": True}' in source


def test_replace_entity_not_found(tmp_path):
    store, root = _setup(tmp_path)
    with pytest.raises(ValueError, match="Entity not found"):
        R.replace_entity(store, root, "nonexistent_xyz", "pass")


# --- add_function ---

def test_add_function_at_end(tmp_path):
    store, root = _setup(tmp_path)
    code = "def new_helper():\n    return 42\n"
    result = R.add_function(store, root, "config.py", code)

    config_py = os.path.join(root, "config.py")
    source = open(config_py).read()
    assert "def new_helper():" in source


def test_add_function_after_entity(tmp_path):
    store, root = _setup(tmp_path)
    code = "def helper():\n    pass\n"
    result = R.add_function(store, root, "config.py", code, after_entity="parse_config")

    config_py = os.path.join(root, "config.py")
    source = open(config_py).read()
    assert "def helper():" in source


def test_add_function_at_line(tmp_path):
    store, root = _setup(tmp_path)
    code = "def at_line_func():\n    pass\n"
    result = R.add_function(store, root, "config.py", code, at_line=1)

    config_py = os.path.join(root, "config.py")
    source = open(config_py).read()
    assert "def at_line_func():" in source
