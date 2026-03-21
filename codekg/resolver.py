"""Post-indexing call resolution: resolve literal call names to entity URIs."""

import pyoxigraph as ox

from .store import CodeStore
from .ontology import CODE, RESOLVED_CALLS

PREFIX = """
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""

# Named graph for resolved call triples
RESOLVED_GRAPH = ox.NamedNode("https://codekg.dev/entity/_resolved#graph")


def _nn(uri: str) -> ox.NamedNode:
    # Strip angle brackets if present (from SPARQL query results)
    uri = str(uri).strip("<>")
    return ox.NamedNode(uri)


def _build_symbol_table(store: CodeStore) -> dict[str, list[dict]]:
    """Build name → [entity info] mapping from the store.

    Returns dict mapping function/method/class name to list of
    {uri, type, module_path, qualified_name} dicts.
    """
    sparql = PREFIX + """
    SELECT ?entity ?name ?type ?modulePath WHERE {
        ?entity code:name ?name .
        ?entity rdf:type ?type .
        ?module code:defines ?entity .
        ?module rdf:type code:Module .
        ?module code:filePath ?modulePath .
        FILTER(?type IN (code:Function, code:Method, code:Class))
    }
    """
    results = store.query(sparql)

    table: dict[str, list[dict]] = {}
    for row in results:
        name = row["name"]
        entry = {
            "uri": row["entity"],
            "type": row["type"],
            "module_path": row["modulePath"],
        }
        table.setdefault(name, []).append(entry)

    return table


def _build_import_map(store: CodeStore) -> dict[str, dict[str, str]]:
    """Build module_path → {imported_name: full_import_string} mapping.

    For `from config import parse_config`, the module `app.py` will have:
    {"parse_config": "config.parse_config"}
    """
    sparql = PREFIX + """
    SELECT ?modulePath ?importedName WHERE {
        ?module rdf:type code:Module .
        ?module code:filePath ?modulePath .
        ?module code:imports ?importedName .
    }
    """
    results = store.query(sparql)

    import_map: dict[str, list[str]] = {}
    for row in results:
        mod = row["modulePath"]
        import_map.setdefault(mod, []).append(row["importedName"])

    return import_map


def _build_caller_info(store: CodeStore) -> list[dict]:
    """Get all call edges with caller context."""
    sparql = PREFIX + """
    SELECT ?caller ?callerName ?callTarget ?callerModulePath WHERE {
        ?caller code:calls ?callTarget .
        ?caller code:name ?callerName .
        ?callerModule code:defines ?caller .
        ?callerModule rdf:type code:Module .
        ?callerModule code:filePath ?callerModulePath .
    }
    """
    return store.query(sparql)


def _build_class_method_map(store: CodeStore) -> dict[str, dict]:
    """Build a map: method_uri → {class_name, class_uri}."""
    sparql = PREFIX + """
    SELECT ?method ?class ?className WHERE {
        ?class rdf:type code:Class .
        ?class code:name ?className .
        ?class code:defines ?method .
        ?method rdf:type code:Method .
    }
    """
    results = store.query(sparql)
    method_map = {}
    for row in results:
        method_map[row["method"]] = {
            "class_name": row["className"],
            "class_uri": row["class"],
        }
    return method_map


def _find_module_for_import(
    call_name: str,
    caller_module: str,
    import_map: dict[str, list[str]],
) -> str | None:
    """Check if call_name was imported in caller_module. Return the source module hint."""
    imports = import_map.get(caller_module, [])
    for imp in imports:
        # imp is like "config.parse_config" or just "os.path"
        # Check if the call_name matches the last part
        parts = imp.split(".")
        if parts[-1] == call_name:
            # Return the module part (everything except the last component)
            return ".".join(parts[:-1]) if len(parts) > 1 else None
    return None


def _resolve_call(
    call_name: str,
    caller_uri: str,
    caller_module: str,
    symbol_table: dict[str, list[dict]],
    import_map: dict[str, list[str]],
    class_method_map: dict[str, dict],
) -> str | None:
    """Try to resolve a single call name to an entity URI.

    Returns the resolved entity URI string, or None.
    """
    # Handle self.method() or this.method()
    if call_name.startswith(("self.", "this.")):
        method_name = call_name.split(".", 1)[1]
        # Find the class that contains the caller
        class_info = class_method_map.get(caller_uri)
        if class_info:
            # Look for the method in the same class
            candidates = symbol_table.get(method_name, [])
            for c in candidates:
                if class_info["class_name"] in c["uri"]:
                    return c["uri"]
        return None

    # Handle dotted calls like obj.method() — try just the method part
    if "." in call_name:
        parts = call_name.split(".")
        method_name = parts[-1]
        # Best-effort: look up the method name in the symbol table
        candidates = symbol_table.get(method_name, [])
        if len(candidates) == 1:
            return candidates[0]["uri"]
        return None

    # Plain call: check if name was imported
    source_module_hint = _find_module_for_import(call_name, caller_module, import_map)

    candidates = symbol_table.get(call_name, [])
    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]["uri"]

    # Multiple candidates — try to disambiguate by module
    if source_module_hint:
        for c in candidates:
            # Check if the candidate's module path contains the source module hint
            mod_path = c["module_path"]
            # Normalize: "config" matches "config.py", "config.ts", "config/index.ts"
            mod_stem = mod_path.rsplit(".", 1)[0]  # strip extension
            if source_module_hint in mod_stem or mod_stem.endswith(source_module_hint):
                return c["uri"]

    # Same-file definitions take priority
    for c in candidates:
        if c["module_path"] == caller_module:
            return c["uri"]

    return None


def resolve_calls(store: CodeStore) -> int:
    """Run call resolution over the entire store.

    Adds code:resolvedCalls triples linking caller URIs to callee URIs.

    Returns the number of calls resolved.
    """
    # Clear any previous resolved calls
    for quad in store._store.quads_for_pattern(
        None, _nn(RESOLVED_CALLS), None, None
    ):
        store._store.remove(quad)

    symbol_table = _build_symbol_table(store)
    import_map = _build_import_map(store)
    callers = _build_caller_info(store)
    class_method_map = _build_class_method_map(store)

    resolved_count = 0
    resolved_quads = []

    for call in callers:
        caller_uri = call["caller"]
        call_target = call["callTarget"]
        caller_module = call["callerModulePath"]

        resolved_uri = _resolve_call(
            call_target, caller_uri, caller_module,
            symbol_table, import_map, class_method_map,
        )

        if resolved_uri:
            resolved_quads.append((
                _nn(caller_uri),
                _nn(RESOLVED_CALLS),
                _nn(resolved_uri),
                RESOLVED_GRAPH,
            ))
            resolved_count += 1

    store.load_triples(resolved_quads)
    return resolved_count
