"""Tests for the Java parser."""

import os
import pytest

from codekg.parser_java import parse_file

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures", "sample_java_project")


def test_parse_class():
    info = parse_file(os.path.join(FIXTURES, "Animal.java"))
    assert len(info.classes) == 1
    cls = info.classes[0]
    assert cls.name == "Animal"


def test_class_methods():
    info = parse_file(os.path.join(FIXTURES, "Animal.java"))
    cls = info.classes[0]
    method_names = [m.name for m in cls.methods]
    assert "Animal" in method_names  # constructor
    assert "getName" in method_names
    assert "speak" in method_names


def test_class_inheritance():
    info = parse_file(os.path.join(FIXTURES, "Dog.java"))
    cls = info.classes[0]
    assert cls.name == "Dog"
    assert "Animal" in cls.bases


def test_annotations_as_decorators():
    info = parse_file(os.path.join(FIXTURES, "Dog.java"))
    cls = info.classes[0]
    speak = [m for m in cls.methods if m.name == "speak"][0]
    assert "Override" in speak.decorators


def test_imports():
    info = parse_file(os.path.join(FIXTURES, "Animal.java"))
    assert len(info.imports) == 2
    modules = [imp.module for imp in info.imports]
    assert "java.util" in modules


def test_interface():
    info = parse_file(os.path.join(FIXTURES, "Speakable.java"))
    assert len(info.classes) == 1
    cls = info.classes[0]
    assert cls.name == "Speakable"
    method_names = [m.name for m in cls.methods]
    assert "speak" in method_names
    assert "getName" in method_names


def test_method_calls():
    info = parse_file(os.path.join(FIXTURES, "Animal.java"))
    cls = info.classes[0]
    speak = [m for m in cls.methods if m.name == "speak"][0]
    assert "System.out.println" in speak.calls


def test_method_parameters():
    info = parse_file(os.path.join(FIXTURES, "Animal.java"))
    cls = info.classes[0]
    constructor = [m for m in cls.methods if m.name == "Animal"][0]
    param_names = [p.name for p in constructor.parameters]
    assert "name" in param_names
    assert "age" in param_names
