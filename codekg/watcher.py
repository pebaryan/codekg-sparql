"""File watcher for live re-indexing using watchdog."""

import os
import threading
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .store import CodeStore
from .indexer import index_file, SKIP_DIRS
from .ontology import graph_uri

SUPPORTED_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx"}
DEBOUNCE_SECONDS = 0.3


class _CodeEventHandler(FileSystemEventHandler):
    def __init__(self, root_path: str, store: CodeStore, on_event=None):
        self._root = root_path
        self._store = store
        self._on_event = on_event
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _should_handle(self, path: str) -> bool:
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return False
        rel = os.path.relpath(path, self._root)
        parts = Path(rel).parts
        return not any(
            part in SKIP_DIRS or part.endswith(".egg-info")
            for part in parts[:-1]
        )

    def _debounced_reindex(self, file_path: str):
        with self._lock:
            if file_path in self._timers:
                self._timers[file_path].cancel()
            timer = threading.Timer(
                DEBOUNCE_SECONDS,
                self._do_reindex,
                args=[file_path],
            )
            self._timers[file_path] = timer
            timer.start()

    def _do_reindex(self, file_path: str):
        try:
            with self._lock:
                self._timers.pop(file_path, None)
            count = index_file(file_path, self._root, self._store)
            rel = os.path.relpath(file_path, self._root)
            if self._on_event:
                self._on_event(f"Re-indexed {rel} ({count} triples)")
        except Exception as e:
            if self._on_event:
                self._on_event(f"Error indexing {file_path}: {e}")

    def _do_delete(self, file_path: str):
        rel_path = os.path.relpath(file_path, self._root).replace("\\", "/")
        self._store.clear_graph(str(graph_uri(rel_path)))
        if self._on_event:
            self._on_event(f"Removed {rel_path} from graph")

    def on_created(self, event):
        if not event.is_directory and self._should_handle(event.src_path):
            self._debounced_reindex(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and self._should_handle(event.src_path):
            self._debounced_reindex(event.src_path)

    def on_deleted(self, event):
        if not event.is_directory and self._should_handle(event.src_path):
            with self._lock:
                if event.src_path in self._timers:
                    self._timers[event.src_path].cancel()
                    del self._timers[event.src_path]
            self._do_delete(event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            if self._should_handle(event.src_path):
                self._do_delete(event.src_path)
            if self._should_handle(event.dest_path):
                self._debounced_reindex(event.dest_path)


def watch_directory(root_path: str, store: CodeStore, on_event=None) -> Observer:
    """Start watching a directory for file changes.

    Args:
        root_path: Directory to watch.
        store: CodeStore to update.
        on_event: Optional callback(message: str) for status output.

    Returns:
        The watchdog Observer (already started). Call observer.stop() to stop.
    """
    handler = _CodeEventHandler(root_path, store, on_event=on_event)
    observer = Observer()
    observer.schedule(handler, root_path, recursive=True)
    observer.start()
    return observer
