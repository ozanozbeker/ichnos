"""Write a graph as one DBML file, with every evidence count as a custom property (ADR 0011).

The graph module holds the records, and this module turns them into text that `@dbml/core` parses with no diagnostic.
"""

import re
from typing import TYPE_CHECKING

from ichnos._graph import Ambiguity, Column, Graph, Table, count

if TYPE_CHECKING:
    from collections.abc import Sequence

    from ichnos._read import Position

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

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer({"q": "SELECT o.order_id FROM sales.orders o"})
    print(ichnos.dbml(graph))
    ```
    """
    blocks = [_project(graph), *(_table(t) for t in graph.tables)]
    return "\n\n".join(blocks) + "\n"


def _project(graph: Graph) -> str:
    note = [
        f"Inferred by ichnos from {len(graph.queries)} queries, with no database connection.",
        "Counts are distinct queries. A column with no type evidence has the type `unknown`.",
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
            ("contradicted", "; ".join(contradictions)),
            ("ambiguity", "; ".join(_ambiguity(a) for a in table.ambiguities)),
        ]
    )
    columns = [_column(c) for c in table.columns] or ['  "*" unknown']
    return f"Table {_table_name(table)}{settings} {{\n" + "\n".join(columns) + "\n}"


def _column(column: Column) -> str:
    settings: list[tuple[str, int | str | bool]] = [
        ("declared", count(column.declared))
    ]
    settings += [(p, count(column.references.get(p, ()))) for p in _POSITIONS]
    settings += [("undeclared", column.undeclared)]
    return f"  {_name(column.name)} unknown{_settings(settings)}"


def _ambiguity(ambiguity: Ambiguity) -> str:
    """Write one ambiguity with each candidate's evidence count, naming its query as a report's name does."""
    candidates = " or ".join(
        f"{name} ({count(q)})" for name, q in ambiguity.candidates.items()
    )
    verb = "may be" if ambiguity.kind == "owner" else "is"
    reading = f"{ambiguity.subject} {verb} {candidates}"
    return reading if ambiguity.query is None else f"{ambiguity.query.name}: {reading}"


def _settings(settings: Sequence[tuple[str, int | str | bool]]) -> str:
    """Write each custom property that holds a count above 0, a string that is not empty, or `true`."""
    written = [f"{key}: {_value(value)}" for key, value in settings if value]
    return f" [{', '.join(written)}]" if written else ""


def _value(value: int | str | bool) -> str:  # noqa: FBT001 # a property value, not a flag
    if isinstance(value, bool):
        return "true"
    if isinstance(value, str):
        return f"'{value.translate(_ESCAPES)}'"
    return str(value)


def _table_name(table: Table) -> str:
    return (
        _name(table.name)
        if table.owner is None
        else f"{_name(table.owner)}.{_name(table.name)}"
    )


def _name(name: str) -> str:
    """Quote a name only when DBML needs it."""
    return name if _BARE.fullmatch(name) else f'"{name.translate(_ESCAPES)}"'
