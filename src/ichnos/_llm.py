"""Write the summary that an LLM chat reads to choose what to slice (ADR 0012).

The graph module holds the records, and this module writes plain text under a character budget.
The summary is plain text, not DBML, because DBML raises on a table with no columns.
"""

from typing import TYPE_CHECKING

from ichnos._dbml import BUDGET, report_name, table_name
from ichnos._graph import Graph, Report, Table, count, fold

if TYPE_CHECKING:
    from collections.abc import Iterable


def summary(
    graph: Graph,
    owner: str | None = None,
    keyword: str | None = None,
    budget: int = BUDGET,
) -> str:
    """Write one line per table and report, so a reader can choose what to slice.

    A table's line holds its kind, its column count, `complete`, its `read` and `write` counts and the tables it joins.
    A report's line holds its output column count and the tables it reads.
    Over the budget, the summary cuts the lines with the lowest `read` plus `write` first, and its first line says how many it cut.

    Parameters
    ----------
    graph
        The graph that `infer` or `read` builds.
    owner
        Keep only the tables of this owner, and the reports that read one. The default keeps every table.
        It compares as Oracle folds a name, so `sales` keeps the owner `SALES`.
    keyword
        Keep only the tables whose name, column names or observed values contain it, ignoring case,
        and the reports whose name or output column names contain it. The default keeps every line.
    budget
        The most characters the text holds. The default is 8,000.

    Returns
    -------
    :
        The text, which ends with one newline.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer(
        {
            "q": "SELECT o.order_id, c.customer_name FROM sales.orders o "
            "JOIN sales.customers c ON c.customer_id = o.customer_id WHERE o.status = 'PAID'"
        }
    )
    print(ichnos.summary(graph, keyword="paid"))
    ```
    """
    folded = None if owner is None else fold(owner)
    lines: list[tuple[str, int]] = []
    for table in graph.tables:
        if folded is not None and table.owner != folded:
            continue
        found = _table_matches(table, keyword)
        if found is not None:
            lines.append(
                (
                    _table_line(graph, table, found),
                    count(table.read) + count(table.write),
                )
            )
    for report in graph.reports:
        tables = [t for t in graph.tables if report.query in t.read]
        if folded is not None and all(t.owner != folded for t in tables):
            continue
        found = _report_matches(report, keyword)
        if found is not None:
            lines.append((_report_line(report, tables, found), 1))
    return _fit(graph, owner, keyword, lines, budget)


def _fit(
    graph: Graph,
    owner: str | None,
    keyword: str | None,
    lines: list[tuple[str, int]],
    budget: int,
) -> str:
    """Cut the lines with the lowest `read` plus `write` first, then the last name, until the text fits."""
    order = sorted(
        range(len(lines)), key=lambda i: (lines[i][1], [-ord(c) for c in lines[i][0]])
    )
    cut: set[int] = set()
    while True:
        kept = [line for i, (line, _) in enumerate(lines) if i not in cut]
        threshold = max((lines[i][1] for i in cut), default=None)
        text = (
            "\n".join([_first_line(graph, owner, keyword, len(cut), threshold), *kept])
            + "\n"
        )
        if len(text) <= budget or len(cut) == len(lines):
            return text
        cut.add(order[len(cut)])


def _first_line(
    graph: Graph,
    owner: str | None,
    keyword: str | None,
    cut: int,
    threshold: int | None,
) -> str:
    parts = [
        f"Summary of {len(graph.queries)} queries, inferred with no database connection"
    ]
    if owner is not None:
        parts.append(f"owner {owner}")
    if keyword is not None:
        parts.append(f"keyword {keyword!r}")
    line = ", ".join(parts)
    if threshold is not None:
        line += f"; cut {cut} lines with read plus write of {threshold} or less"
    return line + "."


def _table_matches(table: Table, keyword: str | None) -> list[str] | None:
    """Return what in a table matches the keyword, or None when nothing does."""
    if keyword is None:
        return []
    word = keyword.casefold()
    found: list[str] = []
    for column in table.columns:
        values = [v for v in column.observed if word in v.casefold()]
        if values:
            found.append(f"{column.name} ({', '.join(values)})")
        elif word in column.name.casefold():
            found.append(column.name)
    if word in table.name.casefold() or word in (table.owner or "").casefold():
        return ["name", *found]
    return found or None


def _report_matches(report: Report, keyword: str | None) -> list[str] | None:
    if keyword is None:
        return []
    word = keyword.casefold()
    found = [c.name for c in report.output_columns if word in c.name.casefold()]
    if word in report.name.casefold():
        return ["name", *found]
    return found or None


def _table_line(graph: Graph, table: Table, matches: list[str]) -> str:
    kind = "" if table.kind is None else f"{table.kind}, "
    complete = ", complete" if table.complete else ""
    counts = [
        f"{key} {n}"
        for key, n in (("read", count(table.read)), ("write", count(table.write)))
        if n
    ]
    head = f"{table_name(table)}: {kind}{_columns(len(table.columns))}{complete}"
    line = ", ".join([head, *counts])
    joins = sorted(
        {
            table_name(other[0].table)
            for r in graph.relationships
            for side, other in (r.sides, r.sides[::-1])
            if side[0].table is table and other[0].table is not table
        }
    )
    if joins:
        line += f"; joins {', '.join(joins)}"
    return line + _matches(matches)


def _report_line(report: Report, tables: Iterable[Table], matches: list[str]) -> str:
    line = f"{report_name(report)}: report, {_columns(len(report.output_columns))}"
    names = sorted(table_name(t) for t in tables)
    if names:
        line += f"; from {', '.join(names)}"
    return line + _matches(matches)


def _columns(number: int) -> str:
    return f"{number} column" if number == 1 else f"{number} columns"


def _matches(matches: list[str]) -> str:
    return f"; matches {', '.join(matches)}" if matches else ""
