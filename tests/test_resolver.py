"""Tests for call resolution."""

import os

from codekg.store import CodeStore
from codekg.indexer import index_directory
from codekg.resolver import resolve_calls
from codekg import queries as Q

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


def _indexed_store(resolve=False) -> CodeStore:
    store = CodeStore()
    index_directory(FIXTURES, store, extensions=(".py",), resolve=resolve)
    return store


def test_resolve_returns_count():
    store = _indexed_store()
    count = resolve_calls(store)
    assert count > 0


def test_resolve_direct_call():
    """create_app calls parse_config, which should resolve to config.py#Function.parse_config."""
    store = _indexed_store()
    resolve_calls(store)

    sparql = """
    PREFIX code: <https://codekg.dev/ontology#>
    SELECT ?caller ?callee WHERE {
        ?caller code:resolvedCalls ?callee .
        ?caller code:name "create_app" .
        ?callee code:name "parse_config" .
    }
    """
    results = store.query(sparql)
    assert len(results) >= 1
    assert "parse_config" in results[0]["callee"]


def test_resolve_keeps_literal():
    """Original code:calls literal triples should still exist."""
    store = _indexed_store()
    resolve_calls(store)

    sparql = """
    PREFIX code: <https://codekg.dev/ontology#>
    SELECT ?target WHERE {
        ?func code:name "create_app" .
        ?func code:calls ?target .
    }
    """
    results = store.query(sparql)
    targets = [r["target"] for r in results]
    assert any("parse_config" in t for t in targets)


def test_resolve_same_file_call():
    """handle_request calls process_action in the same file."""
    store = _indexed_store()
    resolve_calls(store)

    sparql = """
    PREFIX code: <https://codekg.dev/ontology#>
    SELECT ?callee WHERE {
        ?caller code:name "handle_request" .
        ?caller code:resolvedCalls ?callee .
        ?callee code:name "process_action" .
    }
    """
    results = store.query(sparql)
    assert len(results) >= 1


def test_resolve_unresolvable():
    """Calls to builtins like print should not create resolvedCalls triples."""
    store = _indexed_store()
    resolve_calls(store)

    sparql = """
    PREFIX code: <https://codekg.dev/ontology#>
    SELECT ?callee WHERE {
        ?caller code:resolvedCalls ?callee .
        ?callee code:name "print" .
    }
    """
    results = store.query(sparql)
    assert len(results) == 0


def test_callers_of_uses_resolved():
    """callers_of should return results via resolvedCalls."""
    store = _indexed_store(resolve=True)
    results = Q.callers_of(store, "parse_config")
    caller_names = [r["callerName"] for r in results]
    assert "create_app" in caller_names


def test_impact_transitive():
    """impact_of should find transitive callers via resolvedCalls property paths.

    Chain: main -> create_app -> parse_config
    So impact_of("parse_config") should include both create_app and main.
    """
    store = _indexed_store(resolve=True)
    results = Q.impact_of(store, "parse_config")
    caller_names = [r["callerName"] for r in results]
    assert "create_app" in caller_names
    assert "main" in caller_names
