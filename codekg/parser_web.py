"""Tree-sitter based HTML/CSS parser.

HTML: extracts linked resources (CSS, JS) as ImportInfo, elements with id as VariableInfo.
CSS: extracts @import as ImportInfo, selectors (class/id/tag rules) as ClassInfo.
"""

from pathlib import Path

import tree_sitter_html as ts_html
import tree_sitter_css as ts_css
from tree_sitter import Language, Parser

from .parser import ImportInfo, VariableInfo, ClassInfo, ModuleInfo

_PARSERS = {
    ".html": Parser(Language(ts_html.language())),
    ".htm": Parser(Language(ts_html.language())),
    ".css": Parser(Language(ts_css.language())),
}


def _node_text(node) -> str:
    return node.text.decode("utf-8")


# --- HTML ---

def _get_attr(start_tag_node, attr_name: str) -> str | None:
    """Get the value of an attribute from a start_tag node."""
    for child in start_tag_node.children:
        if child.type == "attribute":
            name_node = None
            value_node = None
            for sub in child.children:
                if sub.type == "attribute_name":
                    name_node = sub
                elif sub.type == "quoted_attribute_value":
                    value_node = sub
            if name_node and _node_text(name_node) == attr_name and value_node:
                return _node_text(value_node).strip('"\'')
    return None


def _walk_html(node, module: ModuleInfo):
    """Recursively walk HTML tree to extract imports and ids."""
    if node.type in ("element", "script_element"):
        start_tag = None
        for child in node.children:
            if child.type == "start_tag":
                start_tag = child
                break
        if start_tag:
            tag_name = None
            for child in start_tag.children:
                if child.type == "tag_name":
                    tag_name = _node_text(child)
                    break

            # Extract linked resources as imports
            if tag_name == "link":
                href = _get_attr(start_tag, "href")
                rel = _get_attr(start_tag, "rel")
                if href and rel == "stylesheet":
                    module.imports.append(ImportInfo(
                        module=href,
                        names=[href],
                        start_line=node.start_point[0] + 1,
                    ))
            elif tag_name == "script":
                src = _get_attr(start_tag, "src")
                if src:
                    module.imports.append(ImportInfo(
                        module=src,
                        names=[src],
                        start_line=node.start_point[0] + 1,
                    ))

            # Extract elements with id as variables
            elem_id = _get_attr(start_tag, "id")
            if elem_id:
                module.variables.append(VariableInfo(
                    name=f"#{elem_id}",
                    start_line=node.start_point[0] + 1,
                ))

    for child in node.children:
        _walk_html(child, module)


def _parse_html(root) -> ModuleInfo:
    module = ModuleInfo(file_path="")
    _walk_html(root, module)
    return module


# --- CSS ---

def _selector_text(selectors_node) -> str:
    """Get the full selector text."""
    return _node_text(selectors_node).strip()


def _parse_css(root) -> ModuleInfo:
    module = ModuleInfo(file_path="")
    for child in root.children:
        if child.type == "import_statement":
            # Extract import path from string_value or call_expression(url(...))
            path = None
            for sub in child.children:
                if sub.type == "string_value":
                    path = _node_text(sub).strip("'\"")
                    break
                elif sub.type == "call_expression":
                    # url('...')
                    for arg in sub.children:
                        if arg.type == "arguments":
                            for inner in arg.children:
                                if inner.type == "string_value":
                                    path = _node_text(inner).strip("'\"")
                                    break
            if path:
                module.imports.append(ImportInfo(
                    module=path,
                    names=[path],
                    start_line=child.start_point[0] + 1,
                ))

        elif child.type == "rule_set":
            # Extract selector as a ClassInfo
            selectors_node = None
            for sub in child.children:
                if sub.type == "selectors":
                    selectors_node = sub
                    break
            if selectors_node:
                selector = _selector_text(selectors_node)
                module.classes.append(ClassInfo(
                    name=selector,
                    start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1,
                    bases=[],
                    decorators=[],
                    docstring=None,
                    methods=[],
                ))
    return module


# --- Public API ---

def parse_file(file_path: str) -> ModuleInfo:
    """Parse an HTML/CSS file and extract structural information."""
    ext = Path(file_path).suffix.lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        raise ValueError(f"Unsupported web extension: {ext}")

    source = Path(file_path).read_bytes()
    tree = parser.parse(source)
    root = tree.root_node

    if ext in (".html", ".htm"):
        module = _parse_html(root)
    elif ext == ".css":
        module = _parse_css(root)
    else:
        module = ModuleInfo(file_path=file_path)

    module.file_path = file_path
    return module
