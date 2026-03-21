"""Tree-sitter based Java parser."""

from pathlib import Path

import tree_sitter_java as ts_java
from tree_sitter import Language, Parser

from .parser import (
    ParameterInfo, FunctionInfo, ClassInfo, ImportInfo,
    VariableInfo, ModuleInfo,
)

_parser = Parser(Language(ts_java.language()))


def _node_text(node) -> str:
    return node.text.decode("utf-8")


def _extract_calls(node) -> list[str]:
    """Recursively extract method/function call names."""
    calls = []
    if node.type == "method_invocation":
        name = node.child_by_field_name("name")
        obj = node.child_by_field_name("object")
        if name:
            if obj:
                calls.append(f"{_node_text(obj)}.{_node_text(name)}")
            else:
                calls.append(_node_text(name))
    elif node.type == "object_creation_expression":
        type_node = node.child_by_field_name("type")
        if type_node:
            calls.append(_node_text(type_node))
    for child in node.children:
        calls.extend(_extract_calls(child))
    return calls


def _extract_parameters(params_node) -> list[ParameterInfo]:
    params = []
    if params_node is None:
        return params
    for child in params_node.children:
        if child.type == "formal_parameter" or child.type == "spread_parameter":
            name = child.child_by_field_name("name")
            if name:
                params.append(ParameterInfo(name=_node_text(name)))
    return params


def _extract_annotations(node) -> list[str]:
    """Extract Java annotations as decorators."""
    annotations = []
    for child in node.children:
        if child.type == "marker_annotation" or child.type == "annotation":
            name = child.child_by_field_name("name")
            if name:
                annotations.append(_node_text(name))
        elif child.type == "modifiers":
            for sub in child.children:
                if sub.type in ("marker_annotation", "annotation"):
                    name = sub.child_by_field_name("name")
                    if name:
                        annotations.append(_node_text(name))
    return annotations


def _parse_method(node) -> FunctionInfo:
    """Parse a method_declaration or constructor_declaration."""
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node) if name_node else "<constructor>"
    params_node = node.child_by_field_name("parameters")
    body_node = node.child_by_field_name("body")

    return FunctionInfo(
        name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        parameters=_extract_parameters(params_node),
        decorators=_extract_annotations(node),
        docstring=None,
        calls=_extract_calls(body_node) if body_node else [],
    )


def _parse_class(node) -> ClassInfo:
    """Parse a class_declaration or interface_declaration."""
    name_node = node.child_by_field_name("name")
    name = _node_text(name_node) if name_node else "Unknown"

    bases = []
    for child in node.children:
        if child.type == "superclass":
            for sub in child.children:
                if sub.type == "type_identifier":
                    bases.append(_node_text(sub))
        elif child.type in ("super_interfaces", "extends_interfaces"):
            for sub in child.children:
                if sub.type == "type_list":
                    for t in sub.children:
                        if t.type == "type_identifier":
                            bases.append(_node_text(t))

    methods = []
    body_node = node.child_by_field_name("body")
    if body_node:
        for child in body_node.children:
            if child.type in ("method_declaration", "constructor_declaration"):
                methods.append(_parse_method(child))

    return ClassInfo(
        name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        bases=bases,
        decorators=_extract_annotations(node),
        docstring=None,
        methods=methods,
    )


def _parse_import(node) -> ImportInfo:
    """Parse an import_declaration."""
    text = _node_text(node).replace("import ", "").replace(";", "").strip()
    # Remove static keyword if present
    text = text.replace("static ", "")
    parts = text.rsplit(".", 1)
    if len(parts) == 2:
        return ImportInfo(module=parts[0], names=[parts[1]], start_line=node.start_point[0] + 1)
    return ImportInfo(module=None, names=[text], start_line=node.start_point[0] + 1)


def parse_file(file_path: str) -> ModuleInfo:
    """Parse a Java file and extract structural information."""
    source = Path(file_path).read_bytes()
    tree = _parser.parse(source)
    root = tree.root_node

    module = ModuleInfo(file_path=file_path)

    for node in root.children:
        if node.type == "class_declaration":
            module.classes.append(_parse_class(node))
        elif node.type == "interface_declaration":
            module.classes.append(_parse_class(node))
        elif node.type == "enum_declaration":
            module.classes.append(_parse_class(node))
        elif node.type == "import_declaration":
            module.imports.append(_parse_import(node))
        elif node.type == "method_declaration":
            module.functions.append(_parse_method(node))

    return module
