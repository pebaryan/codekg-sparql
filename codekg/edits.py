"""Curated SPARQL UPDATE operations for editing the knowledge graph.

All user annotations are stored in a dedicated named graph
(ANNOTATIONS_GRAPH) so they survive file re-indexing.
"""

from .store import CodeStore
from .ontology import ANNOTATIONS_GRAPH

_PREFIX = """
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""

_GRAPH = str(ANNOTATIONS_GRAPH)


def _resolve_entity(store: CodeStore, name: str) -> str | None:
    """Find the URI of an entity by name. Returns None if not found."""
    results = store.query(_PREFIX + """
        SELECT ?entity WHERE {
            ?entity code:name "%s" .
        } LIMIT 1
    """ % name.replace('"', '\\"'))
    if results:
        uri = results[0].get("entity", "")
        return uri.strip("<>")
    return None


def _require_entity(store: CodeStore, name: str) -> str:
    """Resolve entity by name or raise ValueError with suggestions."""
    uri = _resolve_entity(store, name)
    if uri is None:
        from .queries import _suggest_on_miss
        raise ValueError(_suggest_on_miss(store, name))
    return uri


# --- Tag operations ---

def add_tag(store: CodeStore, entity_name: str, tag: str) -> str:
    """Add a tag to an entity.

    Returns the entity URI that was tagged.
    """
    uri = _require_entity(store, entity_name)
    store.update(_PREFIX + """
        INSERT DATA {
            GRAPH <%s> {
                <%s> code:tag "%s" .
            }
        }
    """ % (_GRAPH, uri, tag.replace('"', '\\"')))
    return uri


def remove_tag(store: CodeStore, entity_name: str, tag: str) -> str:
    """Remove a tag from an entity.

    Returns the entity URI that was untagged.
    """
    uri = _require_entity(store, entity_name)
    store.update(_PREFIX + """
        DELETE DATA {
            GRAPH <%s> {
                <%s> code:tag "%s" .
            }
        }
    """ % (_GRAPH, uri, tag.replace('"', '\\"')))
    return uri


def list_tags(store: CodeStore, entity_name: str | None = None) -> list[dict]:
    """List tags. If entity_name given, list tags for that entity only."""
    if entity_name:
        uri = _require_entity(store, entity_name)
        return store.query(_PREFIX + """
            SELECT ?tag WHERE {
                GRAPH <%s> { <%s> code:tag ?tag }
            }
        """ % (_GRAPH, uri))
    else:
        return store.query(_PREFIX + """
            SELECT ?entity ?name ?tag WHERE {
                GRAPH <%s> { ?entity code:tag ?tag }
                ?entity code:name ?name .
            }
            ORDER BY ?name ?tag
        """ % _GRAPH)


# --- Note operations ---

def add_note(store: CodeStore, entity_name: str, note: str) -> str:
    """Add a note to an entity.

    Returns the entity URI.
    """
    uri = _require_entity(store, entity_name)
    store.update(_PREFIX + """
        INSERT DATA {
            GRAPH <%s> {
                <%s> code:note "%s" .
            }
        }
    """ % (_GRAPH, uri, note.replace('"', '\\"').replace('\n', '\\n')))
    return uri


def remove_note(store: CodeStore, entity_name: str, note: str) -> str:
    """Remove a specific note from an entity.

    Returns the entity URI.
    """
    uri = _require_entity(store, entity_name)
    store.update(_PREFIX + """
        DELETE DATA {
            GRAPH <%s> {
                <%s> code:note "%s" .
            }
        }
    """ % (_GRAPH, uri, note.replace('"', '\\"').replace('\n', '\\n')))
    return uri


def list_notes(store: CodeStore, entity_name: str | None = None) -> list[dict]:
    """List notes. If entity_name given, list notes for that entity only."""
    if entity_name:
        uri = _require_entity(store, entity_name)
        return store.query(_PREFIX + """
            SELECT ?note WHERE {
                GRAPH <%s> { <%s> code:note ?note }
            }
        """ % (_GRAPH, uri))
    else:
        return store.query(_PREFIX + """
            SELECT ?entity ?name ?note WHERE {
                GRAPH <%s> { ?entity code:note ?note }
                ?entity code:name ?name .
            }
            ORDER BY ?name
        """ % _GRAPH)


# --- Link operations ---

def add_link(store: CodeStore, from_name: str, to_name: str, label: str = "") -> tuple[str, str]:
    """Create a directed link between two entities.

    Returns (from_uri, to_uri).
    """
    from_uri = _require_entity(store, from_name)
    to_uri = _require_entity(store, to_name)
    sparql = _PREFIX + """
        INSERT DATA {
            GRAPH <%s> {
                <%s> code:linksTo <%s> .
    """ % (_GRAPH, from_uri, to_uri)
    if label:
        # Store the label as a property on the source entity scoped by the link.
        # For simplicity, we use a triple: source code:linkLabel "label->target"
        label_val = f"{label}->{to_name}".replace('"', '\\"')
        sparql += '            <%s> code:linkLabel "%s" .\n' % (from_uri, label_val)
    sparql += """
            }
        }
    """
    store.update(sparql)
    return from_uri, to_uri


def remove_link(store: CodeStore, from_name: str, to_name: str) -> tuple[str, str]:
    """Remove a directed link between two entities.

    Returns (from_uri, to_uri).
    """
    from_uri = _require_entity(store, from_name)
    to_uri = _require_entity(store, to_name)
    # Remove the linksTo triple and any associated linkLabel
    store.update(_PREFIX + """
        DELETE {
            GRAPH <%s> {
                <%s> code:linksTo <%s> .
                <%s> code:linkLabel ?label .
            }
        }
        WHERE {
            GRAPH <%s> {
                <%s> code:linksTo <%s> .
                OPTIONAL {
                    <%s> code:linkLabel ?label .
                    FILTER(STRENDS(?label, "->%s"))
                }
            }
        }
    """ % (_GRAPH, from_uri, to_uri, from_uri,
           _GRAPH, from_uri, to_uri, from_uri,
           to_name.replace('"', '\\"')))
    return from_uri, to_uri


def list_links(store: CodeStore, entity_name: str | None = None) -> list[dict]:
    """List links. If entity_name given, list links from/to that entity."""
    if entity_name:
        uri = _require_entity(store, entity_name)
        return store.query(_PREFIX + """
            SELECT ?direction ?other ?otherName ?label WHERE {
                {
                    GRAPH <%s> { <%s> code:linksTo ?other }
                    ?other code:name ?otherName .
                    BIND("outgoing" AS ?direction)
                    OPTIONAL {
                        GRAPH <%s> {
                            <%s> code:linkLabel ?rawLabel .
                            FILTER(STRENDS(?rawLabel, CONCAT("->", ?otherName)))
                        }
                        BIND(STRBEFORE(?rawLabel, "->") AS ?label)
                    }
                }
                UNION
                {
                    GRAPH <%s> { ?other code:linksTo <%s> }
                    ?other code:name ?otherName .
                    BIND("incoming" AS ?direction)
                    OPTIONAL {
                        GRAPH <%s> {
                            ?other code:linkLabel ?rawLabel .
                            FILTER(STRENDS(?rawLabel, CONCAT("->", "%s")))
                        }
                        BIND(STRBEFORE(?rawLabel, "->") AS ?label)
                    }
                }
            }
        """ % (_GRAPH, uri, _GRAPH, uri,
               _GRAPH, uri, _GRAPH, entity_name.replace('"', '\\"')))
    else:
        return store.query(_PREFIX + """
            SELECT ?fromName ?toName WHERE {
                GRAPH <%s> { ?from code:linksTo ?to }
                ?from code:name ?fromName .
                ?to code:name ?toName .
            }
            ORDER BY ?fromName ?toName
        """ % _GRAPH)


# --- Bulk / convenience ---

def clear_annotations(store: CodeStore):
    """Remove all user annotations."""
    store.clear_graph(_GRAPH)


def annotations_for(store: CodeStore, entity_name: str) -> dict:
    """Get all annotations (tags, notes, links) for an entity."""
    return {
        "tags": list_tags(store, entity_name),
        "notes": list_notes(store, entity_name),
        "links": list_links(store, entity_name),
    }
