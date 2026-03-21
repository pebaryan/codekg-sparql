"""Tests for SPARQL query templates."""

import os

from codekg.store import CodeStore
from codekg.indexer import index_directory
from codekg import queries as Q

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


def _indexed_store() -> CodeStore:
    store = CodeStore()
    index_directory(FIXTURES, store)
    return store


def test_callers_of():
    store = _indexed_store()
    results = Q.callers_of(store, "parse_config")
    caller_names = [r["callerName"] for r in results]
    assert "create_app" in caller_names


def test_callees_of():
    store = _indexed_store()
    results = Q.callees_of(store, "create_app")
    callees = [r["callee"] for r in results]
    assert any("parse_config" in c for c in callees)
    assert any("validate_config" in c for c in callees)


def test_functions_in():
    store = _indexed_store()
    results = Q.functions_in(store, "config.py")
    names = [r["name"] for r in results]
    assert "parse_config" in names
    assert "validate_config" in names


def test_search_by_name():
    store = _indexed_store()
    results = Q.search_by_name(store, "config")
    names = [r["name"] for r in results]
    assert any("config" in n.lower() for n in names)


def test_all_classes():
    store = _indexed_store()
    results = Q.all_classes(store)
    names = [r["name"] for r in results]
    assert "BaseModel" in names
    assert "User" in names
    assert "AdminUser" in names


def test_all_functions():
    store = _indexed_store()
    results = Q.all_functions(store)
    names = [r["name"] for r in results]
    assert "parse_config" in names
    assert "create_app" in names


def test_fuzzy_search_exact():
    store = _indexed_store()
    results = Q.fuzzy_search(store, "parse_config")
    names = [r["name"] for r in results]
    assert "parse_config" in names


def test_fuzzy_search_typo():
    store = _indexed_store()
    results = Q.fuzzy_search(store, "prase_config")  # transposed letters
    names = [r["name"] for r in results]
    assert "parse_config" in names


def test_fuzzy_search_partial():
    store = _indexed_store()
    results = Q.fuzzy_search(store, "config")
    # Should find parse_config and validate_config as substring matches (boosted)
    names = [r["name"] for r in results]
    assert any("config" in n for n in names)
    # Substring matches should be ranked first (score > 1.0 due to boost)
    assert results[0]["score"] > 1.0


def test_resolve_entity_by_name():
    store = _indexed_store()
    results = Q.resolve_entity(store, "parse_config")
    assert len(results) >= 1
    assert results[0]["name"] == "parse_config"
    assert results[0]["file"]  # has a file path


def test_resolve_entity_qualified():
    store = _indexed_store()
    results = Q.resolve_entity(store, "config.py:parse_config")
    assert len(results) >= 1
    assert "config.py" in results[0]["file"]


def test_resolve_entity_disambiguates():
    store = _indexed_store()
    # create_app is only in app.py
    all_results = Q.resolve_entity(store, "create_app")
    qualified = Q.resolve_entity(store, "app.py:create_app")
    assert len(qualified) == len(all_results)


def test_list_files():
    store = _indexed_store()
    results = Q.list_files(store)
    paths = [r["filePath"] for r in results]
    assert any("config.py" in p for p in paths)
    assert any("app.py" in p for p in paths)


def test_entities_in_file():
    store = _indexed_store()
    results = Q.entities_in_file(store, "config.py")
    names = [r["name"] for r in results]
    assert "parse_config" in names
    assert "validate_config" in names


def test_read_source():
    import os
    fixture = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project", "config.py")
    source = Q.read_source(fixture, 1, 3)
    lines = source.strip().split("\n")
    assert len(lines) == 3
    assert "1" in lines[0]  # line number present


def test_suggest_on_miss():
    store = _indexed_store()
    msg = Q._suggest_on_miss(store, "prase_config")
    assert "Entity not found" in msg
    assert "Did you mean" in msg
    assert "parse_config" in msg


def test_context_around():
    store = _indexed_store()
    ctx = Q.context_around(store, "create_app")
    assert len(ctx["function"]) > 0
    assert len(ctx["callees"]) > 0
