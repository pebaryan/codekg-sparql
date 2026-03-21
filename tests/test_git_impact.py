"""Tests for git impact analysis module."""

import os

from codekg.store import CodeStore
from codekg.indexer import index_directory
from codekg.git_impact import _parse_diff_stat, _entities_at_lines

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


def _indexed_store() -> CodeStore:
    store = CodeStore()
    index_directory(FIXTURES, store, extensions=(".py",), resolve=False)
    return store


# --- Diff parsing ---

def test_parse_diff_stat_basic():
    diff = """\
diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -10,3 +10,4 @@ def parse_config(path: str) -> dict:
     settings = {}
     raw = Path(path).read_text()
     settings["raw"] = raw
+    settings["extra"] = True
"""
    result = _parse_diff_stat(diff)
    assert len(result) == 1
    assert result[0]["file"] == "config.py"
    assert result[0]["hunks"][0]["start"] == 10
    assert result[0]["hunks"][0]["count"] == 4


def test_parse_diff_stat_multiple_files():
    diff = """\
diff --git a/config.py b/config.py
--- a/config.py
+++ b/config.py
@@ -1,2 +1,3 @@
 line1
+added
 line2
diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -5,1 +5,2 @@
 something
+else
"""
    result = _parse_diff_stat(diff)
    assert len(result) == 2
    assert result[0]["file"] == "config.py"
    assert result[1]["file"] == "app.py"


def test_parse_diff_stat_empty():
    result = _parse_diff_stat("")
    assert result == []


def test_parse_diff_single_line_hunk():
    diff = """\
+++ b/file.py
@@ -0,0 +1 @@
+new line
"""
    result = _parse_diff_stat(diff)
    assert len(result) == 1
    assert result[0]["hunks"][0]["start"] == 1
    assert result[0]["hunks"][0]["count"] == 1


# --- Entity mapping ---

def test_entities_at_lines():
    store = _indexed_store()
    # parse_config starts at line 10 in config.py
    entities = _entities_at_lines(store, "config.py", [{"start": 10, "count": 5}])
    names = [e.get("name") for e in entities]
    assert "parse_config" in names


def test_entities_at_lines_no_overlap():
    store = _indexed_store()
    # Line 1000 doesn't overlap with anything
    entities = _entities_at_lines(store, "config.py", [{"start": 1000, "count": 1}])
    assert entities == []


def test_entities_at_lines_multiple_hunks():
    store = _indexed_store()
    # Two hunks, one in parse_config range, one in validate_config range
    entities = _entities_at_lines(store, "config.py", [
        {"start": 10, "count": 3},
        {"start": 18, "count": 3},
    ])
    names = [e.get("name") for e in entities]
    assert "parse_config" in names
    assert "validate_config" in names
