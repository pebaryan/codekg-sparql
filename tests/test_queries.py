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


def test_context_around():
    store = _indexed_store()
    ctx = Q.context_around(store, "create_app")
    assert len(ctx["function"]) > 0
    assert len(ctx["callees"]) > 0
