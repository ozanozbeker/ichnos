"""Map each query's flows to dependencies between tables, columns, reports and output columns (ADR 0010).

`_read` traces each query's flows over its own scopes, and this module applies what `_infer` combines across queries.
A declaration expands a `*` and maps an `INSERT` with no column list, and a settled reference names its upstream column.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from ichnos._read import Fact, Whole

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ichnos._infer import Declarations, Evidence, ReportEvidence
    from ichnos._read import ColumnRef, Flow, Subtype, TableKey, Trace

type End = (
    tuple[Literal["table"], TableKey]
    | tuple[Literal["column"], TableKey, str]
    | tuple[Literal["report"], int]
    | tuple[Literal["output"], int, str]
)
"""A dependency's end: a table, a column, a report by its query's index, or an output column."""


@dataclass(frozen=True, slots=True)
class AmbiguousDependency:
    """An unqualified upstream column in one query that several tables can hold (ADR 0010)."""

    index: int
    downstream: End
    name: str
    candidates: tuple[TableKey, ...]


@dataclass(slots=True)
class Lineage:
    """Every dependency, with the queries behind each subtype, and every dependency ambiguity."""

    dependencies: dict[tuple[End, End], dict[Subtype, set[int]]]
    ambiguous: list[AmbiguousDependency]


def lineage(traces: Sequence[Trace], evidence: Evidence) -> Lineage:
    """Combine the flows of every query into dependencies."""
    mapper = _Mapper(evidence.declarations, {r.index: r for r in evidence.reports})
    dependencies: defaultdict[tuple[End, End], defaultdict[Subtype, set[int]]] = (
        defaultdict(lambda: defaultdict(set))
    )
    ambiguous: dict[AmbiguousDependency, None] = {}
    for index, trace in enumerate(traces):
        for flow in trace.flows:
            for upstream, downstream in mapper.ends(index, trace, flow):
                if isinstance(upstream, _Unsettled):
                    found = AmbiguousDependency(
                        index, downstream, upstream.name, upstream.candidates
                    )
                    ambiguous[found] = None
                else:
                    dependencies[upstream, downstream][flow.subtype].add(index)
    return Lineage({k: dict(v) for k, v in dependencies.items()}, list(ambiguous))


@dataclass(frozen=True, slots=True)
class _Unsettled:
    """An upstream column that the declarations leave with several candidate tables."""

    name: str
    candidates: tuple[TableKey, ...]


class _Mapper:
    """Map a flow's ends through the declarations and the reports' output columns."""

    def __init__(
        self, declarations: Declarations, reports: dict[int, ReportEvidence]
    ) -> None:
        self.declarations = declarations
        self.reports = reports

    def ends(
        self, index: int, trace: Trace, flow: Flow
    ) -> list[tuple[End | _Unsettled, End]]:
        """Return each pair of ends that a flow gives."""
        names, fallback = self._downstream(index, trace, flow)
        upstream = flow.upstream
        if isinstance(upstream, Whole) and upstream.star:
            columns = self.declarations.columns(upstream.table)
            if columns is not None and names is not None and len(names) == len(columns):
                # A `*` that a declaration expands copies each declared column (ADR 0008).
                return [
                    (("column", upstream.table, c), n)
                    for c, n in zip(columns, names, strict=True)
                ]
            return [(("table", upstream.table), fallback)]
        # `_read` records no flow from the whole rows that a `COUNT(*)` reads.
        assert not isinstance(upstream, Whole)  # noqa: S101
        return [(self._upstream(upstream), fallback)]

    def _upstream(self, upstream: ColumnRef) -> End | _Unsettled:
        candidates = self.declarations.settle(upstream)
        if len(candidates) > 1:
            # An ambiguous upstream column gives evidence to no candidate (ADR 0001).
            return _Unsettled(upstream.name, candidates)
        return ("column", candidates[0], upstream.name)

    def _downstream(
        self, index: int, trace: Trace, flow: Flow
    ) -> tuple[tuple[End, ...] | None, End]:
        """Return the ends of a flow's item, one per column it writes, and the one end the flow takes otherwise."""
        # Every direct flow names a column, or an output column or a value by its position.
        if flow.table is None:
            names = self.reports[index].items[flow.position or 0]
            outputs: tuple[End, ...] = tuple(("output", index, n) for n in names)
            return outputs, outputs[0] if len(outputs) == 1 else ("report", index)
        table = flow.table
        if flow.column is not None:
            return None, ("column", table, flow.column)
        names = self._item(trace, table, flow.position or 0)
        if names is None:
            # A value that maps to no column depends on the written table (ADR 0010).
            return None, ("table", table)
        ends: tuple[End, ...] = tuple(("column", table, n) for n in names)
        return ends, ends[0] if len(ends) == 1 else ("table", table)

    def _item(
        self, trace: Trace, table: TableKey, position: int
    ) -> tuple[str, ...] | None:
        """Return the columns that one select-list item writes, or None when no declaration maps it."""
        creation = trace.creation
        if creation is not None and creation.table == table:
            # A column list that names fewer positions than a `*` gives makes Oracle raise.
            item = creation.columns[min(position, len(creation.columns) - 1)]
            return (item,) if isinstance(item, str) else self.declarations.columns(item)
        write = next(w for w in trace.writes if w.table == table)
        if not self.declarations.mapped(table, write.values):
            return None
        columns = self.declarations.columns(table) or ()
        groups: list[tuple[str, ...]] = []
        for value in write.values or ():
            size = (
                1
                if isinstance(value, Fact)
                else len(self.declarations.columns(value) or ())
            )
            start = sum(map(len, groups))
            groups.append(columns[start : start + size])
        return groups[position]
