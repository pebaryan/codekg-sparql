"""Export knowledge graph as Mermaid or DOT diagrams."""

from .store import CodeStore

_PREFIX = """
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""


def _safe_id(name: str) -> str:
    """Sanitize a name for use as a graph node ID."""
    return name.replace(".", "_").replace("-", "_").replace(" ", "_").replace("/", "_")


# ---------------------------------------------------------------------------
# Call graph
# ---------------------------------------------------------------------------

def call_graph(store: CodeStore, root_function: str | None = None, depth: int = 3, fmt: str = "mermaid") -> str:
    """Export the call graph as Mermaid or DOT.

    Args:
        root_function: Starting function (None = entire graph).
        depth: Max traversal depth from root.
        fmt: 'mermaid' or 'dot'.
    """
    if root_function:
        edges = _call_edges_from(store, root_function, depth)
    else:
        edges = _all_call_edges(store)

    if fmt == "dot":
        return _edges_to_dot(edges, "call_graph")
    return _edges_to_mermaid(edges, "Call Graph")


def _all_call_edges(store: CodeStore) -> list[tuple[str, str]]:
    rows = store.query(_PREFIX + """
        SELECT DISTINCT ?callerName ?calleeName WHERE {
            {
                ?caller code:resolvedCalls ?callee .
                ?caller code:name ?callerName .
                ?callee code:name ?calleeName .
            }
            UNION
            {
                ?caller code:calls ?calleeName .
                ?caller code:name ?callerName .
                ?caller rdf:type ?type .
                FILTER(?type IN (code:Function, code:Method))
            }
        }
        LIMIT 200
    """)
    return [(r["callerName"], r["calleeName"]) for r in rows]


def _call_edges_from(store: CodeStore, root: str, depth: int) -> list[tuple[str, str]]:
    """BFS from root function, collecting call edges up to depth."""
    edges = []
    visited = set()
    frontier = {root}
    for _ in range(depth):
        next_frontier = set()
        for name in frontier:
            if name in visited:
                continue
            visited.add(name)
            rows = store.query(_PREFIX + """
                SELECT DISTINCT ?calleeName WHERE {
                    ?caller code:name "%s" .
                    {
                        ?caller code:resolvedCalls ?callee .
                        ?callee code:name ?calleeName .
                    }
                    UNION
                    {
                        ?caller code:calls ?calleeName .
                    }
                }
            """ % name.replace('"', '\\"'))
            for r in rows:
                callee = r["calleeName"]
                edges.append((name, callee))
                if callee not in visited:
                    next_frontier.add(callee)
        frontier = next_frontier
        if not frontier:
            break
    return edges


# ---------------------------------------------------------------------------
# Inheritance graph
# ---------------------------------------------------------------------------

def inheritance_graph(store: CodeStore, fmt: str = "mermaid") -> str:
    """Export the class inheritance hierarchy."""
    rows = store.query(_PREFIX + """
        SELECT ?className ?baseName WHERE {
            ?class rdf:type code:Class .
            ?class code:name ?className .
            ?class code:inheritsFrom ?baseName .
        }
    """)
    edges = [(r["baseName"], r["className"]) for r in rows]

    # Also include classes with no bases
    all_classes = store.query(_PREFIX + """
        SELECT DISTINCT ?name WHERE {
            ?c rdf:type code:Class .
            ?c code:name ?name .
        }
    """)
    all_names = {r["name"] for r in all_classes}
    edge_names = {e[0] for e in edges} | {e[1] for e in edges}
    orphans = all_names - edge_names

    if fmt == "dot":
        return _edges_to_dot(edges, "inheritance", extra_nodes=orphans)
    return _edges_to_mermaid(edges, "Inheritance", extra_nodes=orphans)


# ---------------------------------------------------------------------------
# File dependency graph
# ---------------------------------------------------------------------------

def file_dependency_graph(store: CodeStore, fmt: str = "mermaid") -> str:
    """Export file-level import dependencies."""
    rows = store.query(_PREFIX + """
        SELECT ?fromFile ?importName WHERE {
            ?module rdf:type code:Module .
            ?module code:filePath ?fromFile .
            ?module code:imports ?importName .
        }
    """)

    # Map import names to known files
    all_files = store.query(_PREFIX + """
        SELECT ?filePath WHERE {
            ?m rdf:type code:Module .
            ?m code:filePath ?filePath .
        }
    """)
    file_basenames = {}
    for r in all_files:
        fp = r["filePath"]
        # Map basename without extension to full path
        base = fp.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        file_basenames[base] = fp

    edges = []
    for r in rows:
        from_file = r["fromFile"]
        imp = r["importName"]
        # Try to resolve import to a known file
        # Extract the first component of the import path
        first = imp.split(".")[0]
        if first in file_basenames:
            to_file = file_basenames[first]
            if from_file != to_file:
                edges.append((from_file, to_file))

    # Deduplicate
    edges = list(set(edges))

    if fmt == "dot":
        return _edges_to_dot(edges, "dependencies")
    return _edges_to_mermaid(edges, "File Dependencies")


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _edges_to_mermaid(edges: list[tuple[str, str]], title: str, extra_nodes: set[str] | None = None) -> str:
    lines = [f"graph TD"]
    seen = set()
    for src, dst in edges:
        sid = _safe_id(src)
        did = _safe_id(dst)
        edge = f"    {sid}[\"{src}\"] --> {did}[\"{dst}\"]"
        if edge not in seen:
            lines.append(edge)
            seen.add(edge)
    if extra_nodes:
        for n in sorted(extra_nodes):
            nid = _safe_id(n)
            node = f"    {nid}[\"{n}\"]"
            if node not in seen:
                lines.append(node)
                seen.add(node)
    return "\n".join(lines)


def _edges_to_dot(edges: list[tuple[str, str]], name: str, extra_nodes: set[str] | None = None) -> str:
    lines = [f"digraph {name} {{", "    rankdir=TB;"]
    seen = set()
    for src, dst in edges:
        sid = _safe_id(src)
        did = _safe_id(dst)
        edge = f'    {sid} -> {did};'
        if edge not in seen:
            lines.append(edge)
            seen.add(edge)
    # Node labels
    all_nodes = set()
    for src, dst in edges:
        all_nodes.add(src)
        all_nodes.add(dst)
    if extra_nodes:
        all_nodes |= extra_nodes
    for n in sorted(all_nodes):
        nid = _safe_id(n)
        lines.append(f'    {nid} [label="{n}"];')
    lines.append("}")
    return "\n".join(lines)
