"""Tests for code analysis module."""

import os

from codekg.store import CodeStore
from codekg.indexer import index_directory
from codekg import analysis as A

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


def _indexed_store() -> CodeStore:
    store = CodeStore()
    index_directory(FIXTURES, store, extensions=(".py",), resolve=False)
    return store


def test_dead_functions():
    store = _indexed_store()
    dead = A.dead_functions(store)
    names = [d["name"] for d in dead]
    # has_permission is never called by anyone
    assert "has_permission" in names


def test_dead_functions_excludes_dunders():
    store = _indexed_store()
    dead = A.dead_functions(store)
    names = [d["name"] for d in dead]
    assert "__init__" not in names


def test_dead_functions_excludes_main():
    store = _indexed_store()
    dead = A.dead_functions(store)
    names = [d["name"] for d in dead]
    assert "main" not in names


def test_unused_imports():
    store = _indexed_store()
    unused = A.unused_imports(store)
    # dataclass is imported but never used as a call or entity name
    import_names = [u["importName"] for u in unused]
    assert any("dataclass" in name for name in import_names)


def test_function_metrics():
    store = _indexed_store()
    metrics = A.function_metrics(store)
    assert len(metrics) > 0
    # Sorted by size descending
    sizes = [m["size"] for m in metrics]
    assert sizes == sorted(sizes, reverse=True)
    # Each metric has required fields
    for m in metrics:
        assert "name" in m
        assert "size" in m
        assert "fan_in" in m
        assert "fan_out" in m


def test_class_metrics():
    store = _indexed_store()
    metrics = A.class_metrics(store)
    assert len(metrics) > 0
    names = [m["name"] for m in metrics]
    assert "User" in names or "BaseModel" in names
    for m in metrics:
        assert "size" in m
        assert "method_count" in m


def test_refactoring_candidates():
    store = _indexed_store()
    # Use low thresholds to get results from small fixture
    candidates = A.refactoring_candidates(store, min_size=2, min_fan_in=1)
    assert len(candidates) > 0


def test_circular_dependencies():
    store = _indexed_store()
    cycles = A.circular_dependencies(store)
    # Our sample project doesn't have circular deps
    assert isinstance(cycles, list)
