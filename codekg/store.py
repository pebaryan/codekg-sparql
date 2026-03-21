"""Oxigraph-based RDF store wrapper."""

from pathlib import Path
from typing import Optional

import pyoxigraph as ox
from rdflib import URIRef

from .ontology import CODE


class CodeStore:
    """Wrapper around pyoxigraph for storing and querying code knowledge graphs."""

    def __init__(self, path: Optional[str] = None):
        """Initialize the store.

        Args:
            path: Directory for persistent storage. None for in-memory store.
        """
        if path:
            Path(path).mkdir(parents=True, exist_ok=True)
            self._store = ox.Store(path)
        else:
            self._store = ox.Store()

    def load_triples(self, quads: list[tuple]) -> int:
        """Bulk insert RDF quads into the store.

        Each quad is (subject, predicate, object, graph_name).
        All values should be pyoxigraph terms.

        Returns the number of quads inserted.
        """
        count = 0
        for s, p, o, g in quads:
            self._store.add(ox.Quad(s, p, o, g))
            count += 1
        return count

    def query(self, sparql: str) -> list[dict]:
        """Execute a SPARQL SELECT query and return results as list of dicts."""
        results = self._store.query(sparql, use_default_graph_as_union=True)
        rows = []
        for solution in results:
            row = {}
            for var in results.variables:
                val = solution[var]
                if val is not None:
                    # Variable names come as "?name", strip the "?"
                    key = str(var).lstrip("?")
                    if isinstance(val, ox.Literal):
                        row[key] = val.value
                    else:
                        row[key] = str(val)
            rows.append(row)
        return rows

    def query_raw(self, sparql: str):
        """Execute a SPARQL query and return the raw pyoxigraph result."""
        return self._store.query(sparql, use_default_graph_as_union=True)

    def clear_graph(self, graph_uri: str):
        """Remove all triples in a named graph (used for re-indexing a file)."""
        graph = ox.NamedNode(graph_uri) if isinstance(graph_uri, str) else graph_uri
        for quad in self._store.quads_for_pattern(None, None, None, graph):
            self._store.remove(quad)

    def update(self, sparql: str):
        """Execute a SPARQL UPDATE (INSERT/DELETE) operation."""
        self._store.update(sparql)

    def clear(self):
        """Remove all triples from the store."""
        for quad in self._store.quads_for_pattern(None, None, None, None):
            self._store.remove(quad)

    def stats(self) -> dict:
        """Return store statistics."""
        total = len(list(self._store.quads_for_pattern(None, None, None, None)))

        type_pred = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")

        def count_type(type_uri: str) -> int:
            node = ox.NamedNode(type_uri)
            return len(list(self._store.quads_for_pattern(None, type_pred, node, None)))

        return {
            "total_triples": total,
            "modules": count_type(str(CODE.Module)),
            "classes": count_type(str(CODE.Class)),
            "functions": count_type(str(CODE.Function)),
            "methods": count_type(str(CODE.Method)),
        }
