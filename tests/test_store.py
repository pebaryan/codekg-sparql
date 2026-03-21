"""Tests for the Oxigraph store wrapper."""

import pyoxigraph as ox

from codekg.store import CodeStore


def _make_quad():
    s = ox.NamedNode("http://example.org/s")
    p = ox.NamedNode("http://example.org/p")
    o = ox.Literal("hello")
    g = ox.NamedNode("http://example.org/graph")
    return (s, p, o, g)


def test_store_in_memory():
    store = CodeStore()
    assert store.stats()["total_triples"] == 0


def test_load_and_query():
    store = CodeStore()
    s, p, o, g = _make_quad()
    store.load_triples([(s, p, o, g)])
    results = store.query("SELECT ?o WHERE { ?s <http://example.org/p> ?o }")
    assert len(results) == 1
    assert results[0]["o"] == "hello"


def test_clear_graph():
    store = CodeStore()
    s, p, o, g = _make_quad()
    store.load_triples([(s, p, o, g)])
    assert store.stats()["total_triples"] == 1
    store.clear_graph("http://example.org/graph")
    assert store.stats()["total_triples"] == 0


def test_clear_all():
    store = CodeStore()
    s, p, o, g = _make_quad()
    store.load_triples([(s, p, o, g)])
    store.clear()
    assert store.stats()["total_triples"] == 0
