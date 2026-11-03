"""Write a graph as one DBML file, with every evidence count as a custom property (ADR 0011).

The graph module holds the records, and this module turns them into text that `@dbml/core` parses with no diagnostic.
"""

import re
from collections import defaultdict
from dataclasses import replace
from typing import TYPE_CHECKING, Literal, overload

from ichnos._graph import (
    Ambiguity,
    Column,
    Dependency,
    Graph,
    IchnosError,
    Key,
    OutputColumn,
    Relationship,
    Report,
    Rollup,
    Slice,
    Table,
    count,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from ichnos._graph import Query
    from ichnos._read import Position, Type

_POSITIONS: tuple[Position, ...] = (
    "select",
    "where",
    "join",
    "group_by",
    "order_by",
    "aggregate",
    "insert",
    "set",
)
# The escape table from issue 20, for every quoted name and string.
_ESCAPES = str.maketrans(
    {"\\": "\\\\", '"': '\\"', "'": "\\'", "\n": "\\n", "\r": "\\r", "\t": "\\t"}
)
type Detail = Literal["compact", "full"]

BUDGET = 8000
"""The default budget in characters: the only prompt size that Microsoft documents for Copilot Chat."""

_TYPES: tuple[Type, ...] = ("text", "number", "datetime", "interval")
_DIRECT = frozenset({"IDENTITY", "TRANSFORMATION", "AGGREGATION"})
# Only a quoted lowercase Oracle owner can take this name, and `dbml` raises on one.
_REPORTS = "report"
# The output lists at most this many observed values, and only their number above it (ADR 0003).
_OBSERVED = 20
_BARE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


@overload
def dbml(source: Graph) -> str: ...
@overload
def dbml(
    source: Slice,
    budget: int = BUDGET,
    detail: Detail = "compact",
    examples: bool = False,  # noqa: FBT001, FBT002 # the API's keyword, as ADR 0013 names it
) -> str: ...
def dbml(
    source: Graph | Slice,
    budget: int = BUDGET,
    detail: Detail = "compact",
    examples: bool = False,  # noqa: FBT001, FBT002 # the API's keyword, as ADR 0013 names it
) -> str:
    r"""Write the full DBML file of a graph, or a slice under a character budget.

    The full file holds the inferred schema, the reports and the lineage (ADR 0011).
    A slice holds a header that says what was asked and what the budget cut,
    and it cuts in ADR 0012's order until it fits, but never below its core.

    Parameters
    ----------
    source
        A graph that `infer` or `read` builds, or a slice that one of its walks returns.
    budget
        A slice's most characters. A core over it is written whole, and its header states the core's size.
        The full file takes no budget. The default is 8,000.
    detail
        `"compact"`, the default, drops each column's position counts and type counts, but keeps the type counts of two types.
        `"full"` writes every count, as the full file does.
    examples
        Whether a slice ends with example queries as `//` comments, which count against the budget.

    Returns
    -------
    :
        The DBML text, which ends with one `\n`.

    Raises
    ------
    IchnosError
        When a table's owner is `report`, the schema that DBML writes reports in.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer(
        {
            "q": "SELECT o.order_id FROM sales.orders o JOIN sales.customers c ON c.customer_id = o.customer_id"
        }
    )
    print(ichnos.dbml(graph.neighborhood([graph.table("sales.orders")]), budget=2000))
    ```
    """
    if isinstance(source, Slice):
        return _Slicer(source, budget, detail, examples=examples).write()
    graph = source
    clash = next((t for t in graph.tables if t.owner == _REPORTS), None)
    if clash is not None:
        message = f'the owner "{_REPORTS}" of {clash.name} is the schema that DBML writes reports in'
        raise IchnosError(message)
    blocks = [_project(_note(graph)), *(_table(t) for t in graph.tables)]
    if graph.relationships:
        blocks.append("\n".join(_ref(r) for r in graph.relationships))
    blocks += [_report(r) for r in graph.reports]
    blocks += _self_dependencies(graph.dependencies)
    blocks += _deps(graph)
    return "\n\n".join(blocks) + "\n"


def _self_dependencies(dependencies: Iterable[Dependency]) -> list[str]:
    """Write each column that depends on itself as a property, because DBML raises on `t.a -> t.a` (ADR 0011)."""
    return [
        f"Metadata Column {_endpoint_of(d.upstream)} {{\n"
        f"  self_dependency: {_value(_subtype_list(d))}\n}}"
        for d in dependencies
        if d.upstream == d.downstream
    ]


def _subtype_list(dependency: Dependency) -> str:
    return ", ".join(f"{s} {count(q)}" for s, q in dependency.subtypes.items())


def _deps(graph: Graph) -> list[str]:
    """Write the `Dep` lines, grouped by downstream table or report, each group's rollups first (ADR 0011)."""
    groups: list[str] = []
    rollups: dict[Table | Report, list[Rollup]] = defaultdict(list)
    for rollup in graph.rollups:
        rollups[rollup.downstream].append(rollup)
    for downstream, found in rollups.items():
        lines: list[str] = []
        for rollup in found:
            # A dependency stored between two tables shares its rollup's edge (ADR 0011).
            stored = next(
                (
                    d
                    for d in rollup.dependencies
                    if d.downstream is downstream and d.upstream is rollup.upstream
                ),
                None,
            )
            counts = [("queries", count(rollup.queries))]
            counts += [
                (s.lower(), count(q))
                for s, q in (stored.subtypes.items() if stored else ())
            ]
            lines.append(
                f"Dep: {_endpoint_of(rollup.upstream)} -> {_endpoint_of(downstream)}{_settings(counts)}"
            )
        for dependency in graph.dependencies:
            stored = (
                isinstance(dependency.upstream, Table)
                and dependency.downstream is downstream
            )
            if (
                _holder(dependency.downstream) is not downstream
                or stored
                or dependency.upstream == dependency.downstream
            ):
                continue
            counts = [(s.lower(), count(q)) for s, q in dependency.subtypes.items()]
            lines.append(
                f"Dep: {_endpoint_of(dependency.upstream)} -> {_endpoint_of(dependency.downstream)}{_settings(counts)}"
            )
        groups.append("\n".join(lines))
    return groups


def _holder(end: Table | Column | Report | OutputColumn) -> Table | Report:
    match end:
        case Column():
            return end.table
        case OutputColumn():
            return end.report
        case _:
            return end


def _endpoint_of(end: Table | Column | Report | OutputColumn) -> str:
    """Write a dependency end as DBML names it: a table, a column, or a report in the schema `report`."""
    match end:
        case Table():
            return table_name(end)
        case Column():
            return f"{table_name(end.table)}.{_name(end.name)}"
        case Report():
            return report_name(end)
        case OutputColumn():
            return f"{_REPORTS}.{_name(end.report.name)}.{_name(end.name)}"


def _report(report: Report, columns: Sequence[OutputColumn] | None = None) -> str:
    """Write a report as a table in the schema `report`, because a `Dep` endpoint must be a table (ADR 0009)."""
    kept = report.output_columns if columns is None else columns
    lines = [
        f"  {_name(c.name)} {_name('|'.join(t for t in _TYPES if t in c.types) or 'unknown')}"
        f"{_settings([('ambiguity', '; '.join(_ambiguity(a) for a in c.ambiguities))])}"
        for c in kept
    ] or ['  "*" unknown']
    ambiguity = "; ".join(_ambiguity(a) for a in report.ambiguities)
    head = f"Table {report_name(report)}{_settings([('kind', 'report'), ('ambiguity', ambiguity)])}"
    return f"{head} {{\n" + "\n".join(lines) + "\n}"


def _ref(relationship: Relationship) -> str:
    """Write a relationship as a `Ref` whose name holds its evidence (ADR 0011)."""
    first, second = relationship.sides
    operator = _operator(relationship)
    name = f"join {count(relationship.join)}"
    if relationship.shared is not None:
        key = relationship.shared
        name += f", shared reference to {table_name(key.columns[0].table)}.{_key_label(key)}"
    return (
        f"Ref {_name_quoted(name)}: {_endpoint(first)} {operator} {_endpoint(second)}"
    )


def _keyed(columns: tuple[Column, ...]) -> bool:
    names = {c.name for c in columns}
    return any({c.name for c in k.columns} == names for k in columns[0].table.keys)


def _endpoint(columns: tuple[Column, ...]) -> str:
    table = table_name(columns[0].table)
    names = [_name(c.name) for c in columns]
    return f"{table}.{names[0]}" if len(names) == 1 else f"{table}.({', '.join(names)})"


def _note(graph: Graph) -> list[str]:
    """Return the full file's note, which explains every mark it can hold (ADR 0011)."""
    return [
        f"Inferred by ichnos from {len(graph.queries)} queries, with no database connection.",
        "Counts are distinct queries. A column with no type evidence has the type `unknown`.",
        "A column with evidence for two types writes both, such as `text|number`, an ambiguity.",
        "`null` claims a column can hold NULL. ichnos never claims NOT NULL.",
        "`>?` means the left side refers to a key on the right. `?<>?` means the direction is unknown.",
        "`?-?` joins two keys. Each key is a unique index, because ichnos never claims a primary key.",
        "The schema `report` holds the reports, which are queries, not tables.",
    ]


def _project(note: list[str]) -> str:
    lines = "\n".join(f"  {line}" for line in note)
    return (
        f"Project ichnos {{\n  database_type: 'Oracle'\n  Note: '''\n{lines}\n  '''\n}}"
    )


def _table(
    table: Table, columns: Sequence[Column] | None = None, detail: Detail = "full"
) -> str:
    kinds = dict.fromkeys(d.kind for d in table.declarations)
    contradictions = (
        f"{c.query.name}: {c.reason}{'' if c.column is None else f' {c.column}'}"
        for c in table.contradictions
    )
    settings = _settings(
        [
            ("kind", "|".join(kinds)),
            ("complete", table.complete),
            ("declared", count(table.declared)),
            ("read", count(table.read)),
            ("write", count(table.write)),
            (
                "keys",
                "; ".join(f"{_key_label(k)}: {_key_basis(k)}" for k in table.keys),
            ),
            ("contradicted", "; ".join(contradictions)),
            ("ambiguity", "; ".join(_ambiguity(a) for a in table.ambiguities)),
        ]
    )
    kept = table.columns if columns is None else columns
    lines = [_column(c, detail) for c in kept] or ['  "*" unknown']
    # A slice writes only the keys whose columns it keeps, because DBML raises on a missing column.
    keys = [k for k in table.keys if set(k.columns) <= set(kept)]
    if keys:
        # ichnos never writes `pk`, because it never claims a primary key (ADR 0006).
        indexes = (f"    {_key_label(k, quote=True)} [unique]" for k in keys)
        lines += ["", "  indexes {", *indexes, "  }"]
    return f"Table {table_name(table)}{settings} {{\n" + "\n".join(lines) + "\n}"


def _key_label(key: Key, *, quote: bool = False) -> str:
    """Write a key's columns as one name, or as a parenthesized list for a composite key."""
    names = [_name(c.name) if quote else c.name for c in key.columns]
    return names[0] if len(names) == 1 else f"({', '.join(names)})"


def _key_basis(key: Key) -> str:
    """Write what supports a key: its name match and the count of each query shape."""
    basis = [] if key.name_match is None else [f"name match {key.name_match}"]
    basis += [f"{shape} {count(queries)}" for shape, queries in key.evidence.items()]
    return ", ".join(basis)


def _column(column: Column, detail: Detail = "full") -> str:
    types = [t for t in _TYPES if t in column.types]
    declared = {
        d.types[column.name]
        for d in column.table.declarations
        if column.name in d.types
    }
    # A declared column takes its declared type outright, and two types are an ambiguity (ADR 0007).
    type_ = declared.pop() if len(declared) == 1 else "|".join(types) or "unknown"
    observed = list(column.observed)
    settings: list[tuple[str, int | str | bool]] = [
        ("declared", count(column.declared))
    ]
    if detail == "full":
        settings += [(p, count(column.references.get(p, ()))) for p in _POSITIONS]
    # Compact detail keeps the type counts of two types, because they are the evidence for that ambiguity (ADR 0012).
    if detail == "full" or "|" in type_:
        settings += [(t, count(column.types.get(t, ()))) for t in _TYPES]
    settings += [
        ("nullable", count(column.nullable)),
        (
            "observed",
            ", ".join(map(_plain, observed)) if len(observed) <= _OBSERVED else "",
        ),
        ("observed_count", len(observed) if len(observed) > _OBSERVED else 0),
        ("undeclared", column.undeclared),
        (
            "ambiguity",
            "; ".join(
                _ambiguity(a) for a in column.ambiguities if a.kind == "dependency"
            ),
        ),
    ]
    null = ["null"] if column.nullable else []
    return f"  {_name(column.name)} {_name(type_)}{_settings(settings, null)}"


def _plain(literal: str) -> str:
    """Write an observed value without its quotes, unless a comma or an outer space needs them (ADR 0011)."""
    if not literal.startswith("'"):
        return literal
    value = literal[1:-1].replace("''", "'")
    return literal if "," in value or value != value.strip(" ") else value


def _ambiguity(ambiguity: Ambiguity) -> str:
    """Write one ambiguity with each candidate's evidence count, naming its query as a report's name does."""
    candidates = " or ".join(
        f"{name} ({count(q)})" for name, q in ambiguity.candidates.items()
    )
    verb = "may be" if ambiguity.kind == "owner" else "is"
    upstream = "upstream " if ambiguity.kind == "dependency" else ""
    reading = f"{upstream}{ambiguity.subject} {verb} {candidates}"
    return reading if ambiguity.query is None else f"{ambiguity.query.name}: {reading}"


def _settings(
    settings: Sequence[tuple[str, int | str | bool]], keywords: Sequence[str] = ()
) -> str:
    """Write the keyword settings, then each custom property that holds a count above 0, a string that is not empty, or `true`."""
    written = [
        *keywords,
        *(f"{key}: {_value(value)}" for key, value in settings if value),
    ]
    return f" [{', '.join(written)}]" if written else ""


def _value(value: int | str | bool) -> str:  # noqa: FBT001 # a property value, not a flag
    if isinstance(value, bool):
        return "true"
    if isinstance(value, str):
        return f"'{value.translate(_ESCAPES)}'"
    return str(value)


def report_name(report: Report) -> str:
    """Write a report's name in the schema `report`, as every DBML text and the summary name it."""
    return f"{_REPORTS}.{_name(report.name)}"


def table_name(table: Table) -> str:
    """Write a table's name, with its owner, as every DBML text and the summary name it."""
    return (
        _name(table.name)
        if table.owner is None
        else f"{_name(table.owner)}.{_name(table.name)}"
    )


def _name_quoted(name: str) -> str:
    return f'"{name.translate(_ESCAPES)}"'


def _name(name: str) -> str:
    """Quote a name only when DBML needs it."""
    return name if _BARE.fullmatch(name) else f'"{name.translate(_ESCAPES)}"'


# --- slices (ADR 0012) -----------------------------------------------------------------------

_LEGEND = {
    "unknown": "A column with no type evidence has the type `unknown`.",
    "|": "A column with evidence for two types writes both, such as `text|number`, an ambiguity.",
    "null": "`null` claims a column can hold NULL. ichnos never claims NOT NULL.",
    ">?": "`>?` means the left side refers to a key on the right.",
    "?<>?": "`?<>?` means the direction is unknown.",
    "?-?": "`?-?` joins two keys.",
    "complete": "`complete: true` means the declarations list every column.",
    "undeclared": "`undeclared: true` marks a column that the declarations lack.",
    "partial": "A table with no `kind` may list only some of its columns.",
    "report": "The schema `report` holds the reports, which are queries, not tables.",
}


class _Slicer:
    """Write a slice under its budget, cutting in ADR 0012's order down to its core."""

    def __init__(
        self, found: Slice, budget: int, detail: Detail, *, examples: bool
    ) -> None:
        self.slice = found
        self.budget = budget
        self.detail = detail
        self.kept: dict[Table | Report, tuple[Column | OutputColumn, ...]] = dict(
            found.columns
        )
        self.dependencies = list(found.dependencies)
        self.lineage = found.kind in {"upstream", "downstream"}
        if not examples:
            self.examples: list[Query] = []
        elif self.lineage:
            self.examples = self._hop_queries()
        else:
            self.examples = _examples(found.relationships)
        self.cut: list[str] = []

    def write(self) -> str:
        """Cut one step at a time until the text fits, or write the core whole with its size."""
        text = self.render()
        for cut in self._cuts():
            if len(text) <= self.budget:
                return text
            cut()
            text = self.render()
        if len(text) <= self.budget:
            return text
        # The core exceeds the budget, so the header states its size, which the line itself changes.
        size = len(text)
        while len(text := self.render(size)) != size:
            size = len(text)
        return text

    def render(self, core: int | None = None) -> str:
        holders = sorted(self.kept, key=self._place)
        marks: set[str] = set()
        blocks: list[str] = []
        for table in (h for h in holders if isinstance(h, Table)):
            columns = [c for c in self.kept[table] if isinstance(c, Column)]
            blocks.append(_table(table, columns, self.detail))
            marks |= _marks(table, columns)
        refs = [
            r
            for r in self.slice.relationships
            if all(s[0].table in self.kept for s in r.sides)
        ]
        if refs:
            blocks.append("\n".join(_ref(r) for r in refs))
            marks |= {_operator(r) for r in refs}
        for report in (h for h in holders if isinstance(h, Report)):
            outputs = [c for c in self.kept[report] if isinstance(c, OutputColumn)]
            blocks.append(_report(report, outputs))
            marks.add("report")
        # A lineage slice writes the self-dependency of each chain column (ADR 0012).
        blocks += _self_dependencies(self.dependencies)
        lines = [_rollup(r) for r in self.slice.rollups]
        lines += [_dep(d) for d in self.dependencies if d.upstream != d.downstream]
        if lines:
            blocks.append("\n".join(lines))
        for query in self.examples:
            text = query.text.split("\n")
            blocks.append(
                "\n".join([f"// {query.name}", *(f"// {line}" for line in text)])
            )
        return "\n\n".join([self._header(marks, core), *blocks]) + "\n"

    def _place(self, holder: Table | Report) -> tuple[int, int, str, str]:
        """Order tables and reports by distance from the start, then by name, tables first."""
        distance = self.slice.distances[holder]
        if isinstance(holder, Report):
            return (distance, 1, "", holder.name)
        return (distance, 0, *_order(holder))

    def _header(self, marks: set[str], core: int | None) -> str:
        found = self.slice
        names = ", ".join(_end_name(s) for s in found.starts)
        total = len(found.graph.tables)
        tables = len([t for t in found.distances if isinstance(t, Table)])
        match found.kind:
            case "neighborhood":
                asked = f"Neighborhood of {names} at depth {found.depth}"
            case "join path":
                asked = f"Join path between {names}"
            case _:
                hops = (
                    "with every indirect dependency"
                    if found.indirect == "all"
                    else "with indirect dependencies on the first hop"
                )
                asked = f"{found.kind.capitalize()} of {names}, {hops}"
        lines = [
            f"{asked}: {tables} of {total} tables.",
            f"Inferred from {len(found.graph.queries)} queries, with no database connection.",
        ]
        lines += [line for mark, line in _LEGEND.items() if mark in marks]
        if self.cut:
            lines.append(
                f"Cut to fit {self.budget:,} characters: {', '.join(self.cut)}."
            )
        if core is not None:
            lines.append(
                f"The core is {core:,} characters, over the {self.budget:,}-character budget."
            )
        outside = [
            f"{label} {', '.join(_end_name(e) for e in ends)}."
            for key, label in (
                ("joins", "Outside the slice, these tables join it:"),
                ("upstream", "Upstream of the centers:"),
                ("downstream", "Downstream of the centers:"),
            )
            if (ends := found.outside.get(key))
        ]
        if found.unconnected:
            unconnected = ", ".join(_end_name(t) for t in found.unconnected)
            outside.append(f"No relationship connects {unconnected}.")
        return _project([*lines, *outside])

    def _cuts(self) -> list[Callable[[], None]]:
        """Return each cut in ADR 0012's order, which `write` applies one at a time."""
        cuts: list[Callable[[], None]] = [
            self._drop_example(q) for q in reversed(self.examples)
        ]
        if self.lineage:
            if any(d.indirect for d in self._first_hop()):
                cuts.append(self._drop_first_hop)
            return cuts
        found = self.slice
        movable = sorted(
            (t for t in self.kept if isinstance(t, Table) and t not in found.starts),
            key=lambda t: (
                -found.distances[t],
                count((*t.read, *t.write)),
                [-ord(c) for c in table_name(t)],
            ),
        )
        on_refs = {c for r in found.relationships for side in r.sides for c in side}
        for table in movable:
            trimmed = tuple(
                c
                for c in table.columns
                if c in on_refs or any(c in k.columns for k in table.keys)
            )
            if trimmed != self.kept[table]:
                cuts.append(self._trim(table, trimmed))
        if found.kind == "neighborhood":
            cuts += [self._drop(t) for t in movable]
        return cuts

    def _first_hop(self) -> list[Dependency]:
        """Return the dependencies whose near end is the start, its columns, or its table or report."""
        found = self.slice
        start = found.starts[0]
        starts: set[object] = {start, _holder(start)}
        if isinstance(start, Table | Report):
            starts |= set(found.columns.get(start, ()))
        if found.kind == "upstream":
            return [d for d in self.dependencies if d.downstream in starts]
        return [d for d in self.dependencies if d.upstream in starts]

    def _drop_first_hop(self) -> None:
        """Drop the first hop's indirect dependencies, and every column that only they reached."""
        first = set(self._first_hop())
        kept: list[Dependency] = []
        for dependency in self.dependencies:
            if dependency not in first or not dependency.indirect:
                kept.append(dependency)
                continue
            direct = {s: q for s, q in dependency.subtypes.items() if s in _DIRECT}
            if direct:
                kept.append(replace(dependency, subtypes=direct))
        self.dependencies = kept
        ends = {e for d in kept for e in (d.upstream, d.downstream)}
        ends |= set(self.slice.starts)
        self.kept = {
            h: tuple(c for c in cs if c in ends or isinstance(h, Report))
            for h, cs in self.kept.items()
            if any(e is h or _holder(e) is h for e in ends)
        }
        self.cut.append("the first hop's indirect dependencies")

    def _hop_queries(self) -> list[Query]:
        """Return the queries that write each hop, nearest hop first (ADR 0012)."""
        upstream = self.slice.kind == "upstream"

        def hop(dependency: Dependency) -> int:
            near = dependency.downstream if upstream else dependency.upstream
            return self.slice.distances.get(_holder(near), 0)

        ordered = sorted(self.dependencies, key=hop)
        return list(
            dict.fromkeys(q for d in ordered for qs in d.subtypes.values() for q in qs)
        )

    def _drop_example(self, query: Query) -> Callable[[], None]:
        def cut() -> None:
            self.examples.remove(query)
            self.cut.append(f"the example {query.name}")

        return cut

    def _trim(self, table: Table, columns: tuple[Column, ...]) -> Callable[[], None]:
        def cut() -> None:
            self.kept[table] = columns
            self.cut.append(f"trimmed {table_name(table)}")

        return cut

    def _drop(self, table: Table) -> Callable[[], None]:
        def cut() -> None:
            del self.kept[table]
            self.cut.append(f"dropped {table_name(table)}")

        return cut


def _rollup(rollup: Rollup) -> str:
    counts = [("queries", count(rollup.queries))]
    upstream, downstream = (
        _endpoint_of(rollup.upstream),
        _endpoint_of(rollup.downstream),
    )
    return f"Dep: {upstream} -> {downstream}{_settings(counts)}"


def _dep(dependency: Dependency) -> str:
    counts = [(s.lower(), count(q)) for s, q in dependency.subtypes.items()]
    upstream = _endpoint_of(dependency.upstream)
    downstream = _endpoint_of(dependency.downstream)
    return f"Dep: {upstream} -> {downstream}{_settings(counts)}"


def _examples(relationships: Sequence[Relationship]) -> list[Query]:
    """Pick, one at a time, the query that covers the most `Ref` lines no picked query covers (ADR 0012)."""
    uncovered = set(relationships)
    picked: list[Query] = []
    while uncovered:
        candidates = {q for r in uncovered for q in r.join}
        best = min(
            candidates,
            key=lambda q: (-sum(q in r.join for r in uncovered), len(q.text), q.name),
        )
        picked.append(best)
        uncovered = {r for r in uncovered if best not in r.join}
    return picked


def _marks(table: Table, columns: Sequence[Column]) -> set[str]:
    """Return the legend marks that one table's text holds."""
    marks = set() if table.kind is not None else {"partial"}
    marks |= {"complete"} if table.complete else set()
    for column in columns:
        types = [t for t in _TYPES if t in column.types]
        declared = {
            d.types[column.name] for d in table.declarations if column.name in d.types
        }
        if not declared and not types:
            marks.add("unknown")
        if len(declared) != 1 and len(types) > 1:
            marks.add("|")
        marks |= {"null"} if column.nullable else set()
        marks |= {"undeclared"} if column.undeclared else set()
    return marks


def _operator(relationship: Relationship) -> str:
    """Return a `Ref` operator. Two keys give one-to-one, because `?<>?` between two unique columns raises a diagnostic."""
    first, second = relationship.sides
    if relationship.direction is not None:
        return ">?"
    return "?-?" if _keyed(first) and _keyed(second) else "?<>?"


def _end_name(end: Table | Column | Report | OutputColumn) -> str:
    """Write a slice's start or outside end as the DBML text names it."""
    return _endpoint_of(end)


def _order(table: Table) -> tuple[str, str]:
    return (table.owner or "", table.name)
