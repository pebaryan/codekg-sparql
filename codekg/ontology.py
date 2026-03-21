"""RDF namespace definitions and URI helpers for the code ontology."""

from rdflib import Namespace, URIRef, Literal, XSD

# Namespaces
CODE = Namespace("https://codekg.dev/ontology#")
ENTITY = Namespace("https://codekg.dev/entity/")

# Classes
MODULE = CODE.Module
CLASS = CODE.Class
FUNCTION = CODE.Function
METHOD = CODE.Method
PARAMETER = CODE.Parameter
IMPORT = CODE.Import
VARIABLE = CODE.Variable

# Data properties
NAME = CODE.name
FILE_PATH = CODE.filePath
START_LINE = CODE.startLine
END_LINE = CODE.endLine
DOCSTRING = CODE.docstring
HAS_DECORATOR = CODE.hasDecorator
IMPORTS = CODE.imports

# Object properties
DEFINES = CODE.defines
CALLS = CODE.calls
RESOLVED_CALLS = CODE.resolvedCalls
INHERITS_FROM = CODE.inheritsFrom
HAS_PARAMETER = CODE.hasParameter

# User annotation properties
TAG = CODE.tag
NOTE = CODE.note
LINKS_TO = CODE.linksTo
LINK_LABEL = CODE.linkLabel

# Named graph for user annotations (survives re-indexing)
ANNOTATIONS_GRAPH = URIRef("https://codekg.dev/entity/_annotations#graph")


def entity_uri(file_path: str, kind: str, qualified_name: str) -> URIRef:
    """Mint a URI for a code entity.

    Pattern: https://codekg.dev/entity/{file_path}#{kind}.{qualified_name}
    Example: https://codekg.dev/entity/src/utils.py#Function.parse_config
    """
    # Normalize path separators to forward slashes
    file_path = file_path.replace("\\", "/")
    return URIRef(f"{ENTITY}{file_path}#{kind}.{qualified_name}")


def module_uri(file_path: str) -> URIRef:
    """Mint a URI for a module (file)."""
    file_path = file_path.replace("\\", "/")
    return URIRef(f"{ENTITY}{file_path}")


def graph_uri(file_path: str) -> URIRef:
    """Named graph URI for a file's triples (used for per-file updates)."""
    file_path = file_path.replace("\\", "/")
    return URIRef(f"{ENTITY}{file_path}#graph")


def literal_str(value: str) -> Literal:
    return Literal(value, datatype=XSD.string)


def literal_int(value: int) -> Literal:
    return Literal(value, datatype=XSD.integer)
