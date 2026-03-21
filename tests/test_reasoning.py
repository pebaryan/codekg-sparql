"""Tests for OWL-RL reasoning (requires owlrl to be installed)."""

import os

import pytest

from codekg.store import CodeStore
from codekg.parser import parse_file
from codekg.triples import module_to_quads

pytest.importorskip("owlrl")

from codekg.reasoning import apply_reasoning, write_inferred_to_store  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")

CODE = "https://codekg.dev/ontology#"
RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def _sample_store() -> CodeStore:
    store = CodeStore()
    for filename in ("config.py", "models.py", "app.py"):
        info = parse_file(os.path.join(FIXTURES, filename))
        store.load_triples(module_to_quads(info, filename))
    return store


# ---------------------------------------------------------------------------
# apply_reasoning
# ---------------------------------------------------------------------------

def test_apply_reasoning_returns_graph():
    from rdflib import Graph
    g = apply_reasoning(_sample_store())
    assert isinstance(g, Graph)
    assert len(g) > 0


def test_method_inferred_as_function():
    """Method subClassOf Function — owlrl must entail all Methods as Functions."""
    from rdflib import URIRef

    g = apply_reasoning(_sample_store())

    FUNCTION = URIRef(f"{CODE}Function")
    METHOD = URIRef(f"{CODE}Method")
    TYPE = URIRef(RDF_TYPE)

    methods = {s for s, p, o in g if p == TYPE and o == METHOD}
    assert methods, "Expected at least one Method in the sample project"

    functions = {s for s, p, o in g if p == TYPE and o == FUNCTION}
    assert methods.issubset(functions), (
        f"Methods not inferred as Function: {methods - functions}"
    )


def test_domain_inference_filePath():
    """rdfs:domain code:Module on filePath — subjects should be inferred as Modules."""
    from rdflib import URIRef

    g = apply_reasoning(_sample_store())

    FILE_PATH = URIRef(f"{CODE}filePath")
    MODULE = URIRef(f"{CODE}Module")
    TYPE = URIRef(RDF_TYPE)

    fp_subjects = {s for s, p, o in g if p == FILE_PATH}
    assert fp_subjects

    modules = {s for s, p, o in g if p == TYPE and o == MODULE}
    assert fp_subjects.issubset(modules)


def test_range_inference_resolved_calls():
    """rdfs:range code:Function on resolvedCalls — objects should be inferred as Functions."""
    from rdflib import URIRef
    import pyoxigraph as ox

    store = _sample_store()

    # Manually add a resolvedCalls triple so we have something to reason over
    ENTITY = "https://codekg.dev/entity/"
    GRAPH = ox.NamedNode(f"{ENTITY}test.py#graph")
    XSD_STR = ox.NamedNode("http://www.w3.org/2001/XMLSchema#string")
    XSD_INT = ox.NamedNode("http://www.w3.org/2001/XMLSchema#integer")
    OX_TYPE = ox.NamedNode(RDF_TYPE)

    caller = ox.NamedNode(f"{ENTITY}test.py#Function.caller")
    callee = ox.NamedNode(f"{ENTITY}test.py#Function.callee")
    store.load_triples([
        (caller, OX_TYPE, ox.NamedNode(f"{CODE}Function"), GRAPH),
        (caller, ox.NamedNode(f"{CODE}name"), ox.Literal("caller", datatype=XSD_STR), GRAPH),
        (caller, ox.NamedNode(f"{CODE}startLine"), ox.Literal("1", datatype=XSD_INT), GRAPH),
        (caller, ox.NamedNode(f"{CODE}endLine"), ox.Literal("3", datatype=XSD_INT), GRAPH),
        (callee, OX_TYPE, ox.NamedNode(f"{CODE}Function"), GRAPH),
        (callee, ox.NamedNode(f"{CODE}name"), ox.Literal("callee", datatype=XSD_STR), GRAPH),
        (callee, ox.NamedNode(f"{CODE}startLine"), ox.Literal("5", datatype=XSD_INT), GRAPH),
        (callee, ox.NamedNode(f"{CODE}endLine"), ox.Literal("7", datatype=XSD_INT), GRAPH),
        (caller, ox.NamedNode(f"{CODE}resolvedCalls"), callee, GRAPH),
    ])

    g = apply_reasoning(store)

    RESOLVED_CALLS = URIRef(f"{CODE}resolvedCalls")
    FUNCTION = URIRef(f"{CODE}Function")
    TYPE = URIRef(RDF_TYPE)

    call_objects = {o for s, p, o in g if p == RESOLVED_CALLS}
    assert call_objects

    inferred_functions = {s for s, p, o in g if p == TYPE and o == FUNCTION}
    assert call_objects.issubset(inferred_functions)


# ---------------------------------------------------------------------------
# write_inferred_to_store
# ---------------------------------------------------------------------------

def test_write_inferred_adds_triples():
    store = _sample_store()
    before = store.stats()["total_triples"]
    n = write_inferred_to_store(store)
    assert n > 0
    assert store.stats()["total_triples"] == before + n


def test_write_inferred_idempotent():
    """Calling write_inferred_to_store twice should write the same count."""
    store = _sample_store()
    n1 = write_inferred_to_store(store)
    n2 = write_inferred_to_store(store)
    assert n1 == n2


def test_methods_queryable_as_functions_after_write():
    """After write_inferred_to_store, SPARQL for code:Function must return Methods too."""
    store = _sample_store()
    write_inferred_to_store(store)

    all_functions = {
        r["entity"] for r in store.query("""
            PREFIX code: <https://codekg.dev/ontology#>
            PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?entity WHERE { ?entity rdf:type code:Function . }
        """)
    }
    all_methods = {
        r["entity"] for r in store.query("""
            PREFIX code: <https://codekg.dev/ontology#>
            PREFIX rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            SELECT ?entity WHERE { ?entity rdf:type code:Method . }
        """)
    }

    assert all_methods, "Expected at least one Method in the sample project"
    assert all_methods.issubset(all_functions), (
        f"Methods not queryable as Functions: {all_methods - all_functions}"
    )
