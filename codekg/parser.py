"""Tree-sitter based Python parser that extracts structural information."""

from dataclasses import dataclass, field
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser


PY_LANGUAGE = Language(tspython.language())

_parser = Parser(PY_LANGUAGE)


@dataclass
class ParameterInfo:
    name: str


@dataclass
class FunctionInfo:
    name: str
    start_line: int
    end_line: int
    parameters: list[ParameterInfo] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    calls: list[str] = field(default_factory=list)


@dataclass
class ClassInfo:
    name: str
    start_line: int
    end_line: int
    bases: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    methods: list[FunctionInfo] = field(default_factory=list)


@dataclass
class ImportInfo:
    module: str | None
    names: list[str]
    start_line: int
    aliases: dict[str, str] = field(default_factory=dict)


@dataclass
class VariableInfo:
    name: str
    start_line: int


@dataclass
class ModuleInfo:
    file_path: str
    functions: list[FunctionInfo] = field(default_factory=list)
    classes: list[ClassInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    variables: list[VariableInfo] = field(default_factory=list)


def _node_text(node) -> str:
    return node.text.decode("utf-8")


def _extract_docstring(body_node) -> str | None:
    """Extract docstring from the first statement of a function/class body."""
    if body_node is None or body_node.child_count == 0:
        return None
    first = body_node.children[0]
    if first.type == "expression_statement" and first.child_count > 0:
        expr = first.children[0]
        if expr.type == "string":
            text = _node_text(expr)
            # Strip quotes
            for q in ('"""', "'''", '"', "'"):
                if text.startswith(q) and text.endswith(q):
                    return text[len(q):-len(q)]
    return None


def _extract_decorators(node) -> list[str]:
    """Extract decorator names from a decorated definition."""
    decorators = []
    for child in node.children:
        if child.type == "decorator":
            # The decorator node contains '@' and the expression
            for sub in child.children:
                if sub.type in ("identifier", "attribute", "call"):
                    decorators.append(_node_text(sub).split("(")[0])
                    break
    return decorators


def _extract_parameters(params_node) -> list[ParameterInfo]:
    """Extract parameter names from a parameters node."""
    params = []
    if params_node is None:
        return params
    for child in params_node.children:
        if child.type == "identifier":
            params.append(ParameterInfo(name=_node_text(child)))
        elif child.type in ("default_parameter", "typed_parameter", "typed_default_parameter"):
            # First child is the name identifier
            for sub in child.children:
                if sub.type == "identifier":
                    params.append(ParameterInfo(name=_node_text(sub)))
                    break
        elif child.type == "list_splat_pattern":
            for sub in child.children:
                if sub.type == "identifier":
                    params.append(ParameterInfo(name="*" + _node_text(sub)))
                    break
        elif child.type == "dictionary_splat_pattern":
            for sub in child.children:
                if sub.type == "identifier":
                    params.append(ParameterInfo(name="**" + _node_text(sub)))
                    break
    return params


def _extract_calls(node) -> list[str]:
    """Recursively extract function/method call names from an AST subtree."""
    calls = []
    if node.type == "call":
        func = node.child_by_field_name("function")
        if func:
            if func.type == "identifier":
                calls.append(_node_text(func))
            elif func.type == "attribute":
                calls.append(_node_text(func))
    for child in node.children:
        calls.extend(_extract_calls(child))
    return calls


def _parse_function(node) -> FunctionInfo:
    """Parse a function_definition node into FunctionInfo."""
    name = _node_text(node.child_by_field_name("name"))
    params_node = node.child_by_field_name("parameters")
    body_node = node.child_by_field_name("body")

    return FunctionInfo(
        name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        parameters=_extract_parameters(params_node),
        decorators=_extract_decorators(node),
        docstring=_extract_docstring(body_node),
        calls=_extract_calls(body_node) if body_node else [],
    )


def _parse_class(node) -> ClassInfo:
    """Parse a class_definition node into ClassInfo."""
    name = _node_text(node.child_by_field_name("name"))

    # Extract base classes
    bases = []
    superclasses = node.child_by_field_name("superclasses")
    if superclasses:
        for child in superclasses.children:
            if child.type == "identifier":
                bases.append(_node_text(child))
            elif child.type == "attribute":
                bases.append(_node_text(child))

    body_node = node.child_by_field_name("body")
    docstring = _extract_docstring(body_node)

    # Extract methods
    methods = []
    if body_node:
        for child in body_node.children:
            if child.type == "function_definition":
                methods.append(_parse_function(child))
            elif child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type == "function_definition":
                        func = _parse_function(sub)
                        func.decorators = _extract_decorators(child)
                        methods.append(func)

    return ClassInfo(
        name=name,
        start_line=node.start_point[0] + 1,
        end_line=node.end_point[0] + 1,
        bases=bases,
        decorators=_extract_decorators(node),
        docstring=docstring,
        methods=methods,
    )


def _parse_import(node) -> ImportInfo:
    """Parse an import_statement or import_from_statement."""
    if node.type == "import_statement":
        names = []
        for child in node.children:
            if child.type == "dotted_name":
                names.append(_node_text(child))
            elif child.type == "aliased_import":
                for sub in child.children:
                    if sub.type == "dotted_name":
                        names.append(_node_text(sub))
                        break
        return ImportInfo(module=None, names=names, start_line=node.start_point[0] + 1)
    else:  # import_from_statement
        module = None
        names = []
        for child in node.children:
            if child.type == "dotted_name" and module is None:
                module = _node_text(child)
            elif child.type == "relative_import":
                module = _node_text(child)
            elif child.type == "dotted_name" and module is not None:
                names.append(_node_text(child))
            elif child.type == "aliased_import":
                for sub in child.children:
                    if sub.type == "dotted_name" or sub.type == "identifier":
                        names.append(_node_text(sub))
                        break
            elif child.type == "identifier" and _node_text(child) not in ("from", "import"):
                names.append(_node_text(child))
        return ImportInfo(module=module, names=names, start_line=node.start_point[0] + 1)


def parse_file(file_path: str) -> ModuleInfo:
    """Parse a Python file and extract structural information.

    Args:
        file_path: Path to the Python file.

    Returns:
        ModuleInfo containing all extracted structural data.
    """
    source = Path(file_path).read_bytes()
    tree = _parser.parse(source)
    root = tree.root_node

    module = ModuleInfo(file_path=file_path)

    for node in root.children:
        if node.type == "function_definition":
            module.functions.append(_parse_function(node))
        elif node.type == "decorated_definition":
            for child in node.children:
                if child.type == "function_definition":
                    func = _parse_function(child)
                    func.decorators = _extract_decorators(node)
                    module.functions.append(func)
                elif child.type == "class_definition":
                    cls = _parse_class(child)
                    cls.decorators = _extract_decorators(node)
                    module.classes.append(cls)
        elif node.type == "class_definition":
            module.classes.append(_parse_class(node))
        elif node.type in ("import_statement", "import_from_statement"):
            module.imports.append(_parse_import(node))
        elif node.type == "expression_statement":
            # Check for module-level assignments
            for child in node.children:
                if child.type == "assignment":
                    left = child.child_by_field_name("left")
                    if left and left.type == "identifier":
                        module.variables.append(
                            VariableInfo(
                                name=_node_text(left),
                                start_line=node.start_point[0] + 1,
                            )
                        )

    return module
