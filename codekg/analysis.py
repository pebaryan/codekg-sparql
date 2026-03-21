"""Code analysis: dead code detection, metrics, and refactoring candidates."""

from .store import CodeStore

_PREFIX = """
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""

# Well-known entry points that should not be flagged as dead code.
_ENTRY_POINTS = frozenset({
    "main", "__init__", "__main__", "__new__", "__del__",
    "__str__", "__repr__", "__eq__", "__hash__", "__len__",
    "__getitem__", "__setitem__", "__contains__", "__iter__",
    "__enter__", "__exit__", "__call__",
    "setUp", "tearDown", "setUpClass", "tearDownClass",
    "test_",  # prefix check handled separately
})


# ---------------------------------------------------------------------------
# Dead code detection
# ---------------------------------------------------------------------------

def dead_functions(store: CodeStore, include_methods: bool = True) -> list[dict]:
    """Find functions/methods that are never called (no callers, no resolvedCalls to them).

    Filters out common entry points and dunder methods.
    """
    type_filter = "FILTER(?type IN (code:Function, code:Method))" if include_methods else "FILTER(?type = code:Function)"

    # Get all functions, then find those with no callers
    all_funcs = store.query(_PREFIX + """
        SELECT ?entity ?name ?type ?startLine ?endLine WHERE {
            ?entity rdf:type ?type .
            ?entity code:name ?name .
            ?entity code:startLine ?startLine .
            OPTIONAL { ?entity code:endLine ?endLine }
            %s
        }
    """ % type_filter)

    # Get all called names (literal calls + resolved targets)
    called_names = set()
    literal_calls = store.query(_PREFIX + """
        SELECT DISTINCT ?callTarget WHERE {
            ?caller code:calls ?callTarget .
        }
    """)
    for row in literal_calls:
        called_names.add(row.get("callTarget", ""))

    resolved_targets = store.query(_PREFIX + """
        SELECT DISTINCT ?targetName WHERE {
            ?caller code:resolvedCalls ?target .
            ?target code:name ?targetName .
        }
    """)
    for row in resolved_targets:
        called_names.add(row.get("targetName", ""))

    dead = []
    for func in all_funcs:
        name = func.get("name", "")
        # Skip entry points
        if name in _ENTRY_POINTS:
            continue
        if name.startswith("test_") or name.startswith("__"):
            continue
        # Check if anyone calls this function
        if name not in called_names:
            dead.append(func)

    return dead


def unused_imports(store: CodeStore) -> list[dict]:
    """Find imports that are never referenced in calls."""
    results = store.query(_PREFIX + """
        SELECT ?module ?filePath ?importName WHERE {
            ?module rdf:type code:Module .
            ?module code:filePath ?filePath .
            ?module code:imports ?importName .
        }
    """)

    # Get all call targets
    all_calls = store.query(_PREFIX + """
        SELECT DISTINCT ?callTarget WHERE {
            ?caller code:calls ?callTarget .
        }
    """)
    call_set = {row.get("callTarget", "") for row in all_calls}

    # Get all entity names (could be referenced as types, bases, etc.)
    all_names = store.query(_PREFIX + """
        SELECT DISTINCT ?name WHERE {
            ?e code:name ?name .
        }
    """)
    name_set = {row.get("name", "") for row in all_names}

    unused = []
    for row in results:
        imp = row.get("importName", "")
        # Extract the short name (after last dot)
        short = imp.rsplit(".", 1)[-1] if "." in imp else imp
        # Check if the short name appears in calls or entity names
        if short not in call_set and short not in name_set:
            unused.append(row)

    return unused


# ---------------------------------------------------------------------------
# Code metrics
# ---------------------------------------------------------------------------

def function_metrics(store: CodeStore, limit: int = 50) -> list[dict]:
    """Compute metrics for each function: size, fan-in, fan-out.

    Returns functions sorted by size (largest first).
    """
    funcs = store.query(_PREFIX + """
        SELECT ?entity ?name ?type ?startLine ?endLine WHERE {
            ?entity rdf:type ?type .
            ?entity code:name ?name .
            ?entity code:startLine ?startLine .
            ?entity code:endLine ?endLine .
            FILTER(?type IN (code:Function, code:Method))
        }
    """)

    # Fan-out: count of calls per function
    fanout_rows = store.query(_PREFIX + """
        SELECT ?callerName (COUNT(DISTINCT ?target) AS ?fanOut) WHERE {
            ?caller code:name ?callerName .
            ?caller code:calls ?target .
            ?caller rdf:type ?type .
            FILTER(?type IN (code:Function, code:Method))
        }
        GROUP BY ?callerName
    """)
    fanout = {r["callerName"]: int(r["fanOut"]) for r in fanout_rows}

    # Fan-in: count of callers per function name
    fanin_rows = store.query(_PREFIX + """
        SELECT ?callTarget (COUNT(DISTINCT ?caller) AS ?fanIn) WHERE {
            ?caller code:calls ?callTarget .
        }
        GROUP BY ?callTarget
    """)
    fanin = {r["callTarget"]: int(r["fanIn"]) for r in fanin_rows}

    metrics = []
    for f in funcs:
        name = f["name"]
        start = int(f["startLine"])
        end = int(f["endLine"])
        size = end - start + 1
        metrics.append({
            "name": name,
            "type": f["type"],
            "file": f["entity"],
            "start_line": start,
            "end_line": end,
            "size": size,
            "fan_in": fanin.get(name, 0),
            "fan_out": fanout.get(name, 0),
        })

    metrics.sort(key=lambda m: m["size"], reverse=True)
    return metrics[:limit]


def class_metrics(store: CodeStore, limit: int = 50) -> list[dict]:
    """Compute metrics for each class: size, method count, depth."""
    classes = store.query(_PREFIX + """
        SELECT ?entity ?name ?startLine ?endLine WHERE {
            ?entity rdf:type code:Class .
            ?entity code:name ?name .
            ?entity code:startLine ?startLine .
            ?entity code:endLine ?endLine .
        }
    """)

    # Method count per class
    method_counts = store.query(_PREFIX + """
        SELECT ?className (COUNT(?method) AS ?methodCount) WHERE {
            ?class rdf:type code:Class .
            ?class code:name ?className .
            ?class code:defines ?method .
            ?method rdf:type code:Method .
        }
        GROUP BY ?className
    """)
    mc = {r["className"]: int(r["methodCount"]) for r in method_counts}

    metrics = []
    for c in classes:
        name = c["name"]
        start = int(c["startLine"])
        end = int(c["endLine"])
        metrics.append({
            "name": name,
            "file": c["entity"],
            "start_line": start,
            "end_line": end,
            "size": end - start + 1,
            "method_count": mc.get(name, 0),
        })

    metrics.sort(key=lambda m: m["size"], reverse=True)
    return metrics[:limit]


def refactoring_candidates(store: CodeStore, min_size: int = 30, min_fan_in: int = 3) -> list[dict]:
    """Find functions that are refactoring candidates: large AND heavily called."""
    all_metrics = function_metrics(store, limit=500)
    return [
        m for m in all_metrics
        if m["size"] >= min_size or m["fan_in"] >= min_fan_in
    ]


def circular_dependencies(store: CodeStore) -> list[dict]:
    """Find circular import dependencies between modules."""
    imports = store.query(_PREFIX + """
        SELECT ?fromFile ?toImport WHERE {
            ?module rdf:type code:Module .
            ?module code:filePath ?fromFile .
            ?module code:imports ?toImport .
        }
    """)

    # Build adjacency: file -> set of imported module names
    file_imports: dict[str, set[str]] = {}
    for row in imports:
        f = row["fromFile"]
        imp = row["toImport"]
        file_imports.setdefault(f, set()).add(imp)

    # Check for A imports B and B imports A
    cycles = []
    checked = set()
    files = list(file_imports.keys())
    for a in files:
        for b in files:
            if a >= b:
                continue
            pair = (a, b)
            if pair in checked:
                continue
            checked.add(pair)
            # Does A import something from B's namespace?
            a_base = a.rsplit(".", 1)[0].rsplit("/", 1)[-1] if "." in a else a
            b_base = b.rsplit(".", 1)[0].rsplit("/", 1)[-1] if "." in b else b
            a_imports_b = any(b_base in imp for imp in file_imports.get(a, set()))
            b_imports_a = any(a_base in imp for imp in file_imports.get(b, set()))
            if a_imports_b and b_imports_a:
                cycles.append({"file_a": a, "file_b": b})

    return cycles
