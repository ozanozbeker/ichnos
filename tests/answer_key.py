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
from sqlglot.optimizer.annotate_types import annotate_types
from sqlglot.optimizer.qualify import qualify
from sqlglot.schema import MappingSchema

import ichnos

if TYPE_CHECKING:
    from collections.abc import Iterator

FIXTURE = Path(__file__).parent / "fixtures" / "oracle_synthetic"
QUERIES = FIXTURE / "queries"
ANSWER_KEY = FIXTURE / "answer_key"

type Name = tuple[str, str]

_SYNONYM = re.compile(r"CREATE PUBLIC SYNONYM (\w+) FOR (\w+)\.(\w+)", re.IGNORECASE)
_LINK = re.compile(r"CREATE DATABASE LINK (\w+)", re.IGNORECASE)


@dataclass
class KeyColumn:
    # The type that ichnos would claim, or None when the answer key cannot say.
    type: ichnos.Type | None
    # None for a view's column, whose constraint the answer key does not state.
    not_null: bool | None


@dataclass
class KeyTable:
    owner: str
    name: str
    kind: Literal["base table", "view", "materialized view"]
    columns: dict[str, KeyColumn] = field(default_factory=dict)
    # Each primary key and unique constraint, as a set of column names.
    keys: list[frozenset[str]] = field(default_factory=list)


@dataclass(frozen=True)
class ForeignKey:
    child: Name
    columns: tuple[str, ...]
    parent: Name
    references: tuple[str, ...]

    def pairs(self) -> frozenset[tuple[tuple[Name, str], tuple[Name, str]]]:
        return frozenset(
            ((self.child, c), (self.parent, r))
            for c, r in zip(self.columns, self.references, strict=True)
        )


@dataclass
class AnswerKey:
    tables: dict[Name, KeyTable]
    synonyms: dict[str, Name]
    links: set[str]
    foreign_keys: list[ForeignKey] = field(default_factory=list)

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


def _type(data_type: exp.DataType | None) -> ichnos.Type | None:
    """Map an Oracle type to ichnos's: `CHAR` and `VARCHAR2` to text, `NUMBER` to number, `DATE` and `TIMESTAMP` to datetime."""
    if data_type is None:
        return None
    if data_type.is_type(*exp.DataType.TEXT_TYPES):
        return "text"
    if data_type.is_type(*exp.DataType.NUMERIC_TYPES):
        return "number"
    if data_type.is_type(*exp.DataType.TEMPORAL_TYPES):
        return "datetime"
    return None


def load() -> AnswerKey:
    text = (ANSWER_KEY / "schema.sql").read_text(encoding="utf-8")
    statements = [
        s
        for s in sqlglot.parse(text, read="oracle")
        if isinstance(s, exp.Create) and s.kind in {"TABLE", "VIEW"}
    ]
    tables: dict[Name, KeyTable] = {}
    for statement in statements:
        if statement.kind == "TABLE":
            schema = statement.this
            key = (_name(schema.this.args["db"]), _name(schema.this.this))
            columns = {
                _name(c.this): KeyColumn(
                    _type(c.args["kind"]),
                    any(
                        isinstance(k.kind, exp.NotNullColumnConstraint)
                        for k in c.constraints
                    ),
                )
                for c in schema.expressions
                if isinstance(c, exp.ColumnDef)
            }
            keys = [
                frozenset(
                    _name(i)
                    for i in (
                        c.expressions
                        if isinstance(c, exp.PrimaryKey)
                        else c.this.expressions
                    )
                )
                for constraint in schema.expressions
                if isinstance(constraint, exp.Constraint)
                for c in constraint.expressions
                if isinstance(c, exp.PrimaryKey | exp.UniqueColumnConstraint)
            ]
            tables[key] = KeyTable(*key, "base table", columns, keys)
    # A view's column takes the type that sqlglot infers from the base tables.
    mapping = MappingSchema(
        {
            owner: {
                t.name: {c: k.type or "UNKNOWN" for c, k in t.columns.items()}
                for t in tables.values()
                if t.owner == owner
            }
            for owner in {t.owner for t in tables.values()}
        },
        dialect="oracle",
    )
    for statement in statements:
        if statement.kind == "VIEW":
            table = statement.this
            key = (_name(table.args["db"]), _name(table.this))
            properties = statement.args.get("properties")
            materialized = properties is not None and any(
                isinstance(p, exp.MaterializedProperty) for p in properties.expressions
            )
            query = qualify(
                statement.expression.copy(), schema=mapping, dialect="oracle"
            )
            annotated = annotate_types(query, schema=mapping, dialect="oracle")
            columns = {
                p.alias_or_name.upper(): KeyColumn(_type(p.type), None)
                for p in annotated.selects
            }
            tables[key] = KeyTable(
                *key, "materialized view" if materialized else "view", columns
            )
    synonyms = {
        m[1].upper(): (m[2].upper(), m[3].upper()) for m in _SYNONYM.finditer(text)
    }
    links = {m[1].upper() for m in _LINK.finditer(text)}
    foreign_keys = [
        ForeignKey(
            (_name(alter.this.args["db"]), _name(alter.this.this)),
            tuple(_name(i) for i in fk.expressions),
            (_name(ref.this.args["db"]), _name(ref.this.this)),
            tuple(_name(i) for i in ref.expressions),
        )
        for alter in sqlglot.parse(text, read="oracle")
        if isinstance(alter, exp.Alter)
        for fk in alter.find_all(exp.ForeignKey)
        for ref in [fk.args["reference"].this]
    ]
    return AnswerKey(tables, synonyms, links, foreign_keys)


def lineage_rows() -> list[dict[str, str]]:
    with (ANSWER_KEY / "lineage.csv").open(encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def _split(name: str) -> tuple[str | None, str, str]:
    """Split a dotted column name into its owner, table and column."""
    *owner, table, column = name.split(".")
    return (owner[0] if owner else None, table, column)


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
    yield from _score_types(graph, key)
    yield from _score_keys(graph, key)
    yield from _score_relationships(graph, key)
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


def _single_type(column: ichnos.Column) -> ichnos.Type | None:
    """Return the one type that ichnos claims for a column, as the DBML file writes it."""
    declared = {
        d.types[column.name]
        for d in column.table.declarations
        if column.name in d.types
    }
    if len(declared) == 1:
        return declared.pop()
    return next(iter(column.types)) if len(column.types) == 1 else None


def _score_types(graph: ichnos.Graph, key: AnswerKey) -> Iterator[Deviation]:
    """Yield each type and nullable claim that the answer key contradicts. Recall is not checked for either."""
    for table in graph.tables:
        resolved = key.resolve(table.owner, table.name)
        if resolved is None:
            continue
        for column in table.columns:
            truth = key.tables[resolved].columns.get(column.name)
            subject = dbml_name(table.owner, table.name, column.name)
            claimed = _single_type(column)
            if (
                truth is not None
                and None not in {truth.type, claimed}
                and claimed != truth.type
            ):
                yield Deviation("type", subject, "extra")
            if truth is not None and column.nullable and truth.not_null:
                yield Deviation("nullable", subject, "extra")


def _score_keys(graph: ichnos.Graph, key: AnswerKey) -> Iterator[Deviation]:
    """Yield each key claim that matches no primary key or unique constraint, and each one that the claims miss."""
    claimed: set[tuple[Name, frozenset[str]]] = set()
    for table in graph.tables:
        resolved = key.resolve(table.owner, table.name)
        for claim in table.keys:
            columns = [c.name for c in claim.columns]
            if resolved is not None and frozenset(columns) in key.tables[resolved].keys:
                claimed.add((resolved, frozenset(columns)))
            else:
                yield Deviation(
                    "key",
                    f"{dbml_name(table.owner, table.name)}({', '.join(columns)})",
                    "extra",
                )
    for name, table in sorted(key.tables.items()):
        for columns in table.keys:
            if (name, columns) not in claimed:
                ordered = [c for c in table.columns if c in columns]
                yield Deviation(
                    "key", f"{dbml_name(*name)}({', '.join(ordered)})", "miss"
                )


def _score_relationships(graph: ichnos.Graph, key: AnswerKey) -> Iterator[Deviation]:
    """Yield each relationship that matches no foreign key, each shared reference that does not hold, and each missed foreign key."""
    claimed: set[ForeignKey] = set()
    for relationship in graph.relationships:
        sides = [_resolve_side(side, key) for side in relationship.sides]
        subject = _relationship_subject(relationship)
        found = next(
            (
                fk
                for fk in key.foreign_keys
                if None not in sides and _holds(relationship, sides, fk)
            ),
            None,
        )
        if found is None:
            yield Deviation("relationship", subject, "extra")
        else:
            claimed.add(found)
        if relationship.shared is not None:
            target = _resolve_side(relationship.shared.columns, key)
            refers = [
                any(_pairs(s, target) == fk.pairs() for fk in key.foreign_keys)
                for s in sides
            ]
            if not all(refers):
                yield Deviation("shared reference", subject, "extra")
    for fk in key.foreign_keys:
        if fk not in claimed:
            child = f"{dbml_name(*fk.child)}({', '.join(fk.columns)})"
            parent = f"{dbml_name(*fk.parent)}({', '.join(fk.references)})"
            yield Deviation("relationship", f"{child} > {parent}", "miss")


type ResolvedSide = tuple[tuple[Name, str], ...] | None


def _resolve_side(columns: tuple[ichnos.Column, ...], key: AnswerKey) -> ResolvedSide:
    table = key.resolve(columns[0].table.owner, columns[0].table.name)
    return None if table is None else tuple((table, c.name) for c in columns)


def _pairs(
    side: ResolvedSide, other: ResolvedSide
) -> frozenset[tuple[tuple[Name, str], tuple[Name, str]]]:
    return frozenset(zip(side or (), other or (), strict=False))


def _holds(
    relationship: ichnos.Relationship, sides: list[ResolvedSide], fk: ForeignKey
) -> bool:
    """Return whether a relationship's columns equal a foreign key's, with the referring side first when it has a direction."""
    forward = _pairs(sides[0], sides[1]) == fk.pairs()
    backward = _pairs(sides[1], sides[0]) == fk.pairs()
    return forward or (backward and relationship.direction is None)


def _relationship_subject(relationship: ichnos.Relationship) -> str:
    names = [
        f"{dbml_name(s[0].table.owner, s[0].table.name)}({', '.join(c.name for c in s)})"
        for s in relationship.sides
    ]
    return f" {'>' if relationship.direction else '<>'} ".join(names)


def _score_ambiguities(
    graph: ichnos.Graph, key: AnswerKey, claimed: set[tuple[Name, str]]
) -> Iterator[Deviation]:
    # The lineage scorer scores a dependency ambiguity.
    for ambiguity in (a for a in graph.ambiguities if a.kind != "dependency"):
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
        if ambiguity.kind == "type":
            owner, table, column = _split(ambiguity.subject)
            resolved = key.resolve(owner, table)
            truth = (
                None if resolved is None else key.tables[resolved].columns.get(column)
            )
            if resolved is not None and truth is not None and truth.type == candidate:
                truths.append((resolved, column))
        elif ambiguity.kind == "column":
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


LINEAGE_COLUMNS = (
    "file",
    "statement",
    "downstream_table",
    "downstream_column",
    "upstream_table",
    "upstream_column",
    "type",
    "subtype",
)
type Row = tuple[str, ...]
_DIRECT = {"IDENTITY", "TRANSFORMATION", "AGGREGATION"}


def _table_name(table: ichnos.Table, key: AnswerKey) -> str:
    """Return a table's name as `lineage.csv` writes it: through its synonym, with any database link."""
    name, _, link = table.name.partition("@")
    resolved = key.resolve(table.owner, name)
    owner, base = resolved if resolved is not None else (table.owner, name)
    return f"{owner}.{base}" + (f"@{link}" if link else "") if owner else base


def _end(
    end: ichnos.Table | ichnos.Column | ichnos.Report | ichnos.OutputColumn,
    key: AnswerKey,
) -> tuple[str, str]:
    match end:
        case ichnos.Table():
            return _table_name(end, key), ""
        case ichnos.Column():
            return _table_name(end.table, key), end.name
        case ichnos.Report():
            return "", ""
        case ichnos.OutputColumn():
            return "", end.name


def lineage_found(graph: ichnos.Graph, key: AnswerKey) -> set[Row]:
    """Return one row per subtype per query behind each dependency, in `lineage.csv`'s columns."""
    rows: set[Row] = set()
    for dependency in graph.dependencies:
        upstream = _end(dependency.upstream, key)
        downstream = _end(dependency.downstream, key)
        for subtype, queries in dependency.subtypes.items():
            kind = "DIRECT" if subtype in _DIRECT else "INDIRECT"
            for query in queries:
                rows.add(
                    (
                        f"{query.file}.sql",
                        str(query.position),
                        *downstream,
                        *upstream,
                        kind,
                        subtype,
                    )
                )
    return rows


def _ambiguous(
    graph: ichnos.Graph, key: AnswerKey
) -> list[tuple[ichnos.Ambiguity, tuple[str, str]]]:
    """Return each dependency ambiguity with its downstream end."""
    found: list[tuple[ichnos.Ambiguity, tuple[str, str]]] = []
    ends: list[ichnos.Table | ichnos.Column | ichnos.Report | ichnos.OutputColumn] = [
        *graph.tables,
        *(c for t in graph.tables for c in t.columns),
        *graph.reports,
        *(c for r in graph.reports for c in r.output_columns),
    ]
    found.extend(
        (ambiguity, _end(end, key))
        for end in ends
        for ambiguity in end.ambiguities
        if ambiguity.kind == "dependency"
    )
    return found


def score_lineage(
    graph: ichnos.Graph, key: AnswerKey, kinds: set[str]
) -> Iterator[tuple[Row, str]]:
    """Yield each `lineage.csv` row of the given types that is not a `match`, and each row ichnos claims that the key lacks."""
    expected = {
        tuple(r[c] for c in LINEAGE_COLUMNS)
        for r in lineage_rows()
        if r["type"] in kinds
    }
    found = {r for r in lineage_found(graph, key) if r[6] in kinds}
    ambiguous: set[Row] = set()
    for ambiguity, (table, column) in _ambiguous(graph, key):
        query = ambiguity.query
        assert query is not None
        candidates = set()
        for name in ambiguity.candidates:
            *owner, table_name, upstream = name.split(".")
            resolved = key.resolve(owner[0] if owner else None, table_name)
            candidates.add((".".join(resolved) if resolved else table_name, upstream))
        ambiguous |= {
            r
            for r in expected
            if r[:4] == (f"{query.file}.sql", str(query.position), table, column)
            and (r[4], r[5]) in candidates
        }
    for row in sorted(expected - found):
        yield row, "ambiguous" if row in ambiguous else "miss"
    for row in sorted(found - expected):
        yield row, "extra"


def lineage_deviations() -> dict[tuple[Row, str], str]:
    path = ANSWER_KEY / "lineage_deviations.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    return {
        (tuple(r[c] for c in LINEAGE_COLUMNS), r["outcome"]): r["reason"] for r in rows
    }
