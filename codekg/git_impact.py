"""Git diff → impact analysis.

Given a git diff (or branch comparison), find all changed entities and
compute their transitive callers to answer 'what does this change affect?'
"""

import os
import re
import subprocess
from pathlib import Path

from .store import CodeStore
from . import queries as Q

_PREFIX = """
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
"""


def _run_git(args: list[str], cwd: str) -> str:
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _parse_diff_stat(diff_output: str) -> list[dict]:
    """Parse unified diff to extract changed files and line ranges.

    Returns list of {file, hunks: [{start, count}]}.
    """
    files = []
    current_file = None
    hunks = []

    for line in diff_output.split("\n"):
        # +++ b/path/to/file.py
        if line.startswith("+++ b/"):
            if current_file and hunks:
                files.append({"file": current_file, "hunks": hunks})
            current_file = line[6:]
            hunks = []
        # @@ -old_start,old_count +new_start,new_count @@
        elif line.startswith("@@"):
            match = re.search(r'\+(\d+)(?:,(\d+))?', line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2)) if match.group(2) else 1
                hunks.append({"start": start, "count": count})

    if current_file and hunks:
        files.append({"file": current_file, "hunks": hunks})
    return files


def _entities_at_lines(store: CodeStore, file_path: str, line_ranges: list[dict]) -> list[dict]:
    """Find entities in a file whose line range overlaps with changed lines."""
    entities = Q.entities_in_file(store, file_path)
    changed = []
    for ent in entities:
        ent_start = int(ent.get("startLine", 0))
        ent_end = int(ent.get("endLine", ent_start))
        for hunk in line_ranges:
            hunk_start = hunk["start"]
            hunk_end = hunk_start + hunk["count"] - 1
            if ent_start <= hunk_end and ent_end >= hunk_start:
                changed.append(ent)
                break
    return changed


def diff_impact(
    store: CodeStore,
    root_path: str,
    ref: str = "HEAD",
    base: str | None = None,
) -> dict:
    """Analyze the impact of changes in a git diff.

    Args:
        store: Indexed CodeStore.
        root_path: Root of the git repository.
        ref: Git ref for the changes (default: HEAD, shows uncommitted changes).
        base: Base ref for comparison (e.g. 'main'). If None, diffs against working tree.

    Returns dict with:
        - changed_files: list of changed file paths
        - changed_entities: list of directly changed entities
        - impacted_entities: list of transitively affected entities (callers of changed)
    """
    root = str(Path(root_path).resolve())

    # Get the diff
    if base:
        diff_out = _run_git(["diff", f"{base}...{ref}", "--unified=0"], cwd=root)
    elif ref == "HEAD":
        # Uncommitted changes (staged + unstaged)
        diff_out = _run_git(["diff", "HEAD", "--unified=0"], cwd=root)
    else:
        diff_out = _run_git(["diff", f"{ref}~1..{ref}", "--unified=0"], cwd=root)

    parsed = _parse_diff_stat(diff_out)
    if not parsed:
        return {"changed_files": [], "changed_entities": [], "impacted_entities": []}

    changed_files = [p["file"] for p in parsed]
    all_changed_entities = []
    all_impacted = []
    seen_impacted = set()

    for file_info in parsed:
        entities = _entities_at_lines(store, file_info["file"], file_info["hunks"])
        all_changed_entities.extend(entities)

        # For each changed entity, find its transitive callers
        for ent in entities:
            name = ent.get("name", "")
            if not name:
                continue
            impact = Q.impact_of(store, name)
            for imp in impact:
                caller_name = imp.get("callerName", "")
                if caller_name and caller_name not in seen_impacted:
                    seen_impacted.add(caller_name)
                    all_impacted.append(imp)

    return {
        "changed_files": changed_files,
        "changed_entities": all_changed_entities,
        "impacted_entities": all_impacted,
        "summary": (
            f"{len(changed_files)} files changed, "
            f"{len(all_changed_entities)} entities directly modified, "
            f"{len(all_impacted)} entities transitively affected"
        ),
    }
