"""Undo stack for refactoring operations.

Stores file snapshots before each refactoring operation so they can be
reverted.  The stack is in-memory (per session) with an optional on-disk
backup directory for persistence across sessions.
"""

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Snapshot:
    """A single file snapshot before a refactoring operation."""
    file_path: str          # absolute path
    content: bytes          # original file content
    timestamp: float = field(default_factory=time.time)


@dataclass
class UndoEntry:
    """One undoable operation: a label + all file snapshots."""
    label: str
    snapshots: list[Snapshot] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class UndoStack:
    """In-memory undo stack with optional disk persistence."""

    def __init__(self, backup_dir: str | None = None, max_entries: int = 50):
        self._stack: list[UndoEntry] = []
        self._max = max_entries
        self._backup_dir = backup_dir
        if backup_dir:
            os.makedirs(backup_dir, exist_ok=True)

    def save(self, label: str, file_paths: list[str]) -> UndoEntry:
        """Snapshot the given files before a refactoring operation.

        Args:
            label: Human-readable description (e.g. "rename foo -> bar").
            file_paths: Absolute paths of files about to be modified.

        Returns the created UndoEntry.
        """
        snapshots = []
        for fp in file_paths:
            if os.path.isfile(fp):
                content = Path(fp).read_bytes()
                snapshots.append(Snapshot(file_path=fp, content=content))

        entry = UndoEntry(label=label, snapshots=snapshots)
        self._stack.append(entry)

        # Trim oldest entries if over limit
        while len(self._stack) > self._max:
            self._stack.pop(0)

        # Persist to disk if configured
        if self._backup_dir:
            self._persist_entry(entry, len(self._stack) - 1)

        return entry

    def undo(self) -> UndoEntry | None:
        """Restore files from the most recent snapshot.

        Returns the UndoEntry that was reverted, or None if stack is empty.
        """
        if not self._stack:
            return None

        entry = self._stack.pop()
        for snap in entry.snapshots:
            Path(snap.file_path).write_bytes(snap.content)

        # Clean up disk backup
        if self._backup_dir:
            idx = len(self._stack)  # was at this index before pop
            entry_dir = os.path.join(self._backup_dir, f"entry_{idx}")
            if os.path.isdir(entry_dir):
                shutil.rmtree(entry_dir)

        return entry

    def history(self) -> list[dict]:
        """List all entries in the undo stack (most recent last)."""
        return [
            {
                "index": i,
                "label": e.label,
                "files": [s.file_path for s in e.snapshots],
                "timestamp": e.timestamp,
            }
            for i, e in enumerate(self._stack)
        ]

    def clear(self):
        """Clear the entire undo stack."""
        self._stack.clear()
        if self._backup_dir and os.path.isdir(self._backup_dir):
            shutil.rmtree(self._backup_dir)
            os.makedirs(self._backup_dir, exist_ok=True)

    def _persist_entry(self, entry: UndoEntry, index: int):
        """Write an entry to disk for persistence."""
        entry_dir = os.path.join(self._backup_dir, f"entry_{index}")
        os.makedirs(entry_dir, exist_ok=True)

        meta = {
            "label": entry.label,
            "timestamp": entry.timestamp,
            "files": [],
        }
        for i, snap in enumerate(entry.snapshots):
            backup_file = os.path.join(entry_dir, f"file_{i}.bak")
            Path(backup_file).write_bytes(snap.content)
            meta["files"].append({
                "original_path": snap.file_path,
                "backup_file": backup_file,
                "timestamp": snap.timestamp,
            })

        meta_file = os.path.join(entry_dir, "meta.json")
        Path(meta_file).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._stack)


# Module-level singleton for convenient access
_default_stack: UndoStack | None = None


def get_undo_stack(backup_dir: str | None = None) -> UndoStack:
    """Get or create the module-level UndoStack singleton."""
    global _default_stack
    if _default_stack is None:
        _default_stack = UndoStack(backup_dir=backup_dir)
    return _default_stack
