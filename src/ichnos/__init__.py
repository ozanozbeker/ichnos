"""Infer an Oracle schema and its lineage from SQL queries alone."""

from ichnos._corpus import read
from ichnos._dbml import dbml
from ichnos._graph import (
    Ambiguity,
    AmbiguityKind,
    Column,
    Contradiction,
    Declaration,
    Dependency,
    Graph,
    IchnosError,
    Key,
    NameMatch,
    OutputColumn,
    Query,
    Relationship,
    Report,
    Rollup,
    Table,
    UnparsedQuery,
    infer,
)
from ichnos._infer import ContradictionReason
from ichnos._read import KeyShape, Position, Subtype, TableKind, Type

__all__ = [
    "Ambiguity",
    "AmbiguityKind",
    "Column",
    "Contradiction",
    "ContradictionReason",
    "Declaration",
    "Dependency",
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
    "Rollup",
    "Subtype",
    "Table",
    "TableKind",
    "Type",
    "UnparsedQuery",
    "dbml",
    "infer",
    "read",
]
