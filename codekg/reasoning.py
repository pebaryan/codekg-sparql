"""OWL-RL reasoning over the code knowledge graph using owlrl."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rdflib import Graph
    from .store import CodeStore

ONTOLOGY_PATH = Path(__file__).parent.parent / "ontology" / "code.ttl"
INFERRED_GRAPH_URI = "https://codekg.dev/entity/_inferred#graph"


def apply_reasoning(code_store: "CodeStore") -> "Graph":
    """Apply OWL-RL + RDFS deductive closure to the store's triples.

    Merges all named graphs into a flat rdflib Graph, loads the ontology
    axioms (so the reasoner sees subClassOf, domain, range etc.), then runs
    owlrl in-place.

    Returns:
        rdflib.Graph containing original triples plus all inferred triples.
    """
    try:
        import owlrl
    except ImportError as exc:
        raise ImportError(
            "owlrl is required for OWL-RL reasoning. "
            "Install it with: pip install owlrl"
        ) from exc

    from rdflib import Graph
    from .shacl import _store_to_rdflib

    # Flatten all named graphs into a single rdflib Graph for owlrl
    g = Graph()
    for triple in _store_to_rdflib(code_store).triples((None, None, None)):
        g.add(triple)

    # Ontology axioms must be present so the reasoner can apply them
    g.parse(str(ONTOLOGY_PATH), format="turtle")

    owlrl.DeductiveClosure(owlrl.RDFS_OWLRL_Semantics).expand(g)

    return g


def write_inferred_to_store(code_store: "CodeStore") -> int:
    """Apply OWL-RL reasoning and write novel inferred triples back to the store.

    Inferred triples land in the named graph
    <https://codekg.dev/entity/_inferred#graph>, which is cleared and
    recomputed on each call so the result stays idempotent.

    After calling this, SPARQL queries against the store will see inferred
    triples — for example, querying for code:Function will also return
    code:Method instances (via the subClassOf entailment).

    Returns:
        Number of new triples written.
    """
    import pyoxigraph as ox
    from rdflib import URIRef, Literal, BNode

    def _to_ox(term):
        if isinstance(term, URIRef):
            # owlrl may emit triples with invalid IRI characters (<, >)
            # used for internal syntax; skip them silently.
            s = str(term)
            if "<" in s or ">" in s:
                return None
            return ox.NamedNode(s)
        if isinstance(term, Literal):
            # owlrl sometimes creates Literal subjects; these aren't valid
            # for pyoxigraph (subject must be NamedNode or BlankNode).
            # Skip them by returning None.
            if term.datatype:
                return ox.Literal(str(term), datatype=ox.NamedNode(str(term.datatype)))
            if term.language:
                return ox.Literal(str(term), language=term.language)
            return ox.Literal(str(term))
        return ox.BlankNode(str(term))  # BNode

    # Snapshot existing triples for deduplication
    existing = frozenset(
        (str(q.subject), str(q.predicate), str(q.object))
        for q in code_store._store.quads_for_pattern(None, None, None, None)
    )

    # Clear any previously written inferred triples
    code_store.clear_graph(INFERRED_GRAPH_URI)
    inferred_graph = ox.NamedNode(INFERRED_GRAPH_URI)

    reasoned = apply_reasoning(code_store)

    quads = [
        (_to_ox(s), _to_ox(p), _to_ox(o), inferred_graph)
        for s, p, o in reasoned
        if (str(s), str(p), str(o)) not in existing
        and not isinstance(s, Literal)  # pyoxigraph subjects must be IRI/BNode
    ]

    # Filter out triples where any component was skipped (invalid IRI)
    # or where the subject is a Literal (not valid for pyoxigraph)
    quads = [q for q in quads if all(c is not None for c in q[:3])]

    code_store.load_triples(quads)
    return len(quads)
