"""Source-level refactoring operations backed by the knowledge graph.

These operations modify actual source files and re-index them so the KG
stays in sync.  Tree-sitter provides byte-accurate AST positions for
precise edits that won't corrupt surrounding code.
"""

import os
from pathlib import Path

from tree_sitter import Language, Parser

from .store import CodeStore
from .indexer import index_file

# Node types that represent identifiers across supported languages.
_IDENT_TYPES = frozenset({
    "identifier", "type_identifier", "property_identifier",
    "shorthand_property_identifier", "shorthand_property_identifier_pattern",
    "field_identifier",
})

_ENTITY_PREFIX = "https://codekg.dev/entity/"

_PREFIX = """
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts_parser(file_path: str) -> Parser | None:
    """Create a tree-sitter Parser for the file's language."""
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".py":
            import tree_sitter_python as m
            return Parser(Language(m.language()))
        if ext in (".ts", ".tsx"):
            import tree_sitter_typescript as m
            lang = m.language_typescript() if ext == ".ts" else m.language_tsx()
            return Parser(Language(lang))
        if ext in (".js", ".jsx"):
            import tree_sitter_javascript as m
            return Parser(Language(m.language()))
        if ext == ".java":
            import tree_sitter_java as m
            return Parser(Language(m.language()))
        if ext in (".c", ".h"):
            import tree_sitter_c as m
            return Parser(Language(m.language()))
        if ext in (".cpp", ".cc", ".cxx", ".hpp", ".hh"):
            import tree_sitter_cpp as m
            return Parser(Language(m.language()))
    except ImportError:
        pass
    return None


def _file_from_uri(uri: str) -> str:
    """Extract relative file path from an entity URI."""
    uri = str(uri).strip("<>")
    if uri.startswith(_ENTITY_PREFIX):
        rest = uri[len(_ENTITY_PREFIX):]
        return rest.split("#")[0]
    return ""


def _find_identifiers(node, name: str) -> list[tuple[int, int]]:
    """Recursively find all identifier nodes matching *name* exactly.

    Returns list of (start_byte, end_byte).
    """
    results = []
    if node.type in _IDENT_TYPES and node.text.decode("utf-8") == name:
        results.append((node.start_byte, node.end_byte))
    for child in node.children:
        results.extend(_find_identifiers(child, name))
    return results


def _replace_bytes(source: bytes, positions: list[tuple[int, int]], new_text: str) -> bytes:
    """Replace byte ranges end-to-start so offsets stay valid."""
    new_bytes = new_text.encode("utf-8")
    for start, end in sorted(positions, reverse=True):
        source = source[:start] + new_bytes + source[end:]
    return source


def _read_lines(path: str) -> list[str]:
    return Path(path).read_text(encoding="utf-8").splitlines(keepends=True)


def _write_lines(path: str, lines: list[str]):
    Path(path).write_text("".join(lines), encoding="utf-8")


def _reindex(file_path: str, root_path: str, store: CodeStore) -> int:
    return index_file(file_path, root_path, store)


def _affected_files(store: CodeStore, name: str) -> set[str]:
    """Query the KG for relative file paths that reference *name*."""
    # Entities named `name` (definitions)
    defs = store.query(_PREFIX + """
        SELECT DISTINCT ?entity WHERE { ?entity code:name "%s" }
    """ % name.replace('"', '\\"'))

    # Entities that call `name`
    callers = store.query(_PREFIX + """
        SELECT DISTINCT ?caller WHERE { ?caller code:calls "%s" }
    """ % name.replace('"', '\\"'))

    # Modules that import `name` (imports store "module.name")
    importers = store.query(_PREFIX + """
        SELECT DISTINCT ?module WHERE {
            ?module code:imports ?imp .
            FILTER(STRENDS(?imp, ".%s") || ?imp = "%s")
        }
    """ % (name.replace('"', '\\"'), name.replace('"', '\\"')))

    files: set[str] = set()
    for row in defs + callers + importers:
        for val in row.values():
            fp = _file_from_uri(val)
            if fp:
                files.add(fp)
    return files


def _find_entity(store: CodeStore, entity_name: str) -> dict | None:
    """Resolve an entity by name.  Returns first match with file, lines."""
    rows = store.query(_PREFIX + """
        SELECT ?entity ?startLine ?endLine WHERE {
            ?entity code:name "%s" .
            ?entity code:startLine ?startLine .
            OPTIONAL { ?entity code:endLine ?endLine }
        } LIMIT 1
    """ % entity_name.replace('"', '\\"'))
    if not rows:
        return None
    row = rows[0]
    return {
        "uri": row["entity"],
        "file": _file_from_uri(row["entity"]),
        "start_line": int(row["startLine"]),
        "end_line": int(row.get("endLine", row["startLine"])),
    }


# ---------------------------------------------------------------------------
# Public operations
# ---------------------------------------------------------------------------

def rename_symbol(
    store: CodeStore,
    root_path: str,
    old_name: str,
    new_name: str,
    reindex: bool = True,
) -> dict:
    """Rename all occurrences of *old_name* to *new_name* across the project.

    Uses tree-sitter for exact identifier matching (won't touch substrings
    or string literals).

    Returns dict with ``files_modified`` and ``occurrences``.
    """
    root = Path(root_path).resolve()
    rel_files = _affected_files(store, old_name)
    if not rel_files:
        return {"files_modified": [], "occurrences": 0}

    files_modified = []
    total = 0

    for rel in rel_files:
        abs_path = str(root / rel)
        if not os.path.isfile(abs_path):
            continue

        parser = _ts_parser(abs_path)
        if parser is None:
            continue

        source = Path(abs_path).read_bytes()
        tree = parser.parse(source)
        positions = _find_identifiers(tree.root_node, old_name)
        if not positions:
            continue

        new_source = _replace_bytes(source, positions, new_name)
        Path(abs_path).write_bytes(new_source)
        files_modified.append(rel)
        total += len(positions)

        if reindex:
            _reindex(abs_path, str(root), store)

    return {"files_modified": files_modified, "occurrences": total}


def insert_code(
    file_path: str,
    line: int,
    code: str,
    position: str = "after",
) -> dict:
    """Insert *code* before or after a given line number (1-based).

    Args:
        file_path: Absolute path to the file.
        line: 1-based line number.
        code: Code to insert (trailing newline added if missing).
        position: ``"after"`` (default) or ``"before"``.

    Returns dict with ``file`` and ``line``.
    """
    lines = _read_lines(file_path)
    if not code.endswith("\n"):
        code += "\n"

    idx = line - 1  # 0-based
    if position == "before":
        lines.insert(idx, code)
    else:
        lines.insert(idx + 1, code)

    _write_lines(file_path, lines)
    return {"file": file_path, "line": line, "position": position}


def replace_lines(
    file_path: str,
    start_line: int,
    end_line: int,
    new_code: str,
) -> dict:
    """Replace lines *start_line* through *end_line* (1-based, inclusive).

    Returns dict with ``file``, ``lines_removed``, ``lines_added``.
    """
    lines = _read_lines(file_path)
    if not new_code.endswith("\n"):
        new_code += "\n"
    new_lines = new_code.splitlines(keepends=True)

    s = start_line - 1
    e = end_line  # exclusive end for slice
    removed = lines[s:e]
    lines[s:e] = new_lines

    _write_lines(file_path, lines)
    return {
        "file": file_path,
        "lines_removed": len(removed),
        "lines_added": len(new_lines),
    }


def replace_entity(
    store: CodeStore,
    root_path: str,
    entity_name: str,
    new_code: str,
    reindex: bool = True,
) -> dict:
    """Replace an entity's source code (function, class, etc.).

    Looks up the entity in the KG to find its file and line range,
    then replaces those lines with *new_code*.

    Returns dict with ``file``, ``entity``, ``lines_removed``, ``lines_added``.
    """
    ent = _find_entity(store, entity_name)
    if ent is None:
        raise ValueError(f"Entity not found: {entity_name}")

    root = Path(root_path).resolve()
    abs_path = str(root / ent["file"])
    result = replace_lines(abs_path, ent["start_line"], ent["end_line"], new_code)
    result["entity"] = entity_name

    if reindex:
        _reindex(abs_path, str(root), store)

    return result


def add_function(
    store: CodeStore,
    root_path: str,
    file_path: str,
    code: str,
    after_entity: str | None = None,
    at_line: int | None = None,
    reindex: bool = True,
) -> dict:
    """Add a function (or any block of code) to a file.

    Insertion point is determined by (in priority order):
      1. *at_line* — explicit 1-based line number.
      2. *after_entity* — insert after the named entity's end line.
      3. Default — append to end of file.

    Returns dict with ``file`` and ``line``.
    """
    root = Path(root_path).resolve()
    abs_path = str(root / file_path) if not os.path.isabs(file_path) else file_path

    if at_line is not None:
        line = at_line
    elif after_entity:
        ent = _find_entity(store, after_entity)
        if ent is None:
            raise ValueError(f"Entity not found: {after_entity}")
        line = ent["end_line"]
    else:
        # Append at end
        lines = _read_lines(abs_path)
        line = len(lines)

    # Add blank line separator before the new code
    if not code.startswith("\n"):
        code = "\n" + code

    result = insert_code(abs_path, line, code, position="after")

    if reindex:
        _reindex(abs_path, str(root), store)

    return result
