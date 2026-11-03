"""Read the synthetic corpus's answer key with sqlglot, and score a graph's claims against it (ADR 0015).

sqlglot parses the tables, views and constraints, and reads the synonyms and the database link as `Command`, so a regex reads those.
This module is the one file outside `ichnos._read` that may import sqlglot.
"""

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import sqlglot
from sqlglot import exp

if TYPE_CHECKING:
    from collections.abc import Iterator

    import ichnos

FIXTURE = Path(__file__).parent / "fixtures" / "oracle_synthetic"
QUERIES = FIXTURE / "queries"
ANSWER_KEY = FIXTURE / "answer_key"

type Name = tuple[str, str]

_SYNONYM = re.compile(r"CREATE PUBLIC SYNONYM (\w+) FOR (\w+)\.(\w+)", re.IGNORECASE)
_LINK = re.compile(r"CREATE DATABASE LINK (\w+)", re.IGNORECASE)


@dataclass
class KeyTable:
    owner: str
    name: str
    kind: Literal["base table", "view", "materialized view"]
    columns: list[str] = field(default_factory=list)


@dataclass
class AnswerKey:
    tables: dict[Name, KeyTable]
    synonyms: dict[str, Name]
    links: set[str]

    def resolve(self, owner: str | None, name: str) -> Name | None:
        """Return the answer key table that a claimed name refers to, through synonyms and database links."""
        if "@" in name:
            name, link = name.split("@", 1)
            if link not in self.links:
                return None
        if owner is None:
            return self.synonyms.get(name)
        return (owner, name) if (owner, name) in self.tables else None


def _name(identifier: exp.Expression) -> str:
    return (
        identifier.name
        if isinstance(identifier, exp.Identifier) and identifier.quoted
        else identifier.name.upper()
    )


def load() -> AnswerKey:
    text = (ANSWER_KEY / "schema.sql").read_text(encoding="utf-8")
    tables: dict[Name, KeyTable] = {}
    for statement in sqlglot.parse(text, read="oracle"):
        if not isinstance(statement, exp.Create) or statement.kind not in {
            "TABLE",
            "VIEW",
        }:
            continue
        schema = statement.this
        table = schema.this if isinstance(schema, exp.Schema) else schema
        key = (_name(table.args["db"]), _name(table.this))
        if isinstance(statement.expression, exp.Query):
            materialized = (
                any(
                    isinstance(p, exp.MaterializedProperty)
                    for p in statement.args["properties"].expressions
                )
                if statement.args.get("properties")
                else False
            )
            columns = [
                _name(p.args["alias"]) if isinstance(p, exp.Alias) else _name(p.this)
                for p in statement.expression.selects
            ]
            tables[key] = KeyTable(
                *key, "materialized view" if materialized else "view", columns
            )
        else:
            columns = [
                _name(c.this)
                for c in schema.expressions
                if isinstance(c, exp.ColumnDef)
            ]
            tables[key] = KeyTable(*key, "base table", columns)
    synonyms = {
        m[1].upper(): (m[2].upper(), m[3].upper()) for m in _SYNONYM.finditer(text)
    }
    links = {m[1].upper() for m in _LINK.finditer(text)}
    return AnswerKey(tables, synonyms, links)


def lineage_rows() -> list[dict[str, str]]:
    with (ANSWER_KEY / "lineage.csv").open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def dbml_name(*parts: str | None) -> str:
    """Return a dotted name as the DBML file writes it, quoting each part only when DBML needs it."""
    return ".".join(
        p if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", p) else f'"{p}"'
        for p in parts
        if p is not None
    )


@dataclass(frozen=True)
class Deviation:
    claim: str
    subject: str
    # "miss", "extra" or "ambiguous".
    outcome: str


def shown(key: AnswerKey) -> tuple[set[Name], set[tuple[Name, str]]]:
    """Return the tables and columns that `lineage.csv` names, which recall is checked against."""
    tables: set[Name] = set()
    columns: set[tuple[Name, str]] = set()
    for row in lineage_rows():
        for end in ("upstream", "downstream"):
            table, column = row[f"{end}_table"], row[f"{end}_column"]
            if table:
                resolved = key.resolve(*table.split(".", 1))
                assert resolved is not None, table
                tables.add(resolved)
                columns |= {(resolved, column)} if column else set()
    return tables, columns


def score_schema(graph: ichnos.Graph, key: AnswerKey) -> Iterator[Deviation]:
    """Yield every schema claim that is not a `match`, and every fact the corpus shows that ichnos misses."""
    # Each claimed table, as (table, ""), and each claimed column, as (table, column).
    claimed: set[tuple[Name, str]] = set()
    yield from _score_tables(graph, key, claimed)
    yield from _score_kinds(graph, key)
    yield from _score_ambiguities(graph, key, claimed)
    shown_tables, shown_columns = shown(key)
    for name in sorted(shown_tables - {t for t, c in claimed if not c}):
        yield Deviation("table", dbml_name(*name), "miss")
    for name, column in sorted(shown_columns - claimed):
        yield Deviation("column", dbml_name(*name, column), "miss")


def _score_tables(
    graph: ichnos.Graph, key: AnswerKey, claimed: set[tuple[Name, str]]
) -> Iterator[Deviation]:
    for table in graph.tables:
        resolved = key.resolve(table.owner, table.name)
        if resolved is None:
            yield Deviation("table", dbml_name(table.owner, table.name), "extra")
            continue
        claimed.add((resolved, ""))
        for column in table.columns:
            claimed.add((resolved, column.name))
            if column.name not in key.tables[resolved].columns:
                subject = dbml_name(table.owner, table.name, column.name)
                yield Deviation("column", subject, "extra")


def _score_kinds(graph: ichnos.Graph, key: AnswerKey) -> Iterator[Deviation]:
    """Yield each declared table whose kind differs from the answer key's, since recall is checked against every declared table."""
    for table in graph.tables:
        resolved = key.resolve(table.owner, table.name)
        if table.declarations and (
            resolved is None or table.kind != key.tables[resolved].kind
        ):
            yield Deviation("kind", dbml_name(table.owner, table.name), "extra")


def _score_ambiguities(
    graph: ichnos.Graph, key: AnswerKey, claimed: set[tuple[Name, str]]
) -> Iterator[Deviation]:
    for ambiguity in graph.ambiguities:
        truths = _truths(ambiguity, key)
        query = "" if ambiguity.query is None else f"{ambiguity.query.name}: "
        subject = f"{query}{ambiguity.subject}"
        # An ambiguity whose candidates hold the truth covers it, so the truth is no miss.
        claimed |= set(truths)
        yield Deviation("ambiguity", subject, "ambiguous" if truths else "extra")


def _truths(ambiguity: ichnos.Ambiguity, key: AnswerKey) -> list[tuple[Name, str]]:
    """Return the candidates of an ambiguity that hold in the answer key."""
    truths: list[tuple[Name, str]] = []
    for candidate in ambiguity.candidates:
        if ambiguity.kind == "column":
            owner, table, column = candidate.split(".")
            resolved = key.resolve(owner, table)
            if resolved is not None and column in key.tables[resolved].columns:
                truths.append((resolved, column))
        else:
            resolved = key.resolve(None, ambiguity.subject)
            if resolved is not None and resolved == tuple(candidate.split(".")):
                truths.append((resolved, ""))
    return truths


def schema_deviations() -> dict[Deviation, str]:
    path = ANSWER_KEY / "schema_deviations.csv"
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return {
        Deviation(r["claim"], r["subject"], r["outcome"]): r["reason"] for r in rows
    }
