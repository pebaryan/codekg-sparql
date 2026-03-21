"""MCP (Model Context Protocol) server exposing CodeKG tools."""

import json

from mcp.server.fastmcp import FastMCP

from .store import CodeStore
from .indexer import index_directory
from . import queries as Q
from .nl2sparql import ask as nl_ask

mcp = FastMCP("codekg")

# Global store instance, set at startup
_store: CodeStore | None = None


def _get_store() -> CodeStore:
    global _store
    if _store is None:
        _store = CodeStore(path=".codekg_store")
    return _store


def init_store(path: str):
    """Initialize the global store with the given path."""
    global _store
    _store = CodeStore(path=path)


def _fmt(data) -> str:
    return json.dumps(data, indent=2)


@mcp.tool()
def list_files() -> str:
    """List all files currently indexed in the knowledge graph."""
    return _fmt(Q.list_files(_get_store()))


@mcp.tool()
def entities_in_file(file_path: str) -> str:
    """List all entities (functions, classes, variables) defined in a file.

    Args:
        file_path: File path or substring to match (e.g. 'app.py').
    """
    return _fmt(Q.entities_in_file(_get_store(), file_path))


@mcp.tool()
def resolve_entity(name: str) -> str:
    """Resolve an entity name, showing all matches with file and line info.

    Use 'file.py:name' to disambiguate when multiple entities share the same name.

    Args:
        name: Entity name, optionally qualified as 'file:name'.
    """
    store = _get_store()
    results = Q.resolve_entity(store, name)
    if not results:
        return Q._suggest_on_miss(store, name)
    return _fmt(results)


@mcp.tool()
def read_source(file_path: str, start_line: int = 1, end_line: int = 0) -> str:
    """Read source code from a file, optionally a specific line range.

    Args:
        file_path: Path to the file.
        start_line: First line to show (1-based, default: 1).
        end_line: Last line to show (0 = to end of file).
    """
    return Q.read_source(file_path, start_line, end_line or None)


@mcp.tool()
def index_codebase(path: str) -> str:
    """Index a codebase directory into the knowledge graph.

    Args:
        path: Path to the directory to index.
    """
    store = _get_store()
    stats = index_directory(path, store)
    return f"Indexed {stats.files_indexed} files, {stats.total_triples} triples, {stats.resolved_calls} calls resolved."


@mcp.tool()
def callers_of(function_name: str) -> str:
    """Find all functions/methods that call the given function.

    Args:
        function_name: Name of the function to find callers for.
    """
    return _fmt(Q.callers_of(_get_store(), function_name))


@mcp.tool()
def callees_of(function_name: str) -> str:
    """Find all functions/methods called by the given function.

    Args:
        function_name: Name of the function to find callees for.
    """
    return _fmt(Q.callees_of(_get_store(), function_name))


@mcp.tool()
def impact_of(function_name: str) -> str:
    """Find transitive callers of a function (impact analysis).

    Args:
        function_name: Name of the function to analyze impact for.
    """
    return _fmt(Q.impact_of(_get_store(), function_name))


@mcp.tool()
def context_around(function_name: str) -> str:
    """Get full context around a function: callers, callees, and container.

    Args:
        function_name: Name of the function to get context for.
    """
    return _fmt(Q.context_around(_get_store(), function_name))


@mcp.tool()
def search(pattern: str) -> str:
    """Search for code entities by name (substring match).

    Args:
        pattern: Substring to search for in entity names.
    """
    return _fmt(Q.search_by_name(_get_store(), pattern))


@mcp.tool()
def fuzzy_search(pattern: str, threshold: float = 0.5, limit: int = 20) -> str:
    """Fuzzy search for code entities by name (typo-tolerant).

    Args:
        pattern: Search string (typos OK).
        threshold: Minimum similarity ratio (0.0-1.0).
        limit: Maximum results to return.
    """
    return _fmt(Q.fuzzy_search(_get_store(), pattern, threshold=threshold, limit=limit))


@mcp.tool()
def sparql_query(sparql: str) -> str:
    """Execute a raw SPARQL query against the code knowledge graph.

    Args:
        sparql: The SPARQL query string to execute.
    """
    return _fmt(_get_store().query(sparql))


@mcp.tool()
def ask_question(
    question: str,
    llm_url: str = "http://localhost:8080/v1",
    model: str = "local-model",
) -> str:
    """Ask a natural language question about the code. Requires a local LLM.

    Args:
        question: Natural language question about the code.
        llm_url: OpenAI-compatible API base URL for the local LLM.
        model: Model name to use.
    """
    result = nl_ask(question, _get_store(), base_url=llm_url, model=model)
    return _fmt(result)


@mcp.tool()
def stats() -> str:
    """Show knowledge graph statistics (total triples, entity counts)."""
    return _fmt(_get_store().stats())


@mcp.tool()
def add_tag(entity_name: str, tag: str) -> str:
    """Add a tag to a code entity (e.g. 'deprecated', 'entry-point').

    Args:
        entity_name: Name of the entity to tag.
        tag: Tag string to add.
    """
    from . import edits as E
    uri = E.add_tag(_get_store(), entity_name, tag)
    return f"Tagged '{entity_name}' with '{tag}'."


@mcp.tool()
def remove_tag(entity_name: str, tag: str) -> str:
    """Remove a tag from a code entity.

    Args:
        entity_name: Name of the entity.
        tag: Tag string to remove.
    """
    from . import edits as E
    E.remove_tag(_get_store(), entity_name, tag)
    return f"Removed tag '{tag}' from '{entity_name}'."


@mcp.tool()
def add_note(entity_name: str, note: str) -> str:
    """Add a free-text note to a code entity.

    Args:
        entity_name: Name of the entity to annotate.
        note: Note text to add.
    """
    from . import edits as E
    E.add_note(_get_store(), entity_name, note)
    return f"Added note to '{entity_name}'."


@mcp.tool()
def remove_note(entity_name: str, note: str) -> str:
    """Remove a specific note from a code entity.

    Args:
        entity_name: Name of the entity.
        note: Exact note text to remove.
    """
    from . import edits as E
    E.remove_note(_get_store(), entity_name, note)
    return f"Removed note from '{entity_name}'."


@mcp.tool()
def add_link(from_entity: str, to_entity: str, label: str = "") -> str:
    """Create a directed link between two code entities.

    Args:
        from_entity: Name of the source entity.
        to_entity: Name of the target entity.
        label: Optional label for the link.
    """
    from . import edits as E
    E.add_link(_get_store(), from_entity, to_entity, label=label)
    msg = f"Linked '{from_entity}' -> '{to_entity}'"
    if label:
        msg += f" (label: {label})"
    return msg + "."


@mcp.tool()
def remove_link(from_entity: str, to_entity: str) -> str:
    """Remove a directed link between two code entities.

    Args:
        from_entity: Name of the source entity.
        to_entity: Name of the target entity.
    """
    from . import edits as E
    E.remove_link(_get_store(), from_entity, to_entity)
    return f"Removed link from '{from_entity}' to '{to_entity}'."


@mcp.tool()
def annotations(entity_name: str = "") -> str:
    """Show annotations (tags, notes, links) for an entity or all entities.

    Args:
        entity_name: Name of entity to query, or empty for all.
    """
    from . import edits as E
    store = _get_store()
    if entity_name:
        return _fmt(E.annotations_for(store, entity_name))
    else:
        return _fmt({
            "tags": E.list_tags(store),
            "notes": E.list_notes(store),
            "links": E.list_links(store),
        })


@mcp.tool()
def preview_rename(old_name: str, new_name: str, directory: str) -> str:
    """Preview a rename without modifying files. Shows a unified diff.

    Always call this before rename_symbol to verify the changes are correct.

    Args:
        old_name: Current name of the symbol.
        new_name: New name for the symbol.
        directory: Root directory of the project.
    """
    from . import refactor as R
    result = R.preview_rename(_get_store(), directory, old_name, new_name)
    if not result["files"]:
        return f"No occurrences of '{old_name}' found."
    header = f"Preview: {result['total_occurrences']} occurrences in {len(result['files'])} files\n\n"
    return header + result["diff"]


@mcp.tool()
def rename_symbol(old_name: str, new_name: str, directory: str) -> str:
    """Rename a symbol across the codebase using tree-sitter for precision.

    Call preview_rename first to verify changes before applying.

    Args:
        old_name: Current name of the symbol.
        new_name: New name for the symbol.
        directory: Root directory of the project.
    """
    from . import refactor as R
    result = R.rename_symbol(_get_store(), directory, old_name, new_name)
    if result["files_modified"]:
        files = ", ".join(result["files_modified"])
        return f"Renamed '{old_name}' -> '{new_name}': {result['occurrences']} occurrences in {files}"
    return f"No occurrences of '{old_name}' found."


@mcp.tool()
def replace_entity(entity_name: str, new_code: str, directory: str) -> str:
    """Replace an entity's source code (function, class, etc.).

    Args:
        entity_name: Name of the entity to replace.
        new_code: New source code for the entity.
        directory: Root directory of the project.
    """
    from . import refactor as R
    result = R.replace_entity(_get_store(), directory, entity_name, new_code)
    return f"Replaced '{entity_name}': {result['lines_removed']} lines removed, {result['lines_added']} added."


@mcp.tool()
def add_function_to_file(
    file_path: str,
    code: str,
    directory: str,
    after_entity: str = "",
    at_line: int = 0,
) -> str:
    """Add a function (or any code block) to a file.

    Args:
        file_path: Relative path to the file.
        code: The function/code to insert.
        directory: Root directory of the project.
        after_entity: Insert after this entity (by name). Empty to skip.
        at_line: Insert at this line number (1-based). 0 to skip.
    """
    from . import refactor as R
    result = R.add_function(
        _get_store(), directory, file_path, code,
        after_entity=after_entity or None,
        at_line=at_line or None,
    )
    return f"Inserted code at line {result['line']} in {result['file']}."


@mcp.tool()
def insert_code_at_line(file_path: str, line: int, code: str, before: bool = False) -> str:
    """Insert code before or after a specific line in a file.

    Args:
        file_path: Absolute path to the file.
        line: 1-based line number.
        code: Code to insert.
        before: If true, insert before the line; otherwise after.
    """
    from . import refactor as R
    pos = "before" if before else "after"
    R.insert_code(file_path, line, code, position=pos)
    return f"Inserted code {pos} line {line} in {file_path}."


# ---------------------------------------------------------------------------
# Analysis tools
# ---------------------------------------------------------------------------

@mcp.tool()
def dead_code(include_methods: bool = True) -> str:
    """Find functions/methods that are never called (dead code detection).

    Args:
        include_methods: Include class methods in the search (default: true).
    """
    from . import analysis as A
    return _fmt(A.dead_functions(_get_store(), include_methods=include_methods))


@mcp.tool()
def unused_imports() -> str:
    """Find imports that are never referenced in the codebase."""
    from . import analysis as A
    return _fmt(A.unused_imports(_get_store()))


@mcp.tool()
def function_metrics(limit: int = 50) -> str:
    """Get code metrics for functions: size, fan-in, fan-out.

    Args:
        limit: Maximum number of results (default: 50).
    """
    from . import analysis as A
    return _fmt(A.function_metrics(_get_store(), limit=limit))


@mcp.tool()
def class_metrics(limit: int = 50) -> str:
    """Get code metrics for classes: size, method count.

    Args:
        limit: Maximum number of results (default: 50).
    """
    from . import analysis as A
    return _fmt(A.class_metrics(_get_store(), limit=limit))


@mcp.tool()
def refactoring_candidates(min_size: int = 30, min_fan_in: int = 3) -> str:
    """Find functions that are refactoring candidates (large or heavily called).

    Args:
        min_size: Minimum function size in lines.
        min_fan_in: Minimum number of callers.
    """
    from . import analysis as A
    return _fmt(A.refactoring_candidates(_get_store(), min_size=min_size, min_fan_in=min_fan_in))


@mcp.tool()
def circular_dependencies() -> str:
    """Find circular import dependencies between modules."""
    from . import analysis as A
    return _fmt(A.circular_dependencies(_get_store()))


# ---------------------------------------------------------------------------
# Git impact analysis
# ---------------------------------------------------------------------------

@mcp.tool()
def git_impact(directory: str, ref: str = "HEAD", base: str = "") -> str:
    """Analyze impact of git changes on the codebase.

    Args:
        directory: Root of the git repository.
        ref: Git ref for changes (default: HEAD = uncommitted changes).
        base: Base ref for comparison (e.g. 'main'). Empty for working tree diff.
    """
    from . import git_impact as G
    return _fmt(G.diff_impact(_get_store(), directory, ref=ref, base=base or None))


# ---------------------------------------------------------------------------
# Graph export
# ---------------------------------------------------------------------------

@mcp.tool()
def export_call_graph(root_function: str = "", depth: int = 3, fmt: str = "mermaid") -> str:
    """Export the call graph as Mermaid or DOT diagram.

    Args:
        root_function: Starting function (empty = entire graph).
        depth: Max traversal depth from root.
        fmt: 'mermaid' or 'dot'.
    """
    from . import export as X
    return X.call_graph(_get_store(), root_function=root_function or None, depth=depth, fmt=fmt)


@mcp.tool()
def export_inheritance_graph(fmt: str = "mermaid") -> str:
    """Export the class inheritance hierarchy as Mermaid or DOT diagram.

    Args:
        fmt: 'mermaid' or 'dot'.
    """
    from . import export as X
    return X.inheritance_graph(_get_store(), fmt=fmt)


@mcp.tool()
def export_dependency_graph(fmt: str = "mermaid") -> str:
    """Export file-level import dependencies as Mermaid or DOT diagram.

    Args:
        fmt: 'mermaid' or 'dot'.
    """
    from . import export as X
    return X.file_dependency_graph(_get_store(), fmt=fmt)


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------

@mcp.tool()
def undo_last(directory: str = "") -> str:
    """Undo the most recent refactoring operation, restoring all modified files.

    Args:
        directory: Root directory for re-indexing after undo (optional).
    """
    from . import refactor as R
    store = _get_store() if directory else None
    result = R.undo_last(store, directory or None)
    if result:
        files = ", ".join(result["files_restored"])
        return f"Undid: {result['label']} (restored: {files})"
    return "Nothing to undo."


@mcp.tool()
def undo_history() -> str:
    """Show the undo stack history of refactoring operations."""
    from . import refactor as R
    return _fmt(R.undo_history())


def run(transport: str = "stdio", store_path: str = ".codekg_store", port: int = 8000):
    """Run the MCP server.

    Args:
        transport: "stdio" or "sse"
        store_path: Path to the persistent store directory.
        port: Port for SSE transport (ignored for stdio).
    """
    init_store(store_path)

    if transport == "sse":
        mcp.settings.port = port
    mcp.run(transport=transport)
