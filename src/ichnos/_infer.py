"""Combine the traces of every query into evidence for each table and column.

`_read` traces one query at a time, and this module counts evidence across queries (ADR 0001) and applies declarations (ADR 0008).
Evidence holds query indices, and the graph module turns each index into its `Query` record.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from ichnos._read import Fact

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ichnos._read import (
        ColumnRef,
        Creation,
        Item,
        KeyShape,
        Position,
        TableKey,
        TableKind,
        Trace,
        Type,
        Value,
    )

type ContradictionReason = Literal["undeclared column", "declaration", "value count"]
type Contradicting = tuple[int, ContradictionReason, str | None]


@dataclass(slots=True)
class ColumnEvidence:
    """The queries behind one column, by reference position, and the creating queries that declare it."""

    references: defaultdict[Position, set[int]] = field(
        default_factory=lambda: defaultdict(set)
    )
    declared: set[int] = field(default_factory=set)
    types: defaultdict[Type, set[int]] = field(default_factory=lambda: defaultdict(set))
    observed: defaultdict[str, set[int]] = field(
        default_factory=lambda: defaultdict(set)
    )
    nullable: set[int] = field(default_factory=set)

    def add(self, fact: Fact, index: int) -> None:
        """Add what one reference or one assigned value shows about the column."""
        if fact.type is not None:
            self.types[fact.type].add(index)
        for value in fact.observed:
            self.observed[value].add(index)
        if fact.nullable:
            self.nullable.add(index)


@dataclass(slots=True)
class DeclarationEvidence:
    """One distinct declaration and the creating queries that state it."""

    kind: TableKind
    columns: tuple[str, ...]
    types: dict[str, Type]
    indices: set[int]


@dataclass(slots=True)
class TableEvidence:
    """The queries that read, write and declare one table, and the evidence for each of its columns."""

    read: set[int] = field(default_factory=set)
    write: set[int] = field(default_factory=set)
    columns: defaultdict[str, ColumnEvidence] = field(
        default_factory=lambda: defaultdict(ColumnEvidence)
    )
    declarations: list[DeclarationEvidence] = field(default_factory=list)
    # The queries behind each set of columns that a query's shape shows is a key, by shape (ADR 0006).
    keys: defaultdict[tuple[str, ...], defaultdict[KeyShape, set[int]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(set))
    )
    complete: bool = False
    contradictions: list[Contradicting] = field(default_factory=list)

    def add(self, name: str, position: Position, fact: Fact, index: int) -> None:
        """Add one query's evidence for a column at one position."""
        self.columns[name].references[position].add(index)
        self.columns[name].add(fact, index)
        if fact.generated:
            self.keys[(name,)]["generated"].add(index)


@dataclass(frozen=True, slots=True)
class AmbiguousColumn:
    """An unqualified column in one query that several tables can hold."""

    index: int
    name: str
    candidates: tuple[TableKey, ...]


type Side = tuple[TableKey, tuple[str, ...]]
"""One side of a relationship: a table and its columns, aligned with the other side's."""


@dataclass(frozen=True, slots=True)
class ReportEvidence:
    """A query that reads tables and writes none, with each output column's name and value (ADR 0009)."""

    index: int
    outputs: tuple[tuple[str, Fact], ...]
    # The output column names of each select-list item, which a `*` can expand to several or none.
    items: tuple[tuple[str, ...], ...]


@dataclass(slots=True)
class Evidence:
    """The evidence of every query, combined."""

    tables: dict[TableKey, TableEvidence]
    ambiguous: list[AmbiguousColumn]
    # The queries behind each relationship, with its sides in name order (ADR 0002).
    relationships: dict[tuple[Side, Side], set[int]]
    reports: list[ReportEvidence]
    declarations: Declarations


def relationship(
    left: TableKey, right: TableKey, columns: Iterable[tuple[str, str]]
) -> tuple[Side, Side]:
    """Return a relationship's two sides in name order, with each side's columns aligned to the other's."""
    pairs = sorted(set(columns))
    forward = ((left, tuple(a for a, _ in pairs)), (right, tuple(b for _, b in pairs)))
    swapped = sorted((b, a) for a, b in pairs)
    backward = (
        (right, tuple(a for a, _ in swapped)),
        (left, tuple(b for _, b in swapped)),
    )
    return min(forward, backward, key=lambda r: [((t[0] or "", t[1]), c) for t, c in r])


def combine(traces: Sequence[Trace]) -> Evidence:
    """Count each table's and column's evidence across the traces of the queries ichnos read."""
    tables: defaultdict[TableKey, TableEvidence] = defaultdict(TableEvidence)
    for index, trace in enumerate(traces):
        for key in trace.reads:
            tables[key].read.add(index)
        for write in trace.writes:
            tables[write.table].write.add(index)
    declarations = Declarations(traces)
    ambiguous: dict[AmbiguousColumn, None] = {}
    for index, trace in enumerate(traces):
        for ref in trace.refs:
            candidates = declarations.settle(ref)
            if len(candidates) == 1:
                tables[candidates[0]].add(ref.name, ref.position, ref.fact, index)
            else:
                # The reference gives evidence to no candidate (ADR 0001).
                ambiguous[AmbiguousColumn(index, ref.name, candidates)] = None
        for write in trace.writes:
            for name, fact in declarations.mapped(write.table, write.values):
                tables[write.table].add(name, "insert", fact, index)
        for key in trace.keys:
            tables[key.table].keys[key.columns][key.shape].add(index)
    declarations.record(tables)
    return Evidence(
        dict(tables),
        list(ambiguous),
        _relationships(traces, declarations),
        _reports(traces, declarations),
        declarations,
    )


def _reports(
    traces: Sequence[Trace], declarations: Declarations
) -> list[ReportEvidence]:
    """Return each query that reads a table and writes none, which is a report (ADR 0009)."""
    reports: list[ReportEvidence] = []
    for index, trace in enumerate(traces):
        if trace.statement != "select" or not trace.reads:
            continue
        outputs: list[tuple[str, Fact]] = []
        items: list[int] = []
        for item, value in trace.outputs:
            # A `*` that a declaration expands gives its columns, and one that stays unexpanded gives none.
            names = (
                [item] if isinstance(item, str) else declarations.columns(item) or ()
            )
            fact = value if isinstance(value, Fact) else Fact()
            outputs.extend((name, fact) for name in names)
            items.append(len(names))
        unique = _unique([n for n, _ in outputs])
        reports.append(
            ReportEvidence(
                index,
                tuple(zip(unique, (f for _, f in outputs), strict=True)),
                _split(unique, items),
            )
        )
    return reports


def _split(names: list[str], sizes: list[int]) -> tuple[tuple[str, ...], ...]:
    """Split a list of names into consecutive groups of the given sizes."""
    groups: list[tuple[str, ...]] = []
    start = 0
    for size in sizes:
        groups.append(tuple(names[start : start + size]))
        start += size
    return tuple(groups)


def _unique(names: list[str]) -> list[str]:
    """Give each repeated output column name a space and `(2)`, `(3)` and so on, skipping every name the report holds."""
    held = set(names)
    seen: set[str] = set()
    unique: list[str] = []
    for name in names:
        candidate, number = name, 2
        while candidate in seen:
            while (candidate := f"{name} ({number})") in held | seen:
                number += 1
        seen.add(candidate)
        unique.append(candidate)
    return unique


def _relationships(
    traces: Sequence[Trace], declarations: Declarations
) -> dict[tuple[Side, Side], set[int]]:
    found: defaultdict[tuple[Side, Side], set[int]] = defaultdict(set)
    for index, trace in enumerate(traces):
        for join in trace.joins:
            columns = join.columns
            if join.natural:
                # A NATURAL JOIN reads as USING over the names that two declarations share (ADR 0002).
                left = declarations.columns(join.left) or ()
                right = declarations.columns(join.right) or ()
                columns = tuple((n, n) for n in left if n in right)
            if columns:
                found[relationship(join.left, join.right, columns)].add(index)
    return dict(found)


class Declarations:
    """The declarations of every creating query, and the contradictions that stop ichnos using them (ADR 0008)."""

    def __init__(self, traces: Sequence[Trace]) -> None:
        self.traces = traces
        self.creations: defaultdict[TableKey, list[Creation]] = defaultdict(list)
        self.indices: defaultdict[TableKey, list[int]] = defaultdict(list)
        for index, trace in enumerate(traces):
            if trace.creation is not None:
                self.creations[trace.creation.table].append(trace.creation)
                self.indices[trace.creation.table].append(index)
        self.contradictions: dict[TableKey, list[Contradicting]] = {}
        # A contradiction stops a `*` expanding through its table, which can contradict another declaration.
        while new := {
            table: found
            for table, found in self._contradictions().items()
            if table not in self.contradictions
        }:
            self.contradictions |= new

    def expand(
        self, items: tuple[Item, ...], seen: frozenset[TableKey] = frozenset()
    ) -> tuple[str, ...] | None:
        """Expand each `*` through a usable declaration, or return None when one stays unexpanded."""
        names: list[str] = []
        for item in items:
            if isinstance(item, str):
                names.append(item)
                continue
            columns = None if item in seen else self.columns(item, seen | {item})
            if columns is None:
                return None
            names.extend(columns)
        return tuple(names)

    def columns(
        self, table: TableKey, seen: frozenset[TableKey] = frozenset()
    ) -> tuple[str, ...] | None:
        """Return a table's complete column list, or None when it has no usable declaration."""
        if table in self.contradictions or table not in self.creations:
            return None
        lists = {self.expand(c.columns, seen) for c in self.creations[table]}
        return lists.pop() if len(lists) == 1 else None

    def named(self, table: TableKey) -> set[str]:
        """Return every name that a declaration states for a table it still describes, complete or not."""
        if table in self.contradictions:
            return set()
        return {
            item
            for creation in self.creations.get(table, ())
            for item in creation.columns
            if isinstance(item, str)
        }

    def settle(self, ref: ColumnRef) -> tuple[TableKey, ...]:
        """Return the candidates left after the declarations assign or remove them (ADR 0008)."""
        first = ref.candidates[0]
        if len(first) == 1:
            return first
        for layer in ref.candidates:
            # Oracle raises ORA-00918 when two tables in one scope hold the name.
            declares = tuple(t for t in layer if ref.name in self.named(t))
            if declares:
                return declares
            remaining = tuple(
                t for t in layer if ref.name in (self.columns(t) or (ref.name,))
            )
            if remaining:
                return remaining
        # A reference whose every candidate lacks the column contradicts them all, so some layer keeps one.
        return first  # pragma: no cover

    def values(self, values: tuple[Value, ...] | None) -> tuple[Fact, ...] | None:
        """Expand each `*` among assigned values, or return None when one stays unexpanded."""
        if values is None:
            return None
        facts: list[Fact] = []
        for value in values:
            if isinstance(value, Fact):
                facts.append(value)
                continue
            columns = self.columns(value)
            if columns is None:
                return None
            # A value copied from a column shows nothing about the column it fills (ADR 0007).
            facts.extend(Fact() for _ in columns)
        return tuple(facts)

    def mapped(
        self, table: TableKey, values: tuple[Value, ...] | None
    ) -> tuple[tuple[str, Fact], ...]:
        """Return each column that an `INSERT` with no column list writes, with its value, by position."""
        columns = self.columns(table)
        facts = self.values(values)
        if columns is None or facts is None or len(facts) != len(columns):
            return ()
        return tuple(zip(columns, facts, strict=True))

    def record(self, tables: defaultdict[TableKey, TableEvidence]) -> None:
        """Add each declaration, its `declared` evidence and its contradictions to the tables."""
        for table, creations in self.creations.items():
            evidence = tables[table]
            for index, creation in zip(self.indices[table], creations, strict=True):
                names = self.expand(creation.columns) or tuple(
                    c for c in creation.columns if isinstance(c, str)
                )
                types = dict(zip(creation.columns, creation.types, strict=True))
                declared_types = {
                    n: t for n in names if (t := types.get(n)) is not None
                }
                for name in names:
                    evidence.columns[name].declared.add(index)
                for name, declared_type in declared_types.items():
                    evidence.columns[name].types[declared_type].add(index)
                found = next(
                    (
                        d
                        for d in evidence.declarations
                        if (d.kind, d.columns, d.types)
                        == (creation.kind, names, declared_types)
                    ),
                    None,
                )
                if found is None:
                    declaration = DeclarationEvidence(
                        creation.kind, names, declared_types, {index}
                    )
                    evidence.declarations.append(declaration)
                else:
                    found.indices.add(index)
            evidence.complete = self.columns(table) is not None
            evidence.contradictions = self.contradictions.get(table, [])

    def _contradictions(self) -> dict[TableKey, list[Contradicting]]:
        found: defaultdict[TableKey, list[Contradicting]] = defaultdict(list)
        for table, creations in self.creations.items():
            if len({(c.kind, self.expand(c.columns)) for c in creations}) > 1:
                found[table].extend(
                    (i, "declaration", None) for i in self.indices[table]
                )
        for index, trace in enumerate(self.traces):
            for ref in trace.refs:
                first = ref.candidates[0]
                candidates = first if len(first) == 1 else sum(ref.candidates, ())
                lists = [self.columns(t) for t in candidates]
                # Only a reference that resolves without a declaration counts, or one whose every candidate lacks it.
                if all(c is not None and ref.name not in c for c in lists):
                    for table in candidates:
                        found[table].append((index, "undeclared column", ref.name))
            for write in trace.writes:
                columns = self.columns(write.table)
                values = self.values(write.values)
                if (
                    columns is not None
                    and values is not None
                    and len(values) != len(columns)
                ):
                    found[write.table].append((index, "value count", None))
        return dict(found)
