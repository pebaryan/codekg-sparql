# CodeKG-RDF

**Lightweight RDF/SPARQL Knowledge Graph for Local Codebases + AI Agents**

Turn any codebase into a queryable RDF knowledge graph using **Tree-sitter** for multi-language parsing and **Oxigraph** as an embedded SPARQL store. Fully local, privacy-first — no cloud dependencies.

Built for **local AI coding agents** (7B–13B models via llama.cpp) to reason structurally about code: callers, callees, impact analysis, inheritance chains, cross-file references — without grep hell or huge context dumps.

## Why RDF/SPARQL?

- **Transitive queries** — SPARQL property paths (`code:resolvedCalls+`) give you full transitive call chains in one query
- **Pattern matching** — find complex structural patterns across files without writing custom graph traversal code
- **Standards-based** — RDF, OWL, SPARQL are W3C standards with decades of tooling
- **Inference-ready** — semantic reasoning (subtype-aware queries, polymorphic resolution) without manual edges
- **Lightweight** — Oxigraph runs embedded in-process, a few hundred MB, no external DB/server

## Features

### Multi-Language Parsing

Tree-sitter grammars extract functions, classes, methods, imports, calls, variables, and more:

| Language | Extensions | What's Extracted |
|---|---|---|
| Python | `.py` | Functions, classes, methods, imports, variables, decorators, docstrings, calls |
| TypeScript/JavaScript | `.ts` `.tsx` `.js` `.jsx` | Functions, arrow functions, classes, interfaces, ES/CommonJS imports, variables, calls |
| Java | `.java` | Classes, interfaces, enums, methods, constructors, annotations, imports, calls |
| C/C++ | `.c` `.h` `.cpp` `.cc` `.cxx` `.hpp` `.hh` | Functions, structs, typedefs, classes (C++), namespaces, includes, calls |
| HTML | `.html` `.htm` | Linked stylesheets/scripts (as imports), element IDs |
| CSS | `.css` | `@import` directives, selectors (class, ID, tag, pseudo) |
| JSON | `.json` | Top-level and nested keys, nested objects as sections |
| YAML | `.yaml` `.yml` | Top-level and nested keys, nested mappings as sections |
| TOML | `.toml` | Tables as sections, key-value pairs |

### Knowledge Graph

- **RDF triples** stored in Oxigraph with named graphs per file for incremental re-indexing
- **OWL ontology** ([`ontology/code.ttl`](ontology/code.ttl)) — 7 classes, 16 properties
- **Entity URIs** encode file path and kind: `https://codekg.dev/entity/src/app.py#Function.main`
- **Call resolution** — post-index pass resolves string call targets to actual entity URIs across files via `code:resolvedCalls`

### Querying

- **Raw SPARQL** — full SPARQL 1.1 against the embedded store
- **Pre-built queries** — `callers_of`, `callees_of`, `impact_of` (transitive), `context_around`, `search_by_name`, `class_hierarchy`, `all_functions`, `all_classes`
- **NL→SPARQL** — ask natural language questions, translated to SPARQL via a local LLM (OpenAI-compatible API)
- **Interactive REPL** — SPARQL REPL with auto-prefixes

### Annotations (Graph Edits)

User annotations stored in a dedicated named graph that survives re-indexing:

- **Tags** — label entities (`deprecated`, `entry-point`, `hot-path`)
- **Notes** — attach free-text notes to any entity
- **Links** — create labeled directed links between entities

### Source-Level Refactoring

Edit operations that modify actual source files, using tree-sitter for byte-accurate precision:

- **`rename_symbol`** — cross-file rename using AST identifier matching (won't touch substrings or string literals)
- **`replace_entity`** — replace a function/class body by name (KG lookup for file + line range)
- **`add_function`** — insert code after a named entity, at a line, or at end of file
- **`insert_code`** — insert code before/after any line

All operations auto re-index affected files so the KG stays in sync.

### File Watcher

`watchdog`-based watcher with per-file debouncing (0.3s). Monitors create/modify/delete/move events and incrementally re-indexes.

### MCP Server

[Model Context Protocol](https://modelcontextprotocol.io/) server exposing all capabilities as tools:

`index_codebase`, `callers_of`, `callees_of`, `impact_of`, `context_around`, `search`, `sparql_query`, `ask_question`, `stats`, `add_tag`, `remove_tag`, `add_note`, `remove_note`, `add_link`, `remove_link`, `annotations`, `rename_symbol`, `replace_entity`, `add_function_to_file`, `insert_code_at_line`

Supports **stdio** (for Claude Desktop, Cursor, etc.) and **SSE** transports.

## Installation

```bash
pip install -r requirements.txt
```

### Dependencies

```
tree-sitter, tree-sitter-python, tree-sitter-typescript, tree-sitter-javascript,
tree-sitter-java, tree-sitter-c, tree-sitter-cpp, tree-sitter-html, tree-sitter-css,
tree-sitter-json, tree-sitter-yaml, tree-sitter-toml,
pyoxigraph, rdflib, click, openai, watchdog, mcp
```

## Usage

### Index a codebase

```bash
python -m codekg index ./my-project
```

This parses all supported files, generates RDF triples, and loads them into the Oxigraph store (persisted in `.codekg_store/`).

### Query

```bash
# Pre-built queries
python -m codekg callers-of parse_config
python -m codekg callees-of create_app
python -m codekg impact-of parse_config     # transitive callers
python -m codekg context parse_config        # callers + callees + container
python -m codekg search "config"

# Raw SPARQL
python -m codekg query "PREFIX code: <https://codekg.dev/ontology#> SELECT ?f ?name WHERE { ?f a code:Function ; code:name ?name } LIMIT 10"

# Natural language (requires local LLM)
python -m codekg ask "which functions call parse_config?"

# Interactive REPL
python -m codekg repl
```

### Annotate

```bash
python -m codekg tag parse_config entry-point
python -m codekg tag parse_config entry-point --remove
python -m codekg note parse_config "Reads from config.yaml"
python -m codekg link create_app parse_config --label depends-on
python -m codekg annotations parse_config
```

### Refactor

```bash
python -m codekg rename parse_config load_config ./my-project
python -m codekg replace-entity parse_config "def parse_config(path):\n    return {}" ./my-project
python -m codekg add-function config.py "def helper():\n    pass" ./my-project --after parse_config
python -m codekg insert-code ./my-project/config.py 1 "# Copyright 2026" --before
```

### Watch for changes

```bash
python -m codekg watch ./my-project
```

### MCP Server

```bash
# stdio transport (for Claude Desktop, Cursor, etc.)
python -m codekg mcp-stdio

# SSE transport
python -m codekg mcp-sse --port 8000
```

## Architecture

```
codekg/
├── parser.py          # Python parser + shared dataclasses
├── parser_ts.py       # TypeScript/JavaScript parser
├── parser_java.py     # Java parser
├── parser_c.py        # C/C++ parser
├── parser_web.py      # HTML/CSS parser
├── parser_config.py   # JSON/YAML/TOML parser
├── ontology.py        # RDF namespace definitions, URI helpers
├── triples.py         # ModuleInfo → RDF quads
├── store.py           # Oxigraph wrapper (query, update, clear)
├── indexer.py         # Directory walker + parser dispatch
├── resolver.py        # Post-index call resolution
├── queries.py         # Pre-built SPARQL query templates
├── nl2sparql.py       # NL→SPARQL via local LLM
├── edits.py           # Graph annotations (tags, notes, links)
├── refactor.py        # Source-level refactoring (rename, replace, insert)
├── watcher.py         # File watcher with debouncing
├── mcp_server.py      # MCP server (stdio + SSE)
└── cli.py             # Click CLI
ontology/
└── code.ttl           # OWL ontology (Turtle)
```

### Data Flow

```
Source Files → Tree-sitter Parser → ModuleInfo (dataclasses)
    → RDF Quads → Oxigraph (named graph per file)
    → SPARQL Queries / NL→SPARQL / MCP Tools
    → Refactoring → File Edits → Re-index
```

### Key Design Decisions

- **Named graphs per file** — each file's triples live in their own named graph, enabling incremental re-indexing without full store rebuild
- **Two-tier call edges** — `code:calls` stores callee names as string literals at parse time; `code:resolvedCalls` links to actual entity URIs after a post-index resolution pass. Both are queryable.
- **Shared dataclasses** — all language parsers output the same `ModuleInfo`/`FunctionInfo`/`ClassInfo` dataclasses, so `triples.py` works unchanged for any language
- **Annotations survive re-indexing** — user tags/notes/links live in a dedicated `_annotations#graph`, separate from per-file graphs

## Tests

```bash
pytest tests/ -v
```

107 tests across 11 test files covering all parsers, the store, triple generation, queries, call resolution, annotations, and refactoring.
