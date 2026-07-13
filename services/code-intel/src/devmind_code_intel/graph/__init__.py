"""Code graph — the structural backbone (Neo4j).

All access goes through `CodeGraphPort`; no Cypher exists outside the adapter
(ADR-0004). Nodes: File, Symbol (incl. a per-file `<module>` symbol), Module,
Name (unresolved targets). Edges: DEFINES, CALLS, CALLS_UNRESOLVED, INHERITS,
IMPLEMENTS, IMPORTS.
"""

from .base import (
    CallRef,
    GraphFile,
    ImportRef,
    InheritRef,
    symbol_id,
)
from .neo4j_graph import Neo4jCodeGraph

__all__ = [
    "CallRef",
    "GraphFile",
    "ImportRef",
    "InheritRef",
    "Neo4jCodeGraph",
    "symbol_id",
]
