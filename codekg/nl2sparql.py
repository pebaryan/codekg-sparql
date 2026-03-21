"""Natural language to SPARQL translation via local LLM."""

import re

from openai import OpenAI

from .store import CodeStore


SYSTEM_PROMPT = """You are a SPARQL query generator for a code knowledge graph. You translate natural language questions about code into SPARQL queries.

## Ontology

Namespace: `https://codekg.dev/ontology#` (prefix `code:`)

### Classes
- code:Module — a source file
- code:Class — a class definition
- code:Function — a top-level function
- code:Method — a method (subclass of Function)
- code:Parameter — a function parameter
- code:Variable — a module-level variable

### Properties
- code:name (string) — entity name
- code:filePath (string) — relative file path (on Module)
- code:startLine (integer) — start line number
- code:endLine (integer) — end line number
- code:defines (object) — module/class defines a function/class/method
- code:calls (literal) — function/method calls another (value is callee name string)
- code:inheritsFrom (literal) — class inherits from (value is base class name string)
- code:imports (string) — module imports a name
- code:hasParameter (object) — function has parameter
- code:hasDecorator (string) — decorator name
- code:docstring (string) — docstring text

## CRITICAL Rules
- Always include PREFIX declarations for code: and rdf:
- IMPORTANT: code:calls stores the callee name as a STRING LITERAL, NOT a URI.
  So `?func code:calls "parse_config"` or `FILTER(CONTAINS(STR(?target), "parse_config"))`.
  NEVER do `?func code:calls ?target . ?target code:name "foo"` — that is WRONG.
- IMPORTANT: code:inheritsFrom stores the base class name as a STRING LITERAL, NOT a URI.
  So `?class code:inheritsFrom "BaseModel"` — NEVER join on it as a URI.
- Output ONLY the SPARQL query, no explanation

## Examples

Question: What functions call parse_config?
```sparql
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?caller ?name WHERE {
    ?caller code:calls ?target .
    ?caller code:name ?name .
    FILTER(CONTAINS(STR(?target), "parse_config"))
}
```

Question: What does the function load_data call?
```sparql
PREFIX code: <https://codekg.dev/ontology#>
SELECT ?callee WHERE {
    ?func code:name "load_data" .
    ?func code:calls ?callee .
}
```

Question: List all classes
```sparql
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?class ?name WHERE {
    ?class rdf:type code:Class .
    ?class code:name ?name .
}
ORDER BY ?name
```

Question: What classes inherit from BaseHandler?
```sparql
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?class ?name WHERE {
    ?class rdf:type code:Class .
    ?class code:name ?name .
    ?class code:inheritsFrom "BaseHandler" .
}
```

Question: Show all functions in utils.py
```sparql
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?func ?name ?startLine WHERE {
    ?module rdf:type code:Module .
    ?module code:filePath ?path .
    ?module code:defines ?func .
    ?func rdf:type code:Function .
    ?func code:name ?name .
    ?func code:startLine ?startLine .
    FILTER(CONTAINS(?path, "utils.py"))
}
ORDER BY ?startLine
```

Question: What are the methods of class UserService?
```sparql
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?method ?name WHERE {
    ?class rdf:type code:Class .
    ?class code:name "UserService" .
    ?class code:defines ?method .
    ?method rdf:type code:Method .
    ?method code:name ?name .
}
```

Question: What does the project import?
```sparql
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT DISTINCT ?import WHERE {
    ?module rdf:type code:Module .
    ?module code:imports ?import .
}
ORDER BY ?import
```

Question: Find functions with "parse" in their name
```sparql
PREFIX code: <https://codekg.dev/ontology#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?func ?name WHERE {
    ?func rdf:type code:Function .
    ?func code:name ?name .
    FILTER(CONTAINS(LCASE(?name), "parse"))
}
```
"""


def _extract_sparql(text: str) -> str:
    """Extract SPARQL query from LLM response."""
    # Try to find a fenced code block
    match = re.search(r"```(?:sparql)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return _repair_sparql(match.group(1).strip())
    # Otherwise, look for lines starting with PREFIX or SELECT
    lines = text.strip().split("\n")
    sparql_lines = []
    capturing = False
    for line in lines:
        stripped = line.strip()
        if stripped.upper().startswith(("PREFIX", "SELECT", "ASK", "CONSTRUCT", "DESCRIBE")):
            capturing = True
        if capturing:
            sparql_lines.append(line)
    raw = "\n".join(sparql_lines).strip() if sparql_lines else text.strip()
    return _repair_sparql(raw)


REQUIRED_PREFIXES = {
    "code:": "https://codekg.dev/ontology#",
    "rdf:": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "xsd:": "http://www.w3.org/2001/XMLSchema#",
}


def _repair_sparql(sparql: str) -> str:
    """Fix common SPARQL issues from small LLMs."""
    # Deduplicate PREFIX lines — keep the first binding for each prefix
    lines = sparql.split("\n")
    seen_prefixes = {}
    cleaned = []
    for line in lines:
        stripped = line.strip()
        match = re.match(r"PREFIX\s+(\S+:)\s+<(.+?)>", stripped, re.IGNORECASE)
        if match:
            prefix = match.group(1)
            if prefix not in seen_prefixes:
                seen_prefixes[prefix] = match.group(2)
                cleaned.append(line)
            # Skip duplicate prefix declarations
        else:
            cleaned.append(line)

    result = "\n".join(cleaned)

    # Force-correct the code: prefix if it was bound to the wrong namespace
    if "code:" in seen_prefixes and "codekg.dev" not in seen_prefixes["code:"]:
        result = re.sub(
            r"PREFIX code:\s+<[^>]+>",
            "PREFIX code: <https://codekg.dev/ontology#>",
            result,
        )
        seen_prefixes["code:"] = "https://codekg.dev/ontology#"

    # Inject any missing prefixes that are used in the query body
    prefix_block = []
    for prefix, uri in REQUIRED_PREFIXES.items():
        if prefix not in seen_prefixes and prefix in result:
            prefix_block.append(f"PREFIX {prefix} <{uri}>")
    if prefix_block:
        result = "\n".join(prefix_block) + "\n" + result

    return result


def nl_to_sparql(
    question: str,
    base_url: str = "http://localhost:8080/v1",
    model: str = "local-model",
    api_key: str = "not-needed",
) -> str:
    """Translate a natural language question to a SPARQL query using a local LLM.

    Args:
        question: Natural language question about the code.
        base_url: OpenAI-compatible API base URL.
        model: Model name to use.
        api_key: API key (most local servers don't need one).

    Returns:
        SPARQL query string.
    """
    client = OpenAI(base_url=base_url, api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0.0,
        max_tokens=1024,
    )

    raw = response.choices[0].message.content
    return _extract_sparql(raw)


def ask(
    question: str,
    store: CodeStore,
    base_url: str = "http://localhost:8080/v1",
    model: str = "local-model",
    api_key: str = "not-needed",
) -> dict:
    """End-to-end: NL question → SPARQL → execute → results.

    Returns dict with 'sparql' (the generated query), 'results' (query output),
    and optionally 'error' if the query failed.
    """
    sparql = nl_to_sparql(question, base_url=base_url, model=model, api_key=api_key)
    try:
        results = store.query(sparql)
        return {"sparql": sparql, "results": results}
    except Exception as e:
        return {"sparql": sparql, "results": [], "error": str(e)}
