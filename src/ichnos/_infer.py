"""Combine the traces of every query into evidence for each table and column.

`_read` traces one query at a time, and this module counts evidence across queries (ADR 0001).
Evidence holds query indices, and the graph module turns each index into its `Query` record.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ichnos._read import Position, TableKey, Trace


@dataclass(slots=True)
class ColumnEvidence:
    """The queries behind one column, by reference position."""

    references: defaultdict[Position, set[int]] = field(
        default_factory=lambda: defaultdict(set)
    )


@dataclass(slots=True)
class TableEvidence:
    """The queries that read and write one table, and the evidence for each of its columns."""

    read: set[int] = field(default_factory=set)
    write: set[int] = field(default_factory=set)
    columns: defaultdict[str, ColumnEvidence] = field(
        default_factory=lambda: defaultdict(ColumnEvidence)
    )


def combine(traces: Sequence[Trace | None]) -> dict[TableKey, TableEvidence]:
    """Count each table's and column's evidence across the traces, where `None` marks an unparsed query."""
    tables: defaultdict[TableKey, TableEvidence] = defaultdict(TableEvidence)
    for index, trace in enumerate(traces):
        if trace is None:
            continue
        for key in trace.reads:
            tables[key].read.add(index)
        if trace.target is not None and trace.statement != "create":
            tables[trace.target].write.add(index)
        for ref in trace.refs:
            candidates = ref.candidates[0]
            # An unqualified column with several candidate tables gives no evidence (ADR 0001).
            if len(candidates) == 1:
                tables[candidates[0]].columns[ref.name].references[ref.position].add(
                    index
                )
    return dict(tables)
