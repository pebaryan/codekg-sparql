"""Tests for RDF triple generation."""

import os

from codekg.parser import parse_file
from codekg.triples import module_to_quads

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_project")


def test_module_triples_generated():
    info = parse_file(os.path.join(FIXTURES, "config.py"))
    quads = module_to_quads(info, "config.py")
    assert len(quads) > 0


def test_module_has_type_triple():
    info = parse_file(os.path.join(FIXTURES, "config.py"))
    quads = module_to_quads(info, "config.py")
    type_triples = [q for q in quads if "rdf-syntax-ns#type" in str(q[1])]
    assert len(type_triples) > 0


def test_function_triples():
    info = parse_file(os.path.join(FIXTURES, "config.py"))
    quads = module_to_quads(info, "config.py")
    # Should have Function type assertions
    func_types = [
        q for q in quads
        if "rdf-syntax-ns#type" in str(q[1]) and "Function" in str(q[2])
    ]
    assert len(func_types) >= 2  # parse_config and validate_config


def test_class_triples():
    info = parse_file(os.path.join(FIXTURES, "models.py"))
    quads = module_to_quads(info, "models.py")
    class_types = [
        q for q in quads
        if "rdf-syntax-ns#type" in str(q[1]) and "Class" in str(q[2])
    ]
    assert len(class_types) >= 3  # BaseModel, User, AdminUser


def test_method_triples():
    info = parse_file(os.path.join(FIXTURES, "models.py"))
    quads = module_to_quads(info, "models.py")
    method_types = [
        q for q in quads
        if "rdf-syntax-ns#type" in str(q[1]) and "Method" in str(q[2])
    ]
    assert len(method_types) >= 4  # validate, __init__, greet, __init__, has_permission


def test_calls_triples():
    info = parse_file(os.path.join(FIXTURES, "app.py"))
    quads = module_to_quads(info, "app.py")
    call_triples = [q for q in quads if "calls" in str(q[1])]
    assert len(call_triples) > 0
    call_targets = [str(q[2]) for q in call_triples]
    # At least parse_config and validate_config should be in there
    assert any("parse_config" in t for t in call_targets)


def test_named_graph():
    info = parse_file(os.path.join(FIXTURES, "config.py"))
    quads = module_to_quads(info, "config.py")
    # All quads should have a graph component
    for q in quads:
        assert q[3] is not None
        assert "config.py" in str(q[3])
