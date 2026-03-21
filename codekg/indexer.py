"""Directory indexer — walks a codebase and builds the knowledge graph."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from .triples import module_to_quads
from .store import CodeStore
from .ontology import graph_uri


SKIP_DIRS = {"__pycache__", ".git", ".hg", ".svn", "node_modules", "venv", ".venv", "env", ".env", ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", "*.egg-info"}

DEFAULT_EXTENSIONS = (
    ".py",
    ".ts", ".tsx", ".js", ".jsx",
    ".java",
    ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh",
    ".html", ".htm", ".css",
    ".json", ".yaml", ".yml", ".toml",
)


def _get_parser(file_path: str):
    """Return the appropriate parse_file function for the given file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".py":
        from .parser import parse_file
        return parse_file
    elif ext in (".ts", ".tsx", ".js", ".jsx"):
        from .parser_ts import parse_file
        return parse_file
    elif ext == ".java":
        from .parser_java import parse_file
        return parse_file
    elif ext in (".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".hh"):
        from .parser_c import parse_file
        return parse_file
    elif ext in (".html", ".htm", ".css"):
        from .parser_web import parse_file
        return parse_file
    elif ext in (".json", ".yaml", ".yml", ".toml"):
        from .parser_config import parse_file
        return parse_file
    raise ValueError(f"Unsupported file extension: {ext}")


@dataclass
class IndexStats:
    files_indexed: int = 0
    total_triples: int = 0
    resolved_calls: int = 0
    errors: list[str] = field(default_factory=list)


def _should_skip(dir_name: str) -> bool:
    return dir_name in SKIP_DIRS or dir_name.endswith(".egg-info")


def index_file(file_path: str, root_path: str, store: CodeStore) -> int:
    """Index a single file. Clears old triples for this file first.

    Returns the number of triples inserted.
    """
    rel_path = os.path.relpath(file_path, root_path).replace("\\", "/")

    # Clear previous triples for this file
    store.clear_graph(str(graph_uri(rel_path)))

    # Parse and generate triples
    parse_file = _get_parser(file_path)
    info = parse_file(file_path)
    quads = module_to_quads(info, rel_path)
    return store.load_triples(quads)


def index_directory(
    root_path: str,
    store: CodeStore,
    extensions: tuple[str, ...] = DEFAULT_EXTENSIONS,
    resolve: bool = True,
) -> IndexStats:
    """Walk a directory and index all matching files.

    Args:
        root_path: Root directory to index.
        store: CodeStore instance to load triples into.
        extensions: File extensions to index.
        resolve: Whether to run call resolution after indexing.

    Returns:
        IndexStats with counts and any errors.
    """
    stats = IndexStats()
    root = Path(root_path).resolve()

    for dirpath, dirnames, filenames in os.walk(root):
        # Filter out directories we should skip (in-place to prevent os.walk from descending)
        dirnames[:] = [d for d in dirnames if not _should_skip(d)]

        for filename in filenames:
            if not any(filename.endswith(ext) for ext in extensions):
                continue

            file_path = os.path.join(dirpath, filename)
            try:
                count = index_file(file_path, str(root), store)
                stats.files_indexed += 1
                stats.total_triples += count
            except Exception as e:
                stats.errors.append(f"{file_path}: {e}")

    if resolve and stats.files_indexed > 0:
        from .resolver import resolve_calls
        stats.resolved_calls = resolve_calls(store)

    return stats
