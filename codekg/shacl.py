"""SHACL validation for the code knowledge graph."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import CodeStore

SHAPES_PATH = Path(__file__).parent.parent / "ontology" / "shapes.ttl"
ONTOLOGY_PATH = Path(__file__).parent.parent / "ontology" / "code.ttl"


def _store_to_rdflib(code_store: "CodeStore"):
    """Convert a CodeStore's quads to an rdflib Graph for pyshacl."""
    import pyoxigraph as ox
    from rdflib import URIRef, Literal, BNode, Graph

    def _term(t):
        if isinstance(t, ox.NamedNode):
            # pyoxigraph str() wraps with <>, strip them for rdflib
            uri = str(t)
            if uri.startswith("<") and uri.endswith(">"):
                uri = uri[1:-1]
            return URIRef(uri)
        if isinstance(t, ox.Literal):
            if t.datatype:
                dt = str(t.datatype)
                if dt.startswith("<") and dt.endswith(">"):
                    dt = dt[1:-1]
                return Literal(t.value, datatype=URIRef(dt))
            if t.language:
                return Literal(t.value, lang=t.language)
            return Literal(t.value)
        return BNode(str(t))  # BlankNode

    g = Graph()
    for quad in code_store._store.quads_for_pattern(None, None, None, None):
        s = _term(quad.subject)
        p = URIRef(str(quad.predicate).strip("<>"))
        o = _term(quad.object)
        g.add((s, p, o))

    return g


def validate(code_store: "CodeStore", raise_on_violation: bool = False) -> tuple[bool, str]:
    """Validate the store against the SHACL shapes.

    RDFS inference is enabled so that code:Method (subClassOf code:Function)
    is automatically covered by shapes targeting code:Function.

    Args:
        code_store: CodeStore instance to validate.
        raise_on_violation: If True, raise ValueError when violations are found.

    Returns:
        (conforms, results_text) tuple.
    """
    try:
        from pyshacl import validate as _shacl_validate
    except ImportError as exc:
        raise ImportError(
            "pyshacl is required for SHACL validation. "
            "Install it with: pip install pyshacl"
        ) from exc

    data_graph = _store_to_rdflib(code_store)

    conforms, _, results_text = _shacl_validate(
        data_graph,
        shacl_graph=str(SHAPES_PATH),
        inference="none",
        serialize_report_graph=False,
    )

    if raise_on_violation and not conforms:
        raise ValueError(f"SHACL validation failed:\n{results_text}")

    return conforms, results_text
