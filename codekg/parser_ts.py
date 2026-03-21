"""Tree-sitter based TypeScript/JavaScript parser."""

import os
from pathlib import Path

import tree_sitter_typescript as ts_typescript
import tree_sitter_javascript as ts_javascript
from tree_sitter import Language, Parser

from .parser import (
    ParameterInfo, FunctionInfo, ClassInfo, ImportInfo,
    VariableInfo, ModuleInfo,
)

_PARSERS = {
    ".ts": Parser(Language(ts_typescript.language_typescript())),
    ".tsx": Parser(Language(ts_typescript.language_tsx())),
    ".js": Parser(Language(ts_javascript.language())),
    ".jsx": Parser(Language(ts_javascript.language())),
}


def _node_text(node) -> str:
    return node.text.decode("utf-8")


def _extract_docstring(body_node) -> str | None:
    """Extract a JSDoc-style comment preceding the node, or a leading string."""
    # TS/JS doesn't have Python-style docstrings; skip for now
    return None


def _extract_decorators(node) -> list[str]:
    """Extract decorator names from a node."""
    decorators = []
    for child in node.children:
        if child.type == "decorator":
            for sub in child.children:
                if sub.type in ("identifier", "call_expression"):
                    decorators.append(_node_text(sub).split("(")[0])
                    break
    return decorators


def _extract_parameters(params_node) -> list[ParameterInfo]:
    """Extract parameters from a formal_parameters node."""
    params = []
    if params_node is None:
        return params
    for child in params_node.children:
        if child.type == "identifier":
            params.append(ParameterInfo(name=_node_text(child)))
        elif child.type in ("required_parameter", "optional_parameter"):
            # First identifier child is the name
            pattern = child.child_by_field_name("pattern")
            if pattern and pattern.type == "identifier":
                params.append(ParameterInfo(name=_node_text(pattern)))
            else:
                for sub in child.children:
                    if sub.type == "identifier":
                        params.append(ParameterInfo(name=_node_text(sub)))
                        break
        elif child.type == "rest_pattern":
            for sub in child.children:
                if sub.type == "identifier":
                    params.append(ParameterInfo(name="..." + _node_text(sub)))
                    break
    return params


def _extract_calls(node) -> list[str]:
    """Recursively extract function/method call names from an AST subtree."""
    calls = []
    if node.type == "call_expression":
        func = node.child_by_field_name("function")
        if func:
            if func.type == "identifier":
                calls.append(_node_text(func))
            elif func.type == "member_expression":
                calls.append(_node_text(func))
    for child in node.children:
        calls.extend(_extract_calls(child))
    return calls


def _parse_function(node) -> FunctionInfo:
    """Parse a function_declaration or generator_function_declaration."""
    name = _node_text(node.child_by_field_name("name"))
    params_node = node.child_by_field_name("parameters")
    body_node = node.child_by_field_name("body")

    return FunctionInfo(
        name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        parameters=_extract_parameters(params_node),
        decorators=_extract_decorators(node),
        docstring=None,
        calls=_extract_calls(body_node) if body_node else [],
    )


def _parse_method(node) -> FunctionInfo:
    """Parse a method_definition inside a class body."""
    name = _node_text(node.child_by_field_name("name"))
    params_node = node.child_by_field_name("parameters")
    body_node = node.child_by_field_name("body")

    return FunctionInfo(
        name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        parameters=_extract_parameters(params_node),
        decorators=_extract_decorators(node),
        docstring=None,
        calls=_extract_calls(body_node) if body_node else [],
    )


def _parse_arrow_function(var_name: str, node, start_line: int, end_line: int) -> FunctionInfo:
    """Parse an arrow_function assigned to a variable."""
    params_node = node.child_by_field_name("parameters")
    body_node = node.child_by_field_name("body")

    return FunctionInfo(
        name=var_name,
        start_line=start_line,
        end_line=end_line,
        parameters=_extract_parameters(params_node),
        decorators=[],
        docstring=None,
        calls=_extract_calls(body_node) if body_node else [],
    )


def _parse_class(node) -> ClassInfo:
    """Parse a class_declaration or interface_declaration."""
    name = _node_text(node.child_by_field_name("name"))

    # Extract base classes from heritage clauses
    bases = []
    for child in node.children:
        if child.type == "class_heritage":
            for sub in child.children:
                if sub.type == "extends_clause":
                    for val in sub.children:
                        if val.type in ("identifier", "member_expression"):
                            bases.append(_node_text(val))
                elif sub.type == "implements_clause":
                    for val in sub.children:
                        if val.type in ("identifier", "type_identifier", "generic_type"):
                            text = _node_text(val).split("<")[0]
                            bases.append(text)

    # Extract methods from class body
    methods = []
    body_node = node.child_by_field_name("body")
    if body_node:
        for child in body_node.children:
            if child.type == "method_definition":
                methods.append(_parse_method(child))
            elif child.type == "public_field_definition":
                # Check if it's an arrow function property
                value = child.child_by_field_name("value")
                name_node = child.child_by_field_name("name")
                if value and value.type == "arrow_function" and name_node:
                    methods.append(_parse_arrow_function(
                        _node_text(name_node), value,
                        child.start_point[0] + 1, child.end_point[0] + 1
                    ))

    return ClassInfo(
        name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        bases=bases,
        decorators=_extract_decorators(node),
        docstring=None,
        methods=methods,
    )


def _parse_interface(node) -> ClassInfo:
    """Parse an interface_declaration as a ClassInfo."""
    name = _node_text(node.child_by_field_name("name"))

    bases = []
    for child in node.children:
        if child.type == "extends_type_clause":
            for sub in child.children:
                if sub.type in ("identifier", "generic_type"):
                    bases.append(_node_text(sub).split("<")[0])

    # Interface method signatures
    methods = []
    body_node = node.child_by_field_name("body")
    if body_node:
        for child in body_node.children:
            if child.type in ("method_signature", "property_signature"):
                name_node = child.child_by_field_name("name")
                if name_node:
                    methods.append(FunctionInfo(
                        name=_node_text(name_node),
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        parameters=[],
                        decorators=[],
                        docstring=None,
                        calls=[],
                    ))

    return ClassInfo(
        name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        bases=bases,
        decorators=[],
        docstring=None,
        methods=methods,
    )


def _parse_import_es(node) -> ImportInfo:
    """Parse an ES module import statement."""
    module = None
    names = []
    aliases = {}

    for child in node.children:
        if child.type == "string":
            # The module source string (strip quotes)
            raw = _node_text(child)
            module = raw.strip("'\"")
        elif child.type == "import_clause":
            for sub in child.children:
                if sub.type == "identifier":
                    # Default import: import Foo from '...'
                    names.append(_node_text(sub))
                elif sub.type == "named_imports":
                    for spec in sub.children:
                        if spec.type == "import_specifier":
                            original = None
                            alias = None
                            for part in spec.children:
                                if part.type == "identifier":
                                    if original is None:
                                        original = _node_text(part)
                                    else:
                                        alias = _node_text(part)
                            if original:
                                names.append(original)
                                if alias:
                                    aliases[alias] = original
                elif sub.type == "namespace_import":
                    # import * as Foo from '...'
                    for part in sub.children:
                        if part.type == "identifier":
                            names.append(_node_text(part))

    return ImportInfo(
        module=module,
        names=names,
        start_line=node.start_point[0] + 1,
        aliases=aliases,
    )


def _try_parse_require(node) -> ImportInfo | None:
    """Try to parse a CommonJS require() from a variable declaration."""
    # Looking for: const x = require("module")
    for child in node.children:
        if child.type == "variable_declarator":
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            if (name_node and value_node and
                    value_node.type == "call_expression"):
                func = value_node.child_by_field_name("function")
                if func and _node_text(func) == "require":
                    args = value_node.child_by_field_name("arguments")
                    if args:
                        for arg in args.children:
                            if arg.type == "string":
                                module_name = _node_text(arg).strip("'\"")
                                var_name = _node_text(name_node)
                                return ImportInfo(
                                    module=module_name,
                                    names=[var_name],
                                    start_line=node.start_point[0] + 1,
                                )
    return None


def _try_parse_arrow_var(node) -> FunctionInfo | None:
    """Try to parse an arrow function from a variable declaration."""
    for child in node.children:
        if child.type == "variable_declarator":
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            if name_node and value_node and value_node.type == "arrow_function":
                return _parse_arrow_function(
                    _node_text(name_node), value_node,
                    node.start_point[0] + 1, node.end_point[0] + 1,
                )
    return None


def _parse_variable(node) -> VariableInfo | None:
    """Extract a variable declaration (if not an arrow function or require)."""
    for child in node.children:
        if child.type == "variable_declarator":
            name_node = child.child_by_field_name("name")
            value_node = child.child_by_field_name("value")
            if name_node and name_node.type == "identifier":
                # Skip if value is arrow function or require call
                if value_node and value_node.type in ("arrow_function",):
                    return None
                if value_node and value_node.type == "call_expression":
                    func = value_node.child_by_field_name("function")
                    if func and _node_text(func) == "require":
                        return None
                return VariableInfo(
                    name=_node_text(name_node),
                    start_line=node.start_point[0] + 1,
                )
    return None


def _process_node(node, module: ModuleInfo):
    """Process a top-level AST node and add results to module."""
    if node.type == "function_declaration":
        module.functions.append(_parse_function(node))

    elif node.type == "class_declaration":
        module.classes.append(_parse_class(node))

    elif node.type == "interface_declaration":
        module.classes.append(_parse_interface(node))

    elif node.type == "import_statement":
        module.imports.append(_parse_import_es(node))

    elif node.type in ("lexical_declaration", "variable_declaration"):
        # Could be: arrow function, require(), or plain variable
        req = _try_parse_require(node)
        if req:
            module.imports.append(req)
            return
        arrow = _try_parse_arrow_var(node)
        if arrow:
            module.functions.append(arrow)
            return
        var = _parse_variable(node)
        if var:
            module.variables.append(var)

    elif node.type == "export_statement":
        # Unwrap: process the inner declaration
        for child in node.children:
            if child.type in ("function_declaration", "class_declaration",
                              "interface_declaration", "lexical_declaration",
                              "variable_declaration"):
                _process_node(child, module)

    elif node.type == "expression_statement":
        # Check for assignment to module-level variable
        for child in node.children:
            if child.type == "assignment_expression":
                left = child.child_by_field_name("left")
                if left and left.type == "identifier":
                    module.variables.append(VariableInfo(
                        name=_node_text(left),
                        start_line=node.start_point[0] + 1,
                    ))


def parse_file(file_path: str) -> ModuleInfo:
    """Parse a TypeScript/JavaScript file and extract structural information."""
    ext = os.path.splitext(file_path)[1].lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        raise ValueError(f"Unsupported extension: {ext}")

    source = Path(file_path).read_bytes()
    tree = parser.parse(source)
    root = tree.root_node

    module = ModuleInfo(file_path=file_path)

    for node in root.children:
        _process_node(node, module)

    return module
