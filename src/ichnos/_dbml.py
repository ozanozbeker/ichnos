"""Write a graph as one DBML file, with every evidence count as a custom property (ADR 0011).

The graph module holds the records, and this module turns them into text that `@dbml/core` parses with no diagnostic.
"""

import re
from collections import defaultdict
from typing import TYPE_CHECKING

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
    Table,
    count,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

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
_TYPES: tuple[Type, ...] = ("text", "number", "datetime", "interval")
# Only a quoted lowercase Oracle owner can take this name, and `dbml` raises on one.
_REPORTS = "report"
# The output lists at most this many observed values, and only their number above it (ADR 0003).
_OBSERVED = 20
_BARE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def dbml(graph: Graph) -> str:
    r"""Write the full DBML file of a graph.

    Parameters
    ----------
    graph
        The graph that `infer` or `read` builds.

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

    graph = ichnos.infer({"q": "SELECT o.order_id FROM sales.orders o"})
    print(ichnos.dbml(graph))
    ```
    """
    clash = next((t for t in graph.tables if t.owner == _REPORTS), None)
    if clash is not None:
        message = f'the owner "{_REPORTS}" of {clash.name} is the schema that DBML writes reports in'
        raise IchnosError(message)
    blocks = [_project(graph), *(_table(t) for t in graph.tables)]
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


def _report(report: Report) -> str:
    """Write a report as a table in the schema `report`, because a `Dep` endpoint must be a table (ADR 0009)."""
    lines = [
        f"  {_name(c.name)} {_name('|'.join(t for t in _TYPES if t in c.types) or 'unknown')}"
        f"{_settings([('ambiguity', '; '.join(_ambiguity(a) for a in c.ambiguities))])}"
        for c in report.output_columns
    ] or ['  "*" unknown']
    ambiguity = "; ".join(_ambiguity(a) for a in report.ambiguities)
    head = f"Table {report_name(report)}{_settings([('kind', 'report'), ('ambiguity', ambiguity)])}"
    return f"{head} {{\n" + "\n".join(lines) + "\n}"


def _ref(relationship: Relationship) -> str:
    """Write a relationship as a `Ref` whose name holds its evidence (ADR 0011)."""
    first, second = relationship.sides
    if relationship.direction is not None:
        operator = ">?"
    elif _keyed(first) and _keyed(second):
        # Two keys give one-to-one, and `?<>?` between two unique columns raises a diagnostic.
        operator = "?-?"
    else:
        operator = "?<>?"
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


def _project(graph: Graph) -> str:
    note = [
        f"Inferred by ichnos from {len(graph.queries)} queries, with no database connection.",
        "Counts are distinct queries. A column with no type evidence has the type `unknown`.",
        "A column with evidence for two types writes both, such as `text|number`, an ambiguity.",
        "`null` claims a column can hold NULL. ichnos never claims NOT NULL.",
        "`>?` means the left side refers to a key on the right. `?<>?` means the direction is unknown.",
        "`?-?` joins two keys. Each key is a unique index, because ichnos never claims a primary key.",
        "The schema `report` holds the reports, which are queries, not tables.",
    ]
    lines = "\n".join(f"  {line}" for line in note)
    return (
        f"Project ichnos {{\n  database_type: 'Oracle'\n  Note: '''\n{lines}\n  '''\n}}"
    )


def _table(table: Table) -> str:
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
    lines = [_column(c) for c in table.columns] or ['  "*" unknown']
    if table.keys:
        # ichnos never writes `pk`, because it never claims a primary key (ADR 0006).
        indexes = (f"    {_key_label(k, quote=True)} [unique]" for k in table.keys)
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


def _column(column: Column) -> str:
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
    settings += [(p, count(column.references.get(p, ()))) for p in _POSITIONS]
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
