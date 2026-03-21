"""Tree-sitter based C/C++ parser."""

import os
from pathlib import Path

import tree_sitter_c as ts_c
import tree_sitter_cpp as ts_cpp
from tree_sitter import Language, Parser

from .parser import (
    ParameterInfo, FunctionInfo, ClassInfo, ImportInfo,
    VariableInfo, ModuleInfo,
)

_PARSERS = {
    ".c": Parser(Language(ts_c.language())),
    ".h": Parser(Language(ts_c.language())),
    ".cpp": Parser(Language(ts_cpp.language())),
    ".cc": Parser(Language(ts_cpp.language())),
    ".cxx": Parser(Language(ts_cpp.language())),
    ".hpp": Parser(Language(ts_cpp.language())),
    ".hh": Parser(Language(ts_cpp.language())),
}


def _node_text(node) -> str:
    return node.text.decode("utf-8")


def _extract_calls(node) -> list[str]:
    """Recursively extract function call names."""
    calls = []
    if node.type == "call_expression":
        func = node.child_by_field_name("function")
        if func:
            if func.type == "identifier":
                calls.append(_node_text(func))
            elif func.type in ("field_expression", "qualified_identifier"):
                calls.append(_node_text(func))
    for child in node.children:
        calls.extend(_extract_calls(child))
    return calls


def _extract_parameters(params_node) -> list[ParameterInfo]:
    params = []
    if params_node is None:
        return params
    for child in params_node.children:
        if child.type == "parameter_declaration":
            declarator = child.child_by_field_name("declarator")
            if declarator:
                if declarator.type == "identifier":
                    params.append(ParameterInfo(name=_node_text(declarator)))
                elif declarator.type == "pointer_declarator":
                    for sub in declarator.children:
                        if sub.type == "identifier":
                            params.append(ParameterInfo(name=_node_text(sub)))
                            break
        elif child.type == "optional_parameter_declaration":
            declarator = child.child_by_field_name("declarator")
            if declarator and declarator.type == "identifier":
                params.append(ParameterInfo(name=_node_text(declarator)))
    return params


def _parse_function(node) -> FunctionInfo:
    """Parse a function_definition."""
    declarator = node.child_by_field_name("declarator")
    name = "unknown"
    params_node = None

    # Navigate declarator to find name and parameters
    if declarator:
        if declarator.type == "function_declarator":
            name_node = declarator.child_by_field_name("declarator")
            params_node = declarator.child_by_field_name("parameters")
            if name_node:
                name = _node_text(name_node)
        elif declarator.type == "pointer_declarator":
            for sub in declarator.children:
                if sub.type == "function_declarator":
                    name_node = sub.child_by_field_name("declarator")
                    params_node = sub.child_by_field_name("parameters")
                    if name_node:
                        name = _node_text(name_node)
                    break

    body_node = node.child_by_field_name("body")

    return FunctionInfo(
        name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        parameters=_extract_parameters(params_node),
        decorators=[],
        docstring=None,
        calls=_extract_calls(body_node) if body_node else [],
    )


def _parse_cpp_class(node) -> ClassInfo:
    """Parse a C++ class_specifier or struct_specifier."""
    name = "anonymous"
    for child in node.children:
        if child.type == "type_identifier":
            name = _node_text(child)
            break

    bases = []
    for child in node.children:
        if child.type == "base_class_clause":
            for sub in child.children:
                if sub.type == "type_identifier":
                    bases.append(_node_text(sub))

    methods = []
    body = node.child_by_field_name("body")
    if body:
        for child in body.children:
            if child.type == "function_definition":
                methods.append(_parse_function(child))
            elif child.type == "declaration":
                # Could be a method declaration (no body)
                pass

    return ClassInfo(
        name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        bases=bases,
        decorators=[],
        docstring=None,
        methods=methods,
    )


def _parse_struct(node) -> ClassInfo:
    """Parse a C struct_specifier."""
    name = "anonymous"
    for child in node.children:
        if child.type == "type_identifier":
            name = _node_text(child)
            break

    return ClassInfo(
        name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        bases=[],
        decorators=[],
        docstring=None,
        methods=[],
    )


def _parse_include(node) -> ImportInfo:
    """Parse a preproc_include directive."""
    path = None
    for child in node.children:
        if child.type in ("string_literal", "system_lib_string"):
            path = _node_text(child).strip('<>"')
            break
    return ImportInfo(
        module=path,
        names=[path] if path else [],
        start_line=node.start_point[0] + 1,
    )


def parse_file(file_path: str) -> ModuleInfo:
    """Parse a C/C++ file and extract structural information."""
    ext = os.path.splitext(file_path)[1].lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        raise ValueError(f"Unsupported C/C++ extension: {ext}")

    source = Path(file_path).read_bytes()
    tree = parser.parse(source)
    root = tree.root_node
    is_cpp = ext in (".cpp", ".cc", ".cxx", ".hpp", ".hh")

    module = ModuleInfo(file_path=file_path)

    for node in root.children:
        if node.type == "function_definition":
            module.functions.append(_parse_function(node))
        elif node.type == "preproc_include":
            module.imports.append(_parse_include(node))
        elif node.type == "declaration":
            # Check for variable declarations at top level
            declarator = node.child_by_field_name("declarator")
            if declarator:
                if declarator.type == "init_declarator":
                    name_node = declarator.child_by_field_name("declarator")
                    if name_node and name_node.type == "identifier":
                        module.variables.append(VariableInfo(
                            name=_node_text(name_node),
                            start_line=node.start_point[0] + 1,
                        ))
                elif declarator.type == "identifier":
                    module.variables.append(VariableInfo(
                        name=_node_text(declarator),
                        start_line=node.start_point[0] + 1,
                    ))
        elif node.type == "struct_specifier":
            module.classes.append(_parse_struct(node))
        elif node.type == "type_definition":
            # typedef struct { ... } Name;
            for child in node.children:
                if child.type == "struct_specifier":
                    cls = _parse_struct(child)
                    # The typedef name comes from a type_identifier after the struct
                    for sibling in node.children:
                        if sibling.type == "type_identifier" and sibling != child:
                            cls.name = _node_text(sibling)
                            break
                    module.classes.append(cls)
        # C++ specific
        elif node.type == "class_specifier" and is_cpp:
            module.classes.append(_parse_cpp_class(node))
        elif node.type == "namespace_definition" and is_cpp:
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "class_specifier":
                        module.classes.append(_parse_cpp_class(child))
                    elif child.type == "function_definition":
                        module.functions.append(_parse_function(child))

    return module
