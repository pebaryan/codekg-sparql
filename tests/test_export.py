"""Tests for graph export module."""

import os

from codekg.store import CodeStore
from codekg.indexer import index_directory
from codekg import export as X

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


def _indexed_store() -> CodeStore:
    store = CodeStore()
    index_directory(FIXTURES, store, extensions=(".py",), resolve=False)
    return store


# --- Call graph ---

def test_call_graph_mermaid():
    store = _indexed_store()
    result = X.call_graph(store, fmt="mermaid")
    assert "graph TD" in result
    # Should contain some edges from the sample project
    assert "-->" in result


def test_call_graph_dot():
    store = _indexed_store()
    result = X.call_graph(store, fmt="dot")
    assert "digraph call_graph" in result
    assert "->" in result


def test_call_graph_with_root():
    store = _indexed_store()
    result = X.call_graph(store, root_function="create_app", depth=2, fmt="mermaid")
    assert "graph TD" in result
    assert "create_app" in result


def test_call_graph_root_not_found():
    store = _indexed_store()
    result = X.call_graph(store, root_function="nonexistent_xyz", fmt="mermaid")
    # Should return just the header with no edges
    assert "graph TD" in result


# --- Inheritance graph ---

def test_inheritance_mermaid():
    store = _indexed_store()
    result = X.inheritance_graph(store, fmt="mermaid")
    assert "graph TD" in result
    # BaseModel -> User, User -> AdminUser
    assert "User" in result
    assert "BaseModel" in result


def test_inheritance_dot():
    store = _indexed_store()
    result = X.inheritance_graph(store, fmt="dot")
    assert "digraph inheritance" in result
    assert "User" in result


# --- File dependency graph ---

def test_file_dependency_mermaid():
    store = _indexed_store()
    result = X.file_dependency_graph(store, fmt="mermaid")
    assert "graph TD" in result


def test_file_dependency_dot():
    store = _indexed_store()
    result = X.file_dependency_graph(store, fmt="dot")
    assert "digraph dependencies" in result
