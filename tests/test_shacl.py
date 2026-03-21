"""Tests for SHACL validation (requires pyshacl to be installed)."""

import os

import pyoxigraph as ox
import pytest

from codekg.store import CodeStore
from codekg.parser import parse_file
from codekg.triples import module_to_quads

pytest.importorskip("pyshacl")

from codekg.shacl import validate  # noqa: E402 — import after skip guard

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")

CODE = "https://codekg.dev/ontology#"
ENTITY = "https://codekg.dev/entity/"
GRAPH = ox.NamedNode(f"{ENTITY}test.py#graph")
RDF_TYPE = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
XSD_STR = ox.NamedNode("http://www.w3.org/2001/XMLSchema#string")
XSD_INT = ox.NamedNode("http://www.w3.org/2001/XMLSchema#integer")


def _nn(uri: str) -> ox.NamedNode:
    return ox.NamedNode(uri)


def _lit(s: str) -> ox.Literal:
    return ox.Literal(s, datatype=XSD_STR)


def _lit_int(n: int) -> ox.Literal:
    return ox.Literal(str(n), datatype=XSD_INT)


def _valid_store() -> CodeStore:
    """Build a store from the sample project — should pass all shapes."""
    store = CodeStore()
    for filename in ("config.py", "models.py", "app.py"):
        info = parse_file(os.path.join(FIXTURES, filename))
        store.load_triples(module_to_quads(info, filename))
    return store


def _function_quads(name: str, extra: list = None) -> list:
    func = _nn(f"{ENTITY}test.py#Function.{name}")
    quads = [
        (func, RDF_TYPE, _nn(f"{CODE}Function"), GRAPH),
        (func, _nn(f"{CODE}name"), _lit(name), GRAPH),
        (func, _nn(f"{CODE}startLine"), _lit_int(1), GRAPH),
        (func, _nn(f"{CODE}endLine"), _lit_int(5), GRAPH),
    ]
    if extra:
        quads.extend(extra)
    return quads


# ---------------------------------------------------------------------------
# Use case 1 — Parser output validation
# ---------------------------------------------------------------------------

def test_valid_store_conforms():
    conforms, report = validate(_valid_store())
    assert conforms, f"Expected conformance but got violations:\n{report}"


def test_function_missing_name_fails():
    store = CodeStore()
    func = _nn(f"{ENTITY}test.py#Function.broken")
    store.load_triples([
        (func, RDF_TYPE, _nn(f"{CODE}Function"), GRAPH),
        (func, _nn(f"{CODE}startLine"), _lit_int(1), GRAPH),
        (func, _nn(f"{CODE}endLine"), _lit_int(5), GRAPH),
    ])
    conforms, report = validate(store)
    assert not conforms
    assert "name" in report.lower()


def test_function_missing_start_line_fails():
    store = CodeStore()
    func = _nn(f"{ENTITY}test.py#Function.broken")
    store.load_triples([
        (func, RDF_TYPE, _nn(f"{CODE}Function"), GRAPH),
        (func, _nn(f"{CODE}name"), _lit("broken"), GRAPH),
        (func, _nn(f"{CODE}endLine"), _lit_int(5), GRAPH),
    ])
    conforms, report = validate(store)
    assert not conforms
    assert "startline" in report.lower()


def test_class_missing_end_line_fails():
    store = CodeStore()
    cls = _nn(f"{ENTITY}test.py#Class.Incomplete")
    store.load_triples([
        (cls, RDF_TYPE, _nn(f"{CODE}Class"), GRAPH),
        (cls, _nn(f"{CODE}name"), _lit("Incomplete"), GRAPH),
        (cls, _nn(f"{CODE}startLine"), _lit_int(10), GRAPH),
    ])
    conforms, report = validate(store)
    assert not conforms
    assert "endline" in report.lower()


def test_parameter_missing_name_fails():
    store = CodeStore()
    param = _nn(f"{ENTITY}test.py#Parameter.fn.nameless")
    store.load_triples([
        (param, RDF_TYPE, _nn(f"{CODE}Parameter"), GRAPH),
    ])
    conforms, report = validate(store)
    assert not conforms
    assert "name" in report.lower()


# ---------------------------------------------------------------------------
# Use case 2 — Method covered by FunctionShape via RDFS subClassOf inference
# ---------------------------------------------------------------------------

def test_method_covered_by_function_shape():
    """Method subClassOf Function — missing required props should fail FunctionShape."""
    store = CodeStore()
    method = _nn(f"{ENTITY}test.py#Method.MyClass.bad_method")
    store.load_triples([
        (method, RDF_TYPE, _nn(f"{CODE}Method"), GRAPH),
        # deliberately missing name, startLine, endLine
    ])
    conforms, report = validate(store)
    assert not conforms
    assert "name" in report.lower()


# ---------------------------------------------------------------------------
# Use case 2 — Domain/range enforcement
# ---------------------------------------------------------------------------

def test_file_path_on_non_module_fails():
    """code:filePath domain is code:Module — a Function carrying it should fail."""
    store = CodeStore()
    store.load_triples(
        _function_quads("orphan", extra=[
            (_nn(f"{ENTITY}test.py#Function.orphan"), _nn(f"{CODE}filePath"), _lit("test.py"), GRAPH),
        ])
    )
    conforms, report = validate(store)
    assert not conforms


def test_inherits_from_on_non_class_fails():
    """code:inheritsFrom domain is code:Class — a Function using it should fail."""
    store = CodeStore()
    store.load_triples(
        _function_quads("pretender", extra=[
            (_nn(f"{ENTITY}test.py#Function.pretender"), _nn(f"{CODE}inheritsFrom"), _lit("Base"), GRAPH),
        ])
    )
    conforms, report = validate(store)
    assert not conforms


def test_has_parameter_range_must_be_parameter():
    """code:hasParameter range is code:Parameter — linking to a non-Parameter should fail."""
    store = CodeStore()
    func = _nn(f"{ENTITY}test.py#Function.fn")
    non_param = _nn(f"{ENTITY}test.py#Function.other")  # a Function, not a Parameter
    store.load_triples(
        _function_quads("fn") + _function_quads("other") + [
            (func, _nn(f"{CODE}hasParameter"), non_param, GRAPH),
        ]
    )
    conforms, report = validate(store)
    assert not conforms


# ---------------------------------------------------------------------------
# Use case 3 — Dangling resolvedCalls
# ---------------------------------------------------------------------------

def test_resolved_calls_literal_fails():
    """resolvedCalls must link to an IRI, not a string literal."""
    store = CodeStore()
    store.load_triples(
        _function_quads("caller", extra=[
            (_nn(f"{ENTITY}test.py#Function.caller"), _nn(f"{CODE}resolvedCalls"), _lit("some_fn"), GRAPH),
        ])
    )
    conforms, report = validate(store)
    assert not conforms


def test_resolved_calls_valid_iri_conforms():
    """resolvedCalls pointing to a valid code:Function IRI should pass."""
    store = CodeStore()
    caller = _nn(f"{ENTITY}test.py#Function.caller")
    callee = _nn(f"{ENTITY}test.py#Function.callee")
    store.load_triples(
        _function_quads("caller") + _function_quads("callee") + [
            (caller, _nn(f"{CODE}resolvedCalls"), callee, GRAPH),
        ]
    )
    conforms, report = validate(store)
    assert conforms, f"Expected conformance but got:\n{report}"


def test_raise_on_violation():
    """raise_on_violation=True should raise ValueError on failure."""
    store = CodeStore()
    func = _nn(f"{ENTITY}test.py#Function.broken")
    store.load_triples([
        (func, RDF_TYPE, _nn(f"{CODE}Function"), GRAPH),
        # missing name, startLine, endLine
    ])
    with pytest.raises(ValueError, match="SHACL validation failed"):
        validate(store, raise_on_violation=True)
