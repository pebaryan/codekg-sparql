"""Tree-sitter based JSON/YAML/TOML parser.

Extracts top-level keys as VariableInfo and section headers as ClassInfo.
"""

from pathlib import Path

import tree_sitter_json as ts_json
import tree_sitter_yaml as ts_yaml
import tree_sitter_toml as ts_toml
from tree_sitter import Language, Parser

from .parser import VariableInfo, ClassInfo, ModuleInfo

_PARSERS = {
    ".json": Parser(Language(ts_json.language())),
    ".yaml": Parser(Language(ts_yaml.language())),
    ".yml": Parser(Language(ts_yaml.language())),
    ".toml": Parser(Language(ts_toml.language())),
}


def _node_text(node) -> str:
    return node.text.decode("utf-8")


# --- JSON ---

def _parse_json_object(obj_node, prefix: str = "") -> tuple[list[VariableInfo], list[ClassInfo]]:
    """Extract keys from a JSON object node."""
    variables = []
    classes = []
    for child in obj_node.children:
        if child.type == "pair":
            key_node = child.child_by_field_name("key")
            value_node = child.child_by_field_name("value")
            if key_node is None:
                continue
            # Key text: strip quotes from string node
            key_text = _node_text(key_node).strip('"')
            qualified = f"{prefix}.{key_text}" if prefix else key_text

            if value_node and value_node.type == "object":
                classes.append(ClassInfo(
                    name=qualified,
                    start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1,
                    bases=[],
                    decorators=[],
                    docstring=None,
                    methods=[],
                ))
                sub_vars, sub_cls = _parse_json_object(value_node, prefix=qualified)
                variables.extend(sub_vars)
                classes.extend(sub_cls)
            else:
                variables.append(VariableInfo(
                    name=qualified,
                    start_line=child.start_point[0] + 1,
                ))
    return variables, classes


def _parse_json(root) -> ModuleInfo:
    module = ModuleInfo(file_path="")
    if root.children and root.children[0].type == "object":
        variables, classes = _parse_json_object(root.children[0])
        module.variables = variables
        module.classes = classes
    return module


# --- YAML ---

def _parse_yaml_mapping(mapping_node, prefix: str = "") -> tuple[list[VariableInfo], list[ClassInfo]]:
    """Extract keys from a YAML block_mapping node."""
    variables = []
    classes = []
    for child in mapping_node.children:
        if child.type != "block_mapping_pair":
            continue
        # First child with a scalar gives us the key
        key_text = None
        value_node = None
        for sub in child.children:
            if sub.type == "flow_node" and key_text is None:
                key_text = _node_text(sub).strip()
            elif sub.type == "block_node":
                value_node = sub
            elif sub.type == "flow_node" and key_text is not None:
                # Simple value (scalar)
                value_node = sub

        if key_text is None:
            continue
        qualified = f"{prefix}.{key_text}" if prefix else key_text

        # Check if value is a nested mapping
        is_mapping = False
        if value_node and value_node.type == "block_node":
            for inner in value_node.children:
                if inner.type == "block_mapping":
                    is_mapping = True
                    classes.append(ClassInfo(
                        name=qualified,
                        start_line=child.start_point[0] + 1,
                        end_line=child.end_point[0] + 1,
                        bases=[],
                        decorators=[],
                        docstring=None,
                        methods=[],
                    ))
                    sub_vars, sub_cls = _parse_yaml_mapping(inner, prefix=qualified)
                    variables.extend(sub_vars)
                    classes.extend(sub_cls)
                    break

        if not is_mapping:
            variables.append(VariableInfo(
                name=qualified,
                start_line=child.start_point[0] + 1,
            ))
    return variables, classes


def _parse_yaml(root) -> ModuleInfo:
    module = ModuleInfo(file_path="")
    # YAML: stream -> document -> block_node -> block_mapping
    for doc in root.children:
        if doc.type != "document":
            continue
        for block in doc.children:
            if block.type == "block_node":
                for inner in block.children:
                    if inner.type == "block_mapping":
                        variables, classes = _parse_yaml_mapping(inner)
                        module.variables.extend(variables)
                        module.classes.extend(classes)
    return module


# --- TOML ---

def _parse_toml(root) -> ModuleInfo:
    module = ModuleInfo(file_path="")
    for child in root.children:
        if child.type == "table":
            # Extract table name from bracket keys
            table_name = None
            for sub in child.children:
                if sub.type in ("bare_key", "dotted_key", "quoted_key"):
                    table_name = _node_text(sub)
                    break
            if table_name:
                module.classes.append(ClassInfo(
                    name=table_name,
                    start_line=child.start_point[0] + 1,
                    end_line=child.end_point[0] + 1,
                    bases=[],
                    decorators=[],
                    docstring=None,
                    methods=[],
                ))
            # Extract pairs within the table
            prefix = table_name or ""
            for sub in child.children:
                if sub.type == "pair":
                    key_node = None
                    for k in sub.children:
                        if k.type in ("bare_key", "dotted_key", "quoted_key"):
                            key_node = k
                            break
                    if key_node:
                        key_text = _node_text(key_node)
                        qualified = f"{prefix}.{key_text}" if prefix else key_text
                        module.variables.append(VariableInfo(
                            name=qualified,
                            start_line=sub.start_point[0] + 1,
                        ))
        elif child.type == "pair":
            # Top-level pair (no table header)
            key_node = None
            for k in child.children:
                if k.type in ("bare_key", "dotted_key", "quoted_key"):
                    key_node = k
                    break
            if key_node:
                module.variables.append(VariableInfo(
                    name=_node_text(key_node),
                    start_line=child.start_point[0] + 1,
                ))
    return module


# --- Public API ---

def parse_file(file_path: str) -> ModuleInfo:
    """Parse a JSON/YAML/TOML file and extract structural information."""
    ext = Path(file_path).suffix.lower()
    parser = _PARSERS.get(ext)
    if parser is None:
        raise ValueError(f"Unsupported config extension: {ext}")

    source = Path(file_path).read_bytes()
    tree = parser.parse(source)
    root = tree.root_node

    if ext == ".json":
        module = _parse_json(root)
    elif ext in (".yaml", ".yml"):
        module = _parse_yaml(root)
    elif ext == ".toml":
        module = _parse_toml(root)
    else:
        module = ModuleInfo(file_path=file_path)

    module.file_path = file_path
    return module
