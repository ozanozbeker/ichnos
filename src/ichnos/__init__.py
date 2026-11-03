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
    OutputColumn,
    Query,
    Relationship,
    Report,
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
    "OutputColumn",
    "Position",
    "Query",
    "Relationship",
    "Report",
    "Table",
    "TableKind",
    "Type",
    "UnparsedQuery",
    "dbml",
    "infer",
    "read",
]
