"""Convert parsed ModuleInfo into RDF quads for Oxigraph."""

import pyoxigraph as ox

from .ontology import (
    CODE, entity_uri, module_uri, graph_uri, literal_str, literal_int,
    DEFINES, CALLS, INHERITS_FROM, HAS_PARAMETER, NAME, FILE_PATH,
    START_LINE, END_LINE, DOCSTRING, HAS_DECORATOR, IMPORTS,
)
from .parser import ModuleInfo, FunctionInfo, ClassInfo

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"


def _nn(uri) -> ox.NamedNode:
    """Convert a rdflib URIRef or string to an Oxigraph NamedNode."""
    return ox.NamedNode(str(uri))


def _lit(value: str) -> ox.Literal:
    return ox.Literal(value, datatype=ox.NamedNode("http://www.w3.org/2001/XMLSchema#string"))


def _lit_int(value: int) -> ox.Literal:
    return ox.Literal(str(value), datatype=ox.NamedNode("http://www.w3.org/2001/XMLSchema#integer"))


def _rdf_type() -> ox.NamedNode:
    return ox.NamedNode(RDF_TYPE)


def _function_triples(
    func: FunctionInfo,
    file_path: str,
    graph: ox.NamedNode,
    parent_uri: ox.NamedNode,
    is_method: bool = False,
    class_name: str | None = None,
) -> list[tuple]:
    """Generate triples for a function or method."""
    quads = []

    kind = "Method" if is_method else "Function"
    qualified_name = f"{class_name}.{func.name}" if class_name else func.name
    func_uri = _nn(entity_uri(file_path, kind, qualified_name))
    type_uri = _nn(CODE.Method) if is_method else _nn(CODE.Function)

    quads.append((func_uri, _rdf_type(), type_uri, graph))
    quads.append((func_uri, _nn(NAME), _lit(func.name), graph))
    quads.append((func_uri, _nn(START_LINE), _lit_int(func.start_line), graph))
    quads.append((func_uri, _nn(END_LINE), _lit_int(func.end_line), graph))
    quads.append((parent_uri, _nn(DEFINES), func_uri, graph))

    if func.docstring:
        quads.append((func_uri, _nn(DOCSTRING), _lit(func.docstring), graph))

    for dec in func.decorators:
        quads.append((func_uri, _nn(HAS_DECORATOR), _lit(dec), graph))

    for param in func.parameters:
        param_uri = _nn(entity_uri(file_path, "Parameter", f"{qualified_name}.{param.name}"))
        quads.append((param_uri, _rdf_type(), _nn(CODE.Parameter), graph))
        quads.append((param_uri, _nn(NAME), _lit(param.name), graph))
        quads.append((func_uri, _nn(HAS_PARAMETER), param_uri, graph))

    # Call edges — we store the callee name as a literal for now.
    # Resolution to actual URIs happens at query time or as a post-processing step,
    # since static call resolution across files requires the full index.
    for call_name in func.calls:
        quads.append((func_uri, _nn(CALLS), _lit(call_name), graph))

    return quads


def module_to_quads(info: ModuleInfo, rel_path: str) -> list[tuple]:
    """Convert a ModuleInfo into a list of Oxigraph quads.

    Args:
        info: Parsed module information.
        rel_path: Relative file path (used in URIs).

    Returns:
        List of (subject, predicate, object, graph) tuples with Oxigraph terms.
    """
    graph = _nn(graph_uri(rel_path))
    mod_uri = _nn(module_uri(rel_path))

    quads = []

    # Module
    quads.append((mod_uri, _rdf_type(), _nn(CODE.Module), graph))
    quads.append((mod_uri, _nn(NAME), _lit(rel_path), graph))
    quads.append((mod_uri, _nn(FILE_PATH), _lit(rel_path), graph))

    # Imports
    for imp in info.imports:
        for name in imp.names:
            full = f"{imp.module}.{name}" if imp.module else name
            quads.append((mod_uri, _nn(IMPORTS), _lit(full), graph))

    # Module-level variables
    for var in info.variables:
        var_uri = _nn(entity_uri(rel_path, "Variable", var.name))
        quads.append((var_uri, _rdf_type(), _nn(CODE.Variable), graph))
        quads.append((var_uri, _nn(NAME), _lit(var.name), graph))
        quads.append((var_uri, _nn(START_LINE), _lit_int(var.start_line), graph))
        quads.append((mod_uri, _nn(DEFINES), var_uri, graph))

    # Functions
    for func in info.functions:
        quads.extend(_function_triples(func, rel_path, graph, mod_uri))

    # Classes
    for cls in info.classes:
        cls_uri = _nn(entity_uri(rel_path, "Class", cls.name))
        quads.append((cls_uri, _rdf_type(), _nn(CODE.Class), graph))
        quads.append((cls_uri, _nn(NAME), _lit(cls.name), graph))
        quads.append((cls_uri, _nn(START_LINE), _lit_int(cls.start_line), graph))
        quads.append((cls_uri, _nn(END_LINE), _lit_int(cls.end_line), graph))
        quads.append((mod_uri, _nn(DEFINES), cls_uri, graph))

        if cls.docstring:
            quads.append((cls_uri, _nn(DOCSTRING), _lit(cls.docstring), graph))

        for dec in cls.decorators:
            quads.append((cls_uri, _nn(HAS_DECORATOR), _lit(dec), graph))

        for base in cls.bases:
            quads.append((cls_uri, _nn(INHERITS_FROM), _lit(base), graph))

        for method in cls.methods:
            quads.extend(
                _function_triples(method, rel_path, graph, cls_uri, is_method=True, class_name=cls.name)
            )

    return quads
