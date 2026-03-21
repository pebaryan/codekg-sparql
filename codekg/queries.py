"""Pre-built SPARQL query templates for common code analysis tasks."""

from .store import CodeStore

PREFIX = """
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""


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


def search_by_name(store: CodeStore, pattern: str) -> list[dict]:
    """Search for entities by name (substring match)."""
    sparql = PREFIX + """
    SELECT ?entity ?name ?type WHERE {
        ?entity code:name ?name .
        ?entity rdf:type ?type .
        FILTER(CONTAINS(LCASE(?name), LCASE("%s")))
    }
    ORDER BY ?name
    """ % pattern
    return store.query(sparql)


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
