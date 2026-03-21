"""Tests for the undo mechanism."""

import os
import shutil

from codekg.store import CodeStore
from codekg.indexer import index_directory
from codekg import refactor as R
from codekg.undo import UndoStack, get_undo_stack

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


def _setup(tmp_path):
    dest = str(tmp_path / "project")
    shutil.copytree(FIXTURES, dest)
    store = CodeStore()
    index_directory(dest, store, extensions=(".py",), resolve=False)
    return store, dest


def test_rename_creates_undo_entry(tmp_path):
    store, root = _setup(tmp_path)
    stack = get_undo_stack()
    stack.clear()

    R.rename_symbol(store, root, "parse_config", "load_config")
    assert len(stack) >= 1
    history = stack.history()
    assert "rename" in history[-1]["label"]


def test_undo_rename(tmp_path):
    store, root = _setup(tmp_path)
    stack = get_undo_stack()
    stack.clear()

    config_py = os.path.join(root, "config.py")
    original = open(config_py).read()

    R.rename_symbol(store, root, "parse_config", "load_config", reindex=False)
    assert "def load_config" in open(config_py).read()

    result = R.undo_last()
    assert result["label"] == "rename parse_config -> load_config"
    assert open(config_py).read() == original


def test_undo_insert_code(tmp_path):
    store, root = _setup(tmp_path)
    stack = get_undo_stack()
    stack.clear()

    config_py = os.path.join(root, "config.py")
    original = open(config_py).read()

    R.insert_code(config_py, 1, "# new comment")
    assert "# new comment" in open(config_py).read()

    R.undo_last()
    assert open(config_py).read() == original


def test_undo_replace_lines(tmp_path):
    store, root = _setup(tmp_path)
    stack = get_undo_stack()
    stack.clear()

    config_py = os.path.join(root, "config.py")
    original = open(config_py).read()

    R.replace_lines(config_py, 1, 1, "# replaced")
    R.undo_last()
    assert open(config_py).read() == original


def test_undo_empty_stack():
    stack = get_undo_stack()
    stack.clear()
    result = R.undo_last()
    assert result == {}


def test_undo_history(tmp_path):
    store, root = _setup(tmp_path)
    stack = get_undo_stack()
    stack.clear()

    config_py = os.path.join(root, "config.py")
    R.insert_code(config_py, 1, "# first")
    R.insert_code(config_py, 1, "# second")

    history = R.undo_history()
    assert len(history) == 2


def test_undo_stack_persistence(tmp_path):
    backup_dir = str(tmp_path / "backups")
    stack = UndoStack(backup_dir=backup_dir)

    test_file = str(tmp_path / "test.txt")
    with open(test_file, "w") as f:
        f.write("original content")

    stack.save("test operation", [test_file])

    # Backup dir should have entry
    assert os.path.isdir(os.path.join(backup_dir, "entry_0"))

    # Modify file
    with open(test_file, "w") as f:
        f.write("modified content")

    # Undo
    entry = stack.undo()
    assert entry is not None
    assert open(test_file).read() == "original content"
