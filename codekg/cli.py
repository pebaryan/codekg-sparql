"""CLI entry point for CodeKG."""

import json
import sys

import click

from .store import CodeStore
from .indexer import index_directory
from . import queries as Q
from .nl2sparql import ask as nl_ask


DEFAULT_STORE_PATH = ".codekg_store"


def _get_store(store_path: str) -> CodeStore:
    return CodeStore(path=store_path)


@click.group()
def cli():
    """CodeKG-RDF: Lightweight RDF/SPARQL Knowledge Graph for Local Codebases."""
    pass


@cli.command()
@click.argument("directory")
@click.option("--store-path", default=DEFAULT_STORE_PATH, help="Path for persistent store.")
@click.option("--no-resolve", is_flag=True, help="Skip call resolution post-processing.")
def index(directory, store_path, no_resolve):
    """Index a codebase into the knowledge graph."""
    store = _get_store(store_path)
    click.echo(f"Indexing {directory} ...")
    stats = index_directory(directory, store, resolve=not no_resolve)
    click.echo(f"Done. {stats.files_indexed} files, {stats.total_triples} triples, {stats.resolved_calls} calls resolved.")
    if stats.errors:
        click.echo(f"{len(stats.errors)} errors:")
        for err in stats.errors:
            click.echo(f"  {err}")


@cli.command("stats")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def stats_cmd(store_path):
    """Show store statistics."""
    store = _get_store(store_path)
    s = store.stats()
    click.echo(json.dumps(s, indent=2))


@cli.command("query")
@click.argument("sparql")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def query_cmd(sparql, store_path):
    """Execute a raw SPARQL query."""
    store = _get_store(store_path)
    results = store.query(sparql)
    click.echo(json.dumps(results, indent=2))


@cli.command("ask")
@click.argument("question")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
@click.option("--llm-url", default="http://localhost:8080/v1", help="OpenAI-compatible API base URL.")
@click.option("--model", default="local-model", help="Model name.")
def ask_cmd(question, store_path, llm_url, model):
    """Ask a natural language question about the code (requires local LLM)."""
    store = _get_store(store_path)
    result = nl_ask(question, store, base_url=llm_url, model=model)
    click.echo(f"Generated SPARQL:\n{result['sparql']}\n")
    if "error" in result:
        click.echo(f"Query error: {result['error']}")
        click.echo("The LLM generated invalid SPARQL. Try rephrasing your question.")
    else:
        click.echo(f"Results:")
        click.echo(json.dumps(result["results"], indent=2))


@cli.command("callers-of")
@click.argument("function_name")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def callers_of_cmd(function_name, store_path):
    """Find all callers of a function."""
    store = _get_store(store_path)
    results = Q.callers_of(store, function_name)
    click.echo(json.dumps(results, indent=2))


@cli.command("callees-of")
@click.argument("function_name")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def callees_of_cmd(function_name, store_path):
    """Find all functions called by a function."""
    store = _get_store(store_path)
    results = Q.callees_of(store, function_name)
    click.echo(json.dumps(results, indent=2))


@cli.command("impact-of")
@click.argument("function_name")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def impact_of_cmd(function_name, store_path):
    """Find transitive callers of a function (impact analysis)."""
    store = _get_store(store_path)
    results = Q.impact_of(store, function_name)
    click.echo(json.dumps(results, indent=2))


@cli.command("context")
@click.argument("function_name")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def context_cmd(function_name, store_path):
    """Show full context around a function (callers, callees, container)."""
    store = _get_store(store_path)
    result = Q.context_around(store, function_name)
    click.echo(json.dumps(result, indent=2))


@cli.command("search")
@click.argument("pattern")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def search_cmd(pattern, store_path):
    """Search entities by name."""
    store = _get_store(store_path)
    results = Q.search_by_name(store, pattern)
    click.echo(json.dumps(results, indent=2))


@cli.command("tag")
@click.argument("entity_name")
@click.argument("tag")
@click.option("--remove", is_flag=True, help="Remove the tag instead of adding it.")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def tag_cmd(entity_name, tag, remove, store_path):
    """Add or remove a tag on an entity."""
    from . import edits as E
    store = _get_store(store_path)
    try:
        if remove:
            E.remove_tag(store, entity_name, tag)
            click.echo(f"Removed tag '{tag}' from '{entity_name}'.")
        else:
            E.add_tag(store, entity_name, tag)
            click.echo(f"Tagged '{entity_name}' with '{tag}'.")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


@cli.command("note")
@click.argument("entity_name")
@click.argument("text")
@click.option("--remove", is_flag=True, help="Remove the note instead of adding it.")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def note_cmd(entity_name, text, remove, store_path):
    """Add or remove a note on an entity."""
    from . import edits as E
    store = _get_store(store_path)
    try:
        if remove:
            E.remove_note(store, entity_name, text)
            click.echo(f"Removed note from '{entity_name}'.")
        else:
            E.add_note(store, entity_name, text)
            click.echo(f"Added note to '{entity_name}'.")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


@cli.command("link")
@click.argument("from_entity")
@click.argument("to_entity")
@click.option("--label", default="", help="Label for the link.")
@click.option("--remove", is_flag=True, help="Remove the link instead of adding it.")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def link_cmd(from_entity, to_entity, label, remove, store_path):
    """Add or remove a link between two entities."""
    from . import edits as E
    store = _get_store(store_path)
    try:
        if remove:
            E.remove_link(store, from_entity, to_entity)
            click.echo(f"Removed link from '{from_entity}' to '{to_entity}'.")
        else:
            E.add_link(store, from_entity, to_entity, label=label)
            msg = f"Linked '{from_entity}' -> '{to_entity}'"
            if label:
                msg += f" (label: {label})"
            click.echo(msg + ".")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


@cli.command("annotations")
@click.argument("entity_name", required=False)
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def annotations_cmd(entity_name, store_path):
    """Show annotations (tags, notes, links) for an entity or all."""
    from . import edits as E
    store = _get_store(store_path)
    if entity_name:
        try:
            result = E.annotations_for(store, entity_name)
            click.echo(json.dumps(result, indent=2))
        except ValueError as e:
            click.echo(f"Error: {e}", err=True)
    else:
        tags = E.list_tags(store)
        notes = E.list_notes(store)
        links = E.list_links(store)
        click.echo(json.dumps({"tags": tags, "notes": notes, "links": links}, indent=2))


@cli.command("rename")
@click.argument("old_name")
@click.argument("new_name")
@click.argument("directory")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def rename_cmd(old_name, new_name, directory, store_path):
    """Rename a symbol across the codebase (uses tree-sitter for precision)."""
    from . import refactor as R
    store = _get_store(store_path)
    try:
        result = R.rename_symbol(store, directory, old_name, new_name)
        if result["files_modified"]:
            click.echo(f"Renamed '{old_name}' -> '{new_name}': {result['occurrences']} occurrences in {len(result['files_modified'])} files.")
            for f in result["files_modified"]:
                click.echo(f"  {f}")
        else:
            click.echo(f"No occurrences of '{old_name}' found.")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


@cli.command("add-function")
@click.argument("file_path")
@click.argument("code")
@click.argument("directory")
@click.option("--after", "after_entity", default=None, help="Insert after this entity.")
@click.option("--at-line", type=int, default=None, help="Insert at this line number.")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def add_function_cmd(file_path, code, directory, after_entity, at_line, store_path):
    """Add a function to a file."""
    from . import refactor as R
    store = _get_store(store_path)
    try:
        result = R.add_function(store, directory, file_path, code,
                                after_entity=after_entity, at_line=at_line)
        click.echo(f"Inserted code at line {result['line']} in {result['file']}.")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


@cli.command("replace-entity")
@click.argument("entity_name")
@click.argument("new_code")
@click.argument("directory")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def replace_entity_cmd(entity_name, new_code, directory, store_path):
    """Replace an entity's source code."""
    from . import refactor as R
    store = _get_store(store_path)
    try:
        result = R.replace_entity(store, directory, entity_name, new_code)
        click.echo(f"Replaced '{entity_name}': {result['lines_removed']} lines removed, {result['lines_added']} lines added.")
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)


@cli.command("insert-code")
@click.argument("file_path")
@click.argument("line", type=int)
@click.argument("code")
@click.option("--before", is_flag=True, help="Insert before the line (default: after).")
def insert_code_cmd(file_path, line, code, before):
    """Insert code at a specific line in a file."""
    from . import refactor as R
    pos = "before" if before else "after"
    result = R.insert_code(file_path, line, code, position=pos)
    click.echo(f"Inserted code {pos} line {line} in {result['file']}.")


@cli.command("repl")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def repl_cmd(store_path):
    """Start an interactive SPARQL REPL."""
    store = _get_store(store_path)
    click.echo("CodeKG SPARQL REPL. Type SPARQL queries (end with ;) or 'quit' to exit.")
    click.echo("Prefixes code: and rdf: are available.\n")

    buffer = []
    while True:
        try:
            prompt = "sparql> " if not buffer else "  ...> "
            line = input(prompt)
        except (EOFError, KeyboardInterrupt):
            click.echo("\nBye.")
            break

        if line.strip().lower() in ("quit", "exit", "\\q"):
            click.echo("Bye.")
            break

        buffer.append(line)
        full = "\n".join(buffer)

        if ";" in line:
            full = full.replace(";", "")
            # Auto-add prefixes if missing
            if "PREFIX" not in full.upper():
                full = Q.PREFIX + full
            try:
                results = store.query(full)
                click.echo(json.dumps(results, indent=2))
            except Exception as e:
                click.echo(f"Error: {e}")
            buffer = []


@cli.command("watch")
@click.argument("directory")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def watch_cmd(directory, store_path):
    """Watch a directory and re-index on file changes."""
    import time
    from .watcher import watch_directory

    store = _get_store(store_path)

    click.echo(f"Performing initial index of {directory} ...")
    stats = index_directory(directory, store)
    click.echo(f"Initial index: {stats.files_indexed} files, {stats.total_triples} triples, {stats.resolved_calls} calls resolved.")

    def on_event(message):
        click.echo(f"  [watch] {message}")

    click.echo(f"Watching {directory} for changes (Ctrl+C to stop)...")
    observer = watch_directory(directory, store, on_event=on_event)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        click.echo("\nStopping watcher...")
        observer.stop()
    observer.join()
    click.echo("Done.")


@cli.command("mcp-stdio")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
def mcp_stdio_cmd(store_path):
    """Start MCP server over stdio transport."""
    from .mcp_server import run
    run(transport="stdio", store_path=store_path)


@cli.command("mcp-sse")
@click.option("--store-path", default=DEFAULT_STORE_PATH)
@click.option("--port", default=8000, help="Port for SSE server.")
def mcp_sse_cmd(store_path, port):
    """Start MCP server over SSE transport."""
    from .mcp_server import run
    click.echo(f"Starting MCP SSE server on port {port}...")
    run(transport="sse", store_path=store_path, port=port)


def main():
    cli()


if __name__ == "__main__":
    main()
