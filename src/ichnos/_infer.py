"""Combine the traces of every query into evidence for each table and column.

`_read` traces one query at a time, and this module counts evidence across queries (ADR 0001) and applies declarations (ADR 0008).
Evidence holds query indices, and the graph module turns each index into its `Query` record.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ichnos._read import (
        ColumnRef,
        Creation,
        Item,
        Position,
        TableKey,
        TableKind,
        Trace,
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


@dataclass(slots=True)
class DeclarationEvidence:
    """One distinct declaration and the creating queries that state it."""

    kind: TableKind
    columns: tuple[str, ...]
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
    complete: bool = False
    contradictions: list[Contradicting] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AmbiguousColumn:
    """An unqualified column in one query that several tables can hold."""

    index: int
    name: str
    candidates: tuple[TableKey, ...]


@dataclass(slots=True)
class Evidence:
    """The evidence of every query, combined."""

    tables: dict[TableKey, TableEvidence]
    ambiguous: list[AmbiguousColumn]


def combine(traces: Sequence[Trace]) -> Evidence:
    """Count each table's and column's evidence across the traces of the queries ichnos read."""
    tables: defaultdict[TableKey, TableEvidence] = defaultdict(TableEvidence)
    for index, trace in enumerate(traces):
        for key in trace.reads:
            tables[key].read.add(index)
        for write in trace.writes:
            tables[write.table].write.add(index)
    declarations = _Declarations(traces)
    ambiguous: dict[AmbiguousColumn, None] = {}
    for index, trace in enumerate(traces):
        for ref in trace.refs:
            candidates = declarations.settle(ref)
            if len(candidates) == 1:
                column = tables[candidates[0]].columns[ref.name]
                column.references[ref.position].add(index)
            else:
                # The reference gives evidence to no candidate (ADR 0001).
                ambiguous[AmbiguousColumn(index, ref.name, candidates)] = None
        for write in trace.writes:
            for name in declarations.mapped(write.table, write.values):
                tables[write.table].columns[name].references["insert"].add(index)
    declarations.record(tables)
    return Evidence(dict(tables), list(ambiguous))


class _Declarations:
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

    def mapped(
        self, table: TableKey, values: tuple[Item, ...] | None
    ) -> tuple[str, ...]:
        """Return the columns that an `INSERT` with no column list writes, by position."""
        columns = self.columns(table)
        expanded = None if values is None else self.expand(values)
        if columns is None or expanded is None or len(expanded) != len(columns):
            return ()
        return columns

    def record(self, tables: defaultdict[TableKey, TableEvidence]) -> None:
        """Add each declaration, its `declared` evidence and its contradictions to the tables."""
        for table, creations in self.creations.items():
            evidence = tables[table]
            for index, creation in zip(self.indices[table], creations, strict=True):
                names = self.expand(creation.columns) or tuple(
                    c for c in creation.columns if isinstance(c, str)
                )
                for name in names:
                    evidence.columns[name].declared.add(index)
                found = next(
                    (
                        d
                        for d in evidence.declarations
                        if (d.kind, d.columns) == (creation.kind, names)
                    ),
                    None,
                )
                if found is None:
                    declaration = DeclarationEvidence(creation.kind, names, {index})
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
                values = None if write.values is None else self.expand(write.values)
                if (
                    columns is not None
                    and values is not None
                    and len(values) != len(columns)
                ):
                    found[write.table].append((index, "value count", None))
        return dict(found)
