"""Hold the public records and build one immutable `Graph` from a corpus.

`_read` traces each query and `_infer` combines the traces, and this module turns their evidence into linked records (ADR 0013).
Every record compares and hashes by name only, because `Table.columns` and `Column.table` form a cycle.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

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
class UnparsedQuery:
    """A query that ichnos could not read whole, so no evidence comes from it.

    That is a query that sqlglot cannot parse or reads as an opaque command, one that is not a `SELECT`, DML or a creating query, and one that a later step fails on (ADR 0004).

    Attributes
    ----------
    name
        The file key, plus `#N` when the file holds several queries.
    file
        The key of the file that holds the query.
    position
        The query's position in its file, counted from 1.
    text
        The query's text.
    error
        Why ichnos could not read the query. Its first line is a one-line summary.

    Examples
    --------
    ```python
    import ichnos

    ichnos.infer({"q": "ALTER TABLE t ADD x NUMBER"}).unparsed
    ```
    """

    name: str
    file: str = field(compare=False)
    position: int = field(compare=False)
    text: str = field(compare=False, repr=False)
    error: str = field(compare=False)


type AmbiguityKind = Literal["column", "owner"]


@dataclass(frozen=True, slots=True)
class Ambiguity:
    """A point where the corpus admits more than one reading, which ichnos records without picking one (ADR 0001).

    Attributes
    ----------
    kind
        What the readings differ on. `"column"` is an unqualified column that several tables can hold,
        and `"owner"` is a table with no owner that shares its name with tables that have one.
    query
        The query that holds the ambiguity.
    subject
        The name that the readings differ on, such as the column `ORDER_ID` or the table `CUSTOMERS`.
    candidates
        Each candidate's name, such as `SALES.ORDERS.ORDER_ID`, with the queries behind it.
        Those queries give the candidate its own evidence count, and the ambiguity's query is never among them.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer(
        {"q": "SELECT order_id FROM sales.orders o, sales.customers c"}
    )
    graph.ambiguities
    ```
    """

    kind: AmbiguityKind
    query: Query
    subject: str
    candidates: Mapping[str, tuple[Query, ...]] = field(compare=False)


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
    ambiguities
        Each ambiguity with the column among its candidates.

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
    ambiguities: tuple[Ambiguity, ...] = field(compare=False, repr=False)


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
    ambiguities
        Each ambiguity with the table among its candidates, and each owner ambiguity of a table with no owner.

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
    ambiguities: tuple[Ambiguity, ...] = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Graph:
    """The inferred schema of one corpus.

    Attributes
    ----------
    tables
        Every table that a query reads or writes, by owner and then by name.
    queries
        Every query that ichnos read, by file key and then by position.
    unparsed
        Every query that ichnos could not read whole, by file key and then by position.
    ambiguities
        Every ambiguity, by query and then by subject.

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
    unparsed: tuple[UnparsedQuery, ...]
    ambiguities: tuple[Ambiguity, ...]


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
    read: list[Query] = []
    traces: list[_read.Trace] = []
    unparsed: list[UnparsedQuery] = []
    for query in queries:
        try:
            traces.append(_read.trace(query.text))
        except _read.ReadError as error:
            unparsed.append(
                UnparsedQuery(
                    query.name, query.file, query.position, query.text, str(error)
                )
            )
        else:
            read.append(query)
    return _Builder(read, _infer.combine(traces)).graph(unparsed)


def _name(owner: str | None, *names: str) -> str:
    return ".".join(n for n in (owner, *names) if n is not None)


class _Builder:
    """Turn combined evidence into linked records, whose cycles need each record built before the next."""

    def __init__(self, queries: list[Query], evidence: _infer.Evidence) -> None:
        self.queries = queries
        self.evidence = evidence
        self.ambiguities: dict[object, list[Ambiguity]] = defaultdict(list)

    def records(self, indices: Iterable[int]) -> tuple[Query, ...]:
        return tuple(self.queries[i] for i in sorted(indices))

    def graph(self, unparsed: list[UnparsedQuery]) -> Graph:
        ambiguities = [*self._column_ambiguities(), *self._owner_ambiguities()]
        order = {query: index for index, query in enumerate(self.queries)}
        for found in self.ambiguities.values():
            found.sort(key=lambda a: (order[a.query], a.subject))
        ambiguities.sort(key=lambda a: (order[a.query], a.subject))
        keys = sorted(self.evidence.tables, key=lambda k: (k[0] or "", k[1]))
        tables = tuple(self._table(key) for key in keys)
        return Graph(tables, tuple(self.queries), tuple(unparsed), tuple(ambiguities))

    def _column_ambiguities(self) -> list[Ambiguity]:
        ambiguities: list[Ambiguity] = []
        for found in self.evidence.ambiguous:
            candidates: dict[str, tuple[Query, ...]] = {}
            for key in found.candidates:
                column = self.evidence.tables[key].columns.get(found.name)
                indices = set().union(*column.references.values()) if column else set()
                candidates[_name(*key, found.name)] = self.records(
                    indices - {found.index}
                )
            ambiguity = Ambiguity(
                "column", self.queries[found.index], found.name, candidates
            )
            ambiguities.append(ambiguity)
            for key in found.candidates:
                self.ambiguities[key].append(ambiguity)
                self.ambiguities[(key, found.name)].append(ambiguity)
        return ambiguities

    def _owner_ambiguities(self) -> list[Ambiguity]:
        ambiguities: list[Ambiguity] = []
        for owner, name in self.evidence.tables:
            if owner is not None:
                continue
            namesakes = sorted(
                k for k in self.evidence.tables if k[0] is not None and k[1] == name
            )
            table = self.evidence.tables[(owner, name)]
            for index in sorted(table.read | table.write) if namesakes else ():
                candidates = {
                    _name(*k): self.records(
                        (self.evidence.tables[k].read | self.evidence.tables[k].write)
                        - {index}
                    )
                    for k in namesakes
                }
                ambiguity = Ambiguity("owner", self.queries[index], name, candidates)
                ambiguities.append(ambiguity)
                self.ambiguities[(owner, name)].append(ambiguity)
        return ambiguities

    def _table(self, key: _read.TableKey) -> Table:
        evidence = self.evidence.tables[key]
        table = Table(
            key[0],
            key[1],
            (),
            self.records(evidence.read),
            self.records(evidence.write),
            tuple(self.ambiguities[key]),
        )
        columns = tuple(
            Column(
                table,
                name,
                {
                    position: self.records(found)
                    for position, found in evidence.columns[name].references.items()
                },
                tuple(self.ambiguities[(key, name)]),
            )
            for name in sorted(evidence.columns)
        )
        # The records are frozen, and a column needs its table before the table can hold it.
        object.__setattr__(table, "columns", columns)
        return table
