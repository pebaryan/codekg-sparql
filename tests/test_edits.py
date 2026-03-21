"""Tests for curated edit operations."""

import os
import pytest

from codekg.store import CodeStore
from codekg.indexer import index_directory
from codekg import edits as E

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


def _indexed_store() -> CodeStore:
    store = CodeStore()
    index_directory(FIXTURES, store, extensions=(".py",), resolve=False)
    return store


# --- Tag tests ---

def test_add_tag():
    store = _indexed_store()
    E.add_tag(store, "parse_config", "entry-point")
    tags = E.list_tags(store, "parse_config")
    assert any(t["tag"] == "entry-point" for t in tags)


def test_remove_tag():
    store = _indexed_store()
    E.add_tag(store, "parse_config", "deprecated")
    E.remove_tag(store, "parse_config", "deprecated")
    tags = E.list_tags(store, "parse_config")
    assert not any(t["tag"] == "deprecated" for t in tags)


def test_list_all_tags():
    store = _indexed_store()
    E.add_tag(store, "parse_config", "entry-point")
    E.add_tag(store, "create_app", "important")
    all_tags = E.list_tags(store)
    names = [t["name"] for t in all_tags]
    assert "parse_config" in names
    assert "create_app" in names


# --- Note tests ---

def test_add_note():
    store = _indexed_store()
    E.add_note(store, "parse_config", "Reads from config.yaml")
    notes = E.list_notes(store, "parse_config")
    assert any(n["note"] == "Reads from config.yaml" for n in notes)


def test_remove_note():
    store = _indexed_store()
    E.add_note(store, "parse_config", "temp note")
    E.remove_note(store, "parse_config", "temp note")
    notes = E.list_notes(store, "parse_config")
    assert not any(n["note"] == "temp note" for n in notes)


def test_list_all_notes():
    store = _indexed_store()
    E.add_note(store, "parse_config", "note1")
    E.add_note(store, "create_app", "note2")
    all_notes = E.list_notes(store)
    names = [n["name"] for n in all_notes]
    assert "parse_config" in names
    assert "create_app" in names


# --- Link tests ---

def test_add_link():
    store = _indexed_store()
    E.add_link(store, "create_app", "parse_config", label="depends-on")
    links = E.list_links(store, "create_app")
    outgoing = [l for l in links if l.get("direction") == "outgoing"]
    assert any(l["otherName"] == "parse_config" for l in outgoing)


def test_remove_link():
    store = _indexed_store()
    E.add_link(store, "create_app", "parse_config")
    E.remove_link(store, "create_app", "parse_config")
    links = E.list_links(store, "create_app")
    outgoing = [l for l in links if l.get("direction") == "outgoing"]
    assert not any(l["otherName"] == "parse_config" for l in outgoing)


def test_list_all_links():
    store = _indexed_store()
    E.add_link(store, "create_app", "parse_config")
    all_links = E.list_links(store)
    assert any(
        l["fromName"] == "create_app" and l["toName"] == "parse_config"
        for l in all_links
    )


def test_incoming_link():
    store = _indexed_store()
    E.add_link(store, "create_app", "parse_config")
    links = E.list_links(store, "parse_config")
    incoming = [l for l in links if l.get("direction") == "incoming"]
    assert any(l["otherName"] == "create_app" for l in incoming)


# --- Annotations summary ---

def test_annotations_for():
    store = _indexed_store()
    E.add_tag(store, "parse_config", "hot-path")
    E.add_note(store, "parse_config", "perf sensitive")
    E.add_link(store, "create_app", "parse_config")
    result = E.annotations_for(store, "parse_config")
    assert len(result["tags"]) >= 1
    assert len(result["notes"]) >= 1
    assert len(result["links"]) >= 1  # incoming link from create_app


# --- Error handling ---

def test_tag_unknown_entity():
    store = _indexed_store()
    with pytest.raises(ValueError, match="Entity not found"):
        E.add_tag(store, "nonexistent_function_xyz", "test")


# --- Annotations survive re-indexing ---

def test_annotations_survive_reindex():
    store = _indexed_store()
    E.add_tag(store, "parse_config", "important")
    # Re-index (clears file graphs, not annotation graph)
    index_directory(FIXTURES, store, extensions=(".py",), resolve=False)
    tags = E.list_tags(store, "parse_config")
    assert any(t["tag"] == "important" for t in tags)


# --- Clear annotations ---

def test_clear_annotations():
    store = _indexed_store()
    E.add_tag(store, "parse_config", "test")
    E.add_note(store, "create_app", "test")
    E.clear_annotations(store)
    assert E.list_tags(store) == []
    assert E.list_notes(store) == []
