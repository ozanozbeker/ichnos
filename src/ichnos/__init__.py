"""Infer an Oracle schema and its lineage from SQL queries alone."""

from ichnos._corpus import read
from ichnos._dbml import dbml
from ichnos._graph import (
    Ambiguity,
    AmbiguityKind,
    Column,
    Contradiction,
    Declaration,
    Graph,
    IchnosError,
    Key,
    NameMatch,
    Query,
    Relationship,
    Table,
    UnparsedQuery,
    infer,
)
from ichnos._infer import ContradictionReason
from ichnos._read import KeyShape, Position, TableKind, Type

__all__ = [
    "Ambiguity",
    "AmbiguityKind",
    "Column",
    "Contradiction",
    "ContradictionReason",
    "Declaration",
    "Graph",
    "IchnosError",
    "Key",
    "KeyShape",
    "NameMatch",
    "Position",
    "Query",
    "Relationship",
    "Table",
    "TableKind",
    "Type",
    "UnparsedQuery",
    "dbml",
    "infer",
    "read",
]
