"""Hold the public records and build one immutable `Graph` from a corpus.

`_read` traces each query and `_infer` combines the traces, and this module turns their evidence into linked records (ADR 0013).
Every record compares and hashes by name only, because `Table.columns` and `Column.table` form a cycle.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ichnos import _infer, _read

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ichnos._read import Position


class IchnosError(Exception):
    """A user error, such as two queries with one name or a file that does not decode.

    The CLI writes its message as one `ichnos: <message>` line and exits with code 1.

    Examples
    --------
    ```python
    import ichnos

    try:
        ichnos.infer(
            {"a#1": "SELECT 1 FROM t", "a": "SELECT 1 FROM t; SELECT 2 FROM t"}
        )
    except ichnos.IchnosError as error:
        print(error)
    ```
    """


@dataclass(frozen=True, slots=True)
class Query:
    """One query of the corpus.

    Attributes
    ----------
    name
        The file key, plus `#N` when the file holds several queries.
    file
        The key of the file that holds the query.
    position
        The query's position in its file, counted from 1.
    text
        The query's text, without the `;` or `/` that ends it.

    Examples
    --------
    ```python
    import ichnos

    ichnos.infer({"daily": "SELECT 1 FROM t; SELECT 2 FROM t"}).queries
    ```
    """

    name: str
    file: str = field(compare=False)
    position: int = field(compare=False)
    text: str = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Column:
    """A column of a table that some query references.

    Attributes
    ----------
    table
        The table that holds the column.
    name
        The column's name in dictionary form: uppercase unless a query quotes it.
    references
        The queries that reference the column, by position.
        A position's evidence count is the number of distinct texts among its queries.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer(
        {"q": "SELECT o.status FROM sales.orders o WHERE o.status = 'A'"}
    )
    graph.tables[0].columns[0].references
    ```
    """

    table: Table = field(repr=False)
    name: str
    references: Mapping[Position, tuple[Query, ...]] = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Table:
    """A table, view, materialized view or synonym that a query reads or writes.

    Attributes
    ----------
    owner
        The owner, or `None` when no query names one.
    name
        The table's name in dictionary form, with any `@link`.
    columns
        The columns that the queries reference, by name.
    read
        The queries that read the table.
    write
        The queries that write the table with DML.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer({"q": "UPDATE sales.orders o SET o.status = 'X'"})
    graph.tables[0]
    ```
    """

    owner: str | None
    name: str
    columns: tuple[Column, ...] = field(compare=False, repr=False)
    read: tuple[Query, ...] = field(compare=False, repr=False)
    write: tuple[Query, ...] = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Graph:
    """The inferred schema of one corpus.

    Attributes
    ----------
    tables
        Every table that a query reads or writes, by owner and then by name.
    queries
        Every query, by file key and then by position.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer({"q": "SELECT o.order_id FROM sales.orders o"})
    graph.tables
    ```
    """

    tables: tuple[Table, ...]
    queries: tuple[Query, ...]


def count(queries: Iterable[Query]) -> int:
    """Return an evidence count: the number of distinct texts among the queries (ADR 0001)."""
    return len({q.text for q in queries})


def infer(files: Mapping[str, str]) -> Graph:
    """Build the graph of a corpus from each file's text under a key that names the file.

    Parameters
    ----------
    files
        Each file's text, under a key such as `sub/038_daily_reports`.
        A query's name is its key, plus `#N` when the file holds several queries.

    Returns
    -------
    :
        The graph of every table and column that the queries reference.

    Raises
    ------
    IchnosError
        When two queries get the same name, such as a one-query key `a#1` beside a two-query key `a`.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer({"q": "SELECT o.order_id FROM sales.orders o"})
    graph.tables[0].columns
    ```
    """
    queries: list[Query] = []
    names: dict[str, Query] = {}
    for key in sorted(files):
        texts = _read.split(files[key])
        for position, text in enumerate(texts, 1):
            query = Query(
                f"{key}#{position}" if len(texts) > 1 else key, key, position, text
            )
            if query.name in names:
                message = f"two queries are named {query.name}, in {names[query.name].file} and {key}"
                raise IchnosError(message)
            names[query.name] = query
            queries.append(query)
    traces: list[_read.Trace | None] = []
    for query in queries:
        try:
            traces.append(_read.trace(query.text))
        except _read.ReadError:
            traces.append(None)
    evidence = _infer.combine(traces)
    tables = [
        _table(key, evidence[key], queries)
        for key in sorted(evidence, key=lambda k: (k[0] or "", k[1]))
    ]
    return Graph(tuple(tables), tuple(queries))


def _table(
    key: _read.TableKey, evidence: _infer.TableEvidence, queries: list[Query]
) -> Table:
    def records(indices: set[int]) -> tuple[Query, ...]:
        return tuple(queries[i] for i in sorted(indices))

    table = Table(key[0], key[1], (), records(evidence.read), records(evidence.write))
    columns = tuple(
        Column(
            table,
            name,
            {
                position: records(found)
                for position, found in evidence.columns[name].references.items()
            },
        )
        for name in sorted(evidence.columns)
    )
    # The records are frozen, and a column needs its table before the table can hold it.
    object.__setattr__(table, "columns", columns)
    return table
