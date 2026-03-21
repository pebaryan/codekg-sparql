"""Pre-built SPARQL query templates for common code analysis tasks."""

from .store import CodeStore

PREFIX = """
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""

_ENTITY_PREFIX = "https://codekg.dev/entity/"


def _file_from_uri(uri: str) -> str:
    uri = str(uri).strip("<>")
    if uri.startswith(_ENTITY_PREFIX):
        return uri[len(_ENTITY_PREFIX):].split("#")[0]
    return ""


# ---------------------------------------------------------------------------
# Qualified name resolution: "file.py:func_name" or just "func_name"
# ---------------------------------------------------------------------------

def resolve_entity(store: CodeStore, name: str) -> list[dict]:
    """Resolve an entity name, optionally qualified with ``file:name``.

    Returns all matches with entity URI, name, type, file, and line info.
    If *name* contains ``:``, the prefix is treated as a file path filter.
    """
    if ":" in name and not name.startswith("http"):
        file_part, name_part = name.split(":", 1)
        rows = store.query(PREFIX + """
            SELECT ?entity ?ename ?type ?startLine ?endLine WHERE {
                ?entity code:name ?ename .
                FILTER(?ename = "%s")
                ?entity rdf:type ?type .
                ?entity code:startLine ?startLine .
                OPTIONAL { ?entity code:endLine ?endLine }
            }
        """ % name_part.replace('"', '\\"'))
        return [
            {**r, "name": r["ename"], "file": _file_from_uri(r["entity"])}
            for r in rows
            if file_part in _file_from_uri(r["entity"])
        ]
    else:
        rows = store.query(PREFIX + """
            SELECT ?entity ?ename ?type ?startLine ?endLine WHERE {
                ?entity code:name ?ename .
                FILTER(?ename = "%s")
                ?entity rdf:type ?type .
                ?entity code:startLine ?startLine .
                OPTIONAL { ?entity code:endLine ?endLine }
            }
        """ % name.replace('"', '\\"'))
        return [{**r, "name": r["ename"], "file": _file_from_uri(r["entity"])} for r in rows]


def _suggest_on_miss(store: CodeStore, name: str) -> str:
    """Build an error message with fuzzy suggestions when an entity isn't found."""
    suggestions = fuzzy_search(store, name.split(":")[-1], threshold=0.4, limit=5)
    msg = f"Entity not found: '{name}'"
    if suggestions:
        names = [f"  {s['name']} ({s.get('file', _file_from_uri(s.get('entity', '')))})" for s in suggestions]
        msg += "\nDid you mean:\n" + "\n".join(names)
    return msg


# ---------------------------------------------------------------------------
# Index browsing
# ---------------------------------------------------------------------------

def list_files(store: CodeStore) -> list[dict]:
    """List all indexed files."""
    return store.query(PREFIX + """
        SELECT ?filePath WHERE {
            ?m rdf:type code:Module .
            ?m code:filePath ?filePath .
        }
        ORDER BY ?filePath
    """)


def entities_in_file(store: CodeStore, file_path: str) -> list[dict]:
    """List all entities defined in a file."""
    return store.query(PREFIX + """
        SELECT ?name ?type ?startLine ?endLine WHERE {
            ?module rdf:type code:Module .
            ?module code:filePath ?filePath .
            FILTER(CONTAINS(?filePath, "%s"))
            ?module code:defines ?entity .
            ?entity code:name ?name .
            ?entity rdf:type ?type .
            ?entity code:startLine ?startLine .
            OPTIONAL { ?entity code:endLine ?endLine }
        }
        ORDER BY ?startLine
    """ % file_path.replace('"', '\\"'))


# ---------------------------------------------------------------------------
# Source reading
# ---------------------------------------------------------------------------

def read_source(file_path: str, start_line: int = 1, end_line: int | None = None) -> str:
    """Read source code from a file, optionally a line range.

    Args:
        file_path: Path to the file.
        start_line: First line (1-based, inclusive).
        end_line: Last line (inclusive). None = to end of file.

    Returns the source code as a string with line numbers.
    """
    from pathlib import Path
    lines = Path(file_path).read_text(encoding="utf-8").splitlines()
    if end_line is None:
        end_line = len(lines)
    start_line = max(1, start_line)
    end_line = min(len(lines), end_line)
    numbered = []
    for i in range(start_line - 1, end_line):
        numbered.append(f"{i + 1:4d} | {lines[i]}")
    return "\n".join(numbered)


def callers_of(store: CodeStore, function_name: str) -> list[dict]:
    """Find all functions/methods that call the given function name.

    Uses resolvedCalls (URI links) when available, falls back to literal match.
    """
    sparql = PREFIX + """
    SELECT DISTINCT ?caller ?callerName ?callerType WHERE {
        {
            # Resolved path
            ?callee code:name ?cname .
            FILTER(CONTAINS(?cname, "%s"))
            ?caller code:resolvedCalls ?callee .
            ?caller code:name ?callerName .
            ?caller rdf:type ?callerType .
        }
        UNION
        {
            # Fallback: unresolved literal match
            ?caller code:calls ?callTarget .
            ?caller code:name ?callerName .
            ?caller rdf:type ?callerType .
            FILTER(CONTAINS(STR(?callTarget), "%s"))
        }
    }
    """ % (function_name, function_name)
    return store.query(sparql)


def callees_of(store: CodeStore, function_name: str) -> list[dict]:
    """Find all functions/methods called by the given function.

    Returns resolved callee URIs when available, plus unresolved literal names.
    """
    sparql = PREFIX + """
    SELECT DISTINCT ?callee ?calleeName WHERE {
        ?func code:name "%s" .
        {
            ?func code:resolvedCalls ?calleeEntity .
            ?calleeEntity code:name ?calleeName .
            BIND(STR(?calleeEntity) AS ?callee)
        }
        UNION
        {
            ?func code:calls ?calleeLiteral .
            BIND(?calleeLiteral AS ?callee)
            BIND(?calleeLiteral AS ?calleeName)
        }
    }
    """ % function_name
    return store.query(sparql)


def class_hierarchy(store: CodeStore, class_name: str) -> list[dict]:
    """Find the inheritance chain for a class (direct bases)."""
    sparql = PREFIX + """
    SELECT ?class ?className ?base WHERE {
        ?class rdf:type code:Class .
        ?class code:name ?className .
        ?class code:inheritsFrom ?base .
        FILTER(?className = "%s" || ?base = "%s")
    }
    """ % (class_name, class_name)
    return store.query(sparql)


def functions_in(store: CodeStore, file_path: str) -> list[dict]:
    """List all functions defined in a file."""
    sparql = PREFIX + """
    SELECT ?func ?name ?startLine ?endLine WHERE {
        ?module rdf:type code:Module .
        ?module code:filePath "%s" .
        ?module code:defines ?func .
        ?func code:name ?name .
        ?func code:startLine ?startLine .
        ?func code:endLine ?endLine .
        FILTER EXISTS { ?func rdf:type code:Function }
    }
    ORDER BY ?startLine
    """ % file_path
    return store.query(sparql)


def search_by_name(store: CodeStore, pattern: str, limit: int = 50) -> list[dict]:
    """Search for entities by name (substring match)."""
    sparql = PREFIX + """
    SELECT ?entity ?name ?type WHERE {
        ?entity code:name ?name .
        ?entity rdf:type ?type .
        FILTER(CONTAINS(LCASE(?name), LCASE("%s")))
    }
    ORDER BY ?name
    LIMIT %d
    """ % (pattern, limit)
    return store.query(sparql)


def fuzzy_search(store: CodeStore, pattern: str, threshold: float = 0.5, limit: int = 20) -> list[dict]:
    """Fuzzy search for entities by name.

    Uses SequenceMatcher ratio for ranking.  Also boosts exact substring
    matches so they always appear above pure-fuzzy hits.

    Args:
        pattern: Search string (typos OK).
        threshold: Minimum similarity ratio (0.0–1.0).
        limit: Maximum results to return.
    """
    from difflib import SequenceMatcher

    all_entities = store.query(PREFIX + """
        SELECT ?entity ?name ?type WHERE {
            ?entity code:name ?name .
            ?entity rdf:type ?type .
        }
    """)

    pattern_lower = pattern.lower()
    scored = []
    for row in all_entities:
        name = row.get("name", "")
        name_lower = name.lower()

        # Substring match gets a boost to always rank above fuzzy-only
        if pattern_lower in name_lower:
            score = 1.0 + SequenceMatcher(None, pattern_lower, name_lower).ratio()
        else:
            score = SequenceMatcher(None, pattern_lower, name_lower).ratio()

        if score >= threshold:
            scored.append({**row, "score": round(score, 3)})

    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:limit]


def impact_of(store: CodeStore, function_name: str) -> list[dict]:
    """Find transitive callers — all functions that directly or indirectly call this function.

    Uses code:resolvedCalls+ property path for true transitive closure when available.
    Falls back to literal-based matching for unresolved calls.
    """
    sparql = PREFIX + """
    SELECT DISTINCT ?caller ?callerName WHERE {
        {
            # Transitive via resolved call URIs (property path)
            ?target code:name ?tname .
            FILTER(CONTAINS(?tname, "%s"))
            ?caller code:resolvedCalls+ ?target .
            ?caller code:name ?callerName .
        }
        UNION
        {
            # Fallback: direct literal match
            ?caller code:calls ?callTarget .
            ?caller code:name ?callerName .
            FILTER(CONTAINS(STR(?callTarget), "%s"))
        }
    }
    """ % (function_name, function_name)
    return store.query(sparql)


def context_around(store: CodeStore, function_name: str) -> dict:
    """Get full context around a function: the function itself, its callers, callees, and containing module/class."""
    # The function itself
    func_sparql = PREFIX + """
    SELECT ?func ?name ?startLine ?endLine ?docstring WHERE {
        ?func code:name "%s" .
        ?func code:startLine ?startLine .
        ?func code:endLine ?endLine .
        OPTIONAL { ?func code:docstring ?docstring }
        BIND("%s" AS ?name)
    }
    """ % (function_name, function_name)

    # Container (module or class that defines it)
    container_sparql = PREFIX + """
    SELECT ?container ?containerName ?containerType WHERE {
        ?container code:defines ?func .
        ?func code:name "%s" .
        ?container code:name ?containerName .
        ?container rdf:type ?containerType .
    }
    """ % function_name

    return {
        "function": store.query(func_sparql),
        "container": store.query(container_sparql),
        "callers": callers_of(store, function_name),
        "callees": callees_of(store, function_name),
    }


def all_classes(store: CodeStore) -> list[dict]:
    """List all classes in the knowledge graph."""
    sparql = PREFIX + """
    SELECT ?class ?name ?startLine ?endLine WHERE {
        ?class rdf:type code:Class .
        ?class code:name ?name .
        ?class code:startLine ?startLine .
        ?class code:endLine ?endLine .
    }
    ORDER BY ?name
    """
    return store.query(sparql)


def all_functions(store: CodeStore) -> list[dict]:
    """List all functions in the knowledge graph."""
    sparql = PREFIX + """
    SELECT ?func ?name ?type ?startLine WHERE {
        ?func rdf:type ?type .
        ?func code:name ?name .
        ?func code:startLine ?startLine .
        FILTER(?type IN (code:Function, code:Method))
    }
    ORDER BY ?name
    """
    return store.query(sparql)
