"""Hold the public records and build one immutable `Graph` from a corpus.

`_read` traces each query and `_infer` combines the traces, and this module turns their evidence into linked records (ADR 0013).
Every record compares and hashes by name only, because `Table.columns` and `Column.table` form a cycle.
"""

from collections import defaultdict
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Literal

from ichnos import _infer, _lineage, _read

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from ichnos._infer import ContradictionReason
    from ichnos._read import KeyShape, Position, Subtype, TableKind, Type


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


type AmbiguityKind = Literal["column", "owner", "declaration", "type", "dependency"]


@dataclass(frozen=True, slots=True)
class Ambiguity:
    """A point where the corpus admits more than one reading, which ichnos records without picking one (ADR 0001).

    Attributes
    ----------
    kind
        What the readings differ on. `"column"` is an unqualified column that several tables can hold,
        `"owner"` is a table with no owner that shares its name with tables that have one,
        `"declaration"` is a table that creating queries declare in more than one way,
        `"type"` is a column with evidence for two types,
        and `"dependency"` is an unqualified upstream column that several tables can hold.
    query
        The query that holds the ambiguity, or `None` for a `"declaration"` or `"type"` ambiguity, which spans queries.
    subject
        The name that the readings differ on, such as the column `ORDER_ID` or the table `CUSTOMERS`.
        A `"dependency"` ambiguity names its upstream column, and its downstream end lists it.
    candidates
        Each candidate's name, such as `SALES.ORDERS.ORDER_ID`, with the queries behind it.
        Those queries give the candidate its own evidence count, and the ambiguity's query is never among them.
        A `"declaration"` candidate names a kind and a column list, such as `view (ID, NAME)`, and a `"type"` candidate names a type.

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
    query: Query | None
    subject: str
    candidates: Mapping[str, tuple[Query, ...]] = field(compare=False)


@dataclass(frozen=True, slots=True)
class Declaration:
    """One distinct way that creating queries declare a table: its kind and its column list (ADR 0008).

    Attributes
    ----------
    kind
        The kind that the creating queries state.
    columns
        The declared column names, in declared order, with each `*` over a declared table expanded.
    types
        The type of each declared column whose expression has a fixed type (ADR 0007).
    queries
        The creating queries that state this declaration. Two that match give one declaration.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer({"q": "CREATE VIEW m.v AS SELECT t.a, t.b AS c FROM t"})
    graph.tables[0].declarations
    ```
    """

    kind: TableKind
    columns: tuple[str, ...]
    types: Mapping[str, Type] = field(compare=False)
    queries: tuple[Query, ...] = field(compare=False)


@dataclass(frozen=True, slots=True)
class Contradiction:
    """A query that shows a declaration no longer describes its table (ADR 0008).

    Attributes
    ----------
    query
        The query that contradicts the declaration.
    reason
        `"undeclared column"` when the query references a column that the declaration lacks,
        `"declaration"` when another creating query declares the table differently,
        and `"value count"` when an `INSERT` with no column list writes a different number of values.
    column
        The undeclared column, or `None` for the other reasons.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer(
        {
            "a": "CREATE TABLE m.t AS SELECT s.x FROM s",
            "b": "SELECT t.y FROM m.t t",
        }
    )
    graph.tables[0].contradictions
    ```
    """

    query: Query
    reason: ContradictionReason
    column: str | None


type NameMatch = Literal["ID", "<S>_ID", "<S>_CODE"]


@dataclass(frozen=True, slots=True)
class Key:
    """An inferred claim that a set of columns identifies at most one row of its table (ADR 0006).

    ichnos never claims a primary key. A table can have several keys, such as a surrogate key and a business key.

    Attributes
    ----------
    columns
        The key's columns.
    name_match
        The pattern that the one column's name follows, such as `<S>_ID`, or `None`.
        A name match supports a key on its own, and has no evidence count.
    evidence
        The queries behind each query shape that shows the key: `"generated"`, `"merge"`, `"single_row"` or `"grouped"`.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer({"q": "SELECT w.id, w.warehouse_code FROM inv.warehouses w"})
    graph.tables[0].keys
    ```
    """

    columns: tuple[Column, ...]
    name_match: NameMatch | None = field(compare=False)
    evidence: Mapping[KeyShape, tuple[Query, ...]] = field(compare=False, repr=False)


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
    declared
        The creating queries that declare the column.
    types
        The queries behind each type that the column shows (ADR 0007).
    nullable
        The queries that show the column can hold `NULL`. ichnos never claims `NOT NULL`.
    observed
        The queries behind each observed value, as its SQL literal text, such as `'PAID'` or `10000`.
        A corpus never shows a column's full set of values (ADR 0003).
    undeclared
        Whether the table has a declaration that lacks the column.
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
    declared: tuple[Query, ...] = field(compare=False, repr=False)
    types: Mapping[Type, tuple[Query, ...]] = field(compare=False, repr=False)
    nullable: tuple[Query, ...] = field(compare=False, repr=False)
    observed: Mapping[str, tuple[Query, ...]] = field(compare=False, repr=False)
    undeclared: bool = field(compare=False, repr=False)
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
        The columns that the queries reference or declare.
        A declared table lists its declared columns in declared order, then its undeclared columns by name.
        Every other table lists its columns by name.
    read
        The queries that read the table.
    write
        The queries that write the table with DML.
    declared
        The creating queries that declare the table.
    declarations
        Each distinct declaration, in corpus order.
    kind
        The table kind that the declarations state,
        or `None` with no declaration or when the declarations differ in kind.
    complete
        Whether the declarations list every column, which holds while no query contradicts them
        and every `*` in them expanded.
    contradictions
        The queries that contradict the declarations. With any, every declaration is contradicted.
    keys
        The table's keys, from name matches and from key evidence, with the shorter keys first.
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
    declared: tuple[Query, ...] = field(compare=False, repr=False)
    declarations: tuple[Declaration, ...] = field(compare=False, repr=False)
    kind: TableKind | None = field(compare=False, repr=False)
    complete: bool = field(compare=False, repr=False)
    contradictions: tuple[Contradiction, ...] = field(compare=False, repr=False)
    keys: tuple[Key, ...] = field(compare=False, repr=False)
    ambiguities: tuple[Ambiguity, ...] = field(compare=False, repr=False)

    def column(self, name: str) -> Column:
        """Return the column with a name, which compares in dictionary form as Oracle folds it.

        Parameters
        ----------
        name
            An unquoted name, which matches without regard to case, or a quoted one, which keeps its case.

        Returns
        -------
        :
            The column.

        Raises
        ------
        KeyError
            When the table holds no such column.

        Examples
        --------
        ```python
        import ichnos

        graph = ichnos.infer({"q": "SELECT o.status FROM sales.orders o"})
        graph.tables[0].column("status")
        ```
        """
        folded = _fold(name)
        for column in self.columns:
            if column.name == folded:
                return column
        raise KeyError(name)


@dataclass(frozen=True, slots=True)
class Relationship:
    """An inferred claim that columns of one table match columns of another table, or of the same table (ADR 0002).

    Attributes
    ----------
    sides
        The two sides' columns, aligned position by position.
        With a direction, the first side refers to the second. Without one, the sides go in name order.
    direction
        The key that the first side refers to, or `None` when no side, or both, equal a key of their table.
    shared
        The key of a third table that both sides refer to, for a shared reference, or `None`.
    join
        The queries whose bare `=` join conditions give the relationship evidence.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer(
        {
            "q": "SELECT o.order_id FROM sales.orders o JOIN sales.customers c ON c.customer_id = o.customer_id"
        }
    )
    graph.relationships
    ```
    """

    sides: tuple[tuple[Column, ...], tuple[Column, ...]]
    direction: Key | None = field(compare=False)
    shared: Key | None = field(compare=False)
    join: tuple[Query, ...] = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class OutputColumn:
    """One position in a report's select list, under the name Oracle gives it (ADR 0009).

    An output column is never a column, because a report is never a table.

    Attributes
    ----------
    report
        The report that holds the output column.
    name
        The alias, the column's name, or the expression's source text with whitespace and comments dropped and uppercased.
        A repeated name takes a space and `(2)`, `(3)` and so on.
    position
        The position in the select list, counted from 1, after each `*` expands.
    types
        The type of an expression with a fixed type, with the report's query behind it.
    ambiguities
        Each dependency ambiguity whose downstream end is the output column.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer(
        {"r": "SELECT o.id, COUNT( * ) FROM sales.orders o GROUP BY o.id"}
    )
    graph.reports[0].output_columns
    ```
    """

    report: Report = field(repr=False)
    name: str
    position: int = field(compare=False)
    types: Mapping[Type, tuple[Query, ...]] = field(compare=False, repr=False)
    ambiguities: tuple[Ambiguity, ...] = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Report:
    """A query that reads tables and writes none, named after its file (ADR 0009).

    A report is never a table, because no other query can read it, and it takes no owner.

    Attributes
    ----------
    name
        The query's name: its file key, plus `#N` when the file holds several queries.
    query
        The query.
    output_columns
        The output columns, in position order.
    ambiguities
        Each dependency ambiguity whose downstream end is the report itself.

    Examples
    --------
    ```python
    import ichnos

    ichnos.infer({"daily": "SELECT COUNT(*) AS n FROM sales.orders"}).reports
    ```
    """

    name: str
    query: Query = field(compare=False, repr=False)
    output_columns: tuple[OutputColumn, ...] = field(compare=False, repr=False)
    ambiguities: tuple[Ambiguity, ...] = field(compare=False, repr=False)

    def output_column(self, name: str) -> OutputColumn:
        """Return the output column with a name, which compares in dictionary form as Oracle folds it.

        Parameters
        ----------
        name
            An unquoted name, which matches without regard to case, or a quoted one, which keeps its case.

        Returns
        -------
        :
            The output column.

        Raises
        ------
        KeyError
            When the report has no such output column.

        Examples
        --------
        ```python
        import ichnos

        graph = ichnos.infer({"r": "SELECT o.status AS state FROM sales.orders o"})
        graph.reports[0].output_column("state")
        ```
        """
        folded = _fold(name)
        for column in self.output_columns:
            if column.name == folded:
                return column
        raise KeyError(name)


type End = Table | Column | Report | OutputColumn


@dataclass(frozen=True, slots=True)
class Dependency:
    """An inferred claim that a downstream end is derived from an upstream end, or that the upstream end selects its rows (ADR 0010).

    Attributes
    ----------
    upstream
        A table or a column.
    downstream
        A table, a column, a report or an output column.
    subtypes
        The queries behind each OpenLineage transformation subtype, each an evidence kind.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer({"q": "SELECT o.status AS state FROM sales.orders o"})
    graph.dependencies
    ```
    """

    upstream: Table | Column
    downstream: End
    subtypes: Mapping[Subtype, tuple[Query, ...]] = field(compare=False, repr=False)

    @property
    def direct(self) -> bool:
        """Whether the dependency holds a direct subtype: `IDENTITY`, `TRANSFORMATION` or `AGGREGATION`."""
        return any(s in _DIRECT for s in self.subtypes)

    @property
    def indirect(self) -> bool:
        """Whether the dependency holds an indirect subtype, such as `JOIN` or `FILTER`."""
        return any(s not in _DIRECT for s in self.subtypes)


@dataclass(frozen=True, slots=True)
class Rollup:
    """A dependency between two tables, or a table and a report, that holds wherever another dependency joins them.

    Attributes
    ----------
    upstream
        The table that the dependencies read.
    downstream
        The table or report that they feed.
    queries
        The queries that hold one of the dependencies. Its evidence count is the number of distinct texts among them.
    dependencies
        The dependencies that the rollup joins.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer(
        {"q": "CREATE TABLE m.t AS SELECT o.status FROM sales.orders o"}
    )
    graph.rollups
    ```
    """

    upstream: Table
    downstream: Table | Report
    queries: tuple[Query, ...] = field(compare=False, repr=False)
    dependencies: tuple[Dependency, ...] = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Graph:
    """The inferred schema of one corpus.

    Attributes
    ----------
    tables
        Every table that a query reads or writes, by owner and then by name.
    relationships
        Every relationship, by the first side's table and columns.
    reports
        Every report, by file key and then by position.
    dependencies
        Every dependency, grouped by its downstream end, with tables before reports.
    rollups
        Every rollup, by its downstream end and then its upstream table.
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
    relationships: tuple[Relationship, ...]
    reports: tuple[Report, ...]
    dependencies: tuple[Dependency, ...]
    rollups: tuple[Rollup, ...]
    queries: tuple[Query, ...]
    unparsed: tuple[UnparsedQuery, ...]
    ambiguities: tuple[Ambiguity, ...]

    def table(self, name: str) -> Table:
        """Return the table with a name, which parses as Oracle parses it.

        An unquoted part becomes uppercase, a quoted part keeps its case, and `@link` stays part of the name.
        So `X` and `MART.X` are different tables.

        Parameters
        ----------
        name
            The table's name, with its owner when it has one, such as `sales.orders`.

        Returns
        -------
        :
            The table.

        Raises
        ------
        KeyError
            When the graph holds no such table.

        Examples
        --------
        ```python
        import ichnos

        graph = ichnos.infer({"q": "SELECT o.status FROM sales.orders o"})
        graph.table("sales.orders")
        ```
        """
        parts = _parts(name)
        if len(parts) > 2:  # noqa: PLR2004 # an owner and a name
            raise KeyError(name)
        owner, table = (None, parts[0]) if len(parts) == 1 else parts
        for found in self.tables:
            if (found.owner, found.name) == (owner, table):
                return found
        raise KeyError(name)

    def report(self, name: str) -> Report:
        """Return the report with a name, which keeps its file's case.

        Parameters
        ----------
        name
            The report's name: its file key, plus `#N` when the file holds several queries.

        Returns
        -------
        :
            The report.

        Raises
        ------
        KeyError
            When the graph holds no such report.

        Examples
        --------
        ```python
        import ichnos

        graph = ichnos.infer({"daily": "SELECT COUNT(*) AS n FROM sales.orders"})
        graph.report("daily")
        ```
        """
        for report in self.reports:
            if report.name == name:
                return report
        raise KeyError(name)

    def neighborhood(self, tables: Iterable[Table], depth: int = 1) -> Slice:
        """Return the tables within some relationships of one or more centers (ADR 0012).

        The walk follows relationships only, never dependencies, and every table in it keeps all its columns.

        Parameters
        ----------
        tables
            The center tables.
        depth
            The most relationships between a center and a table in the slice. The default is 1.

        Returns
        -------
        :
            The slice, which `dbml` writes.

        Examples
        --------
        ```python
        import ichnos

        graph = ichnos.infer(
            {
                "q": "SELECT 1 FROM sales.orders o JOIN sales.customers c ON c.customer_id = o.customer_id"
            }
        )
        graph.neighborhood([graph.table("sales.orders")]).distances
        ```
        """
        centers = tuple(dict.fromkeys(tables))
        neighbors = _neighbors(self.relationships)
        found: dict[Table, int] = dict.fromkeys(centers, 0)
        frontier = list(centers)
        for distance in range(1, depth + 1):
            frontier = [n for t in frontier for n, _ in neighbors[t] if n not in found]
            found.update(dict.fromkeys(frontier, distance))
        joined = {n for t in found for n, _ in neighbors[t]} - set(found)
        upstream = (r.upstream for r in self.rollups if r.downstream in centers)
        downstream = (r.downstream for r in self.rollups if r.upstream in centers)
        outside = {
            "joins": _ends(joined),
            "upstream": _ends(u for u in upstream if u not in found),
            "downstream": _ends(d for d in downstream if d not in found),
        }
        distances: dict[Table | Report, int] = dict(found.items())
        return Slice(
            "neighborhood",
            centers,
            depth,
            None,
            distances,
            {t: t.columns for t in found},
            tuple(
                r
                for r in self.relationships
                if {s[0].table for s in r.sides} <= set(found)
            ),
            (),
            (),
            outside,
            (),
            self,
        )

    def join_path(self, tables: Iterable[Table]) -> Slice:
        """Return the union of every shortest join path between each pair of tables (ADR 0012).

        A path's length is its number of relationships, whatever their direction or evidence.

        Parameters
        ----------
        tables
            Two or more tables.

        Returns
        -------
        :
            The slice, which `dbml` writes.

        Examples
        --------
        ```python
        import ichnos

        graph = ichnos.infer(
            {
                "a": "SELECT 1 FROM s.a a JOIN s.b b ON b.id = a.b_id",
                "b": "SELECT 1 FROM s.b b JOIN s.c c ON c.id = b.c_id",
            }
        )
        graph.join_path([graph.table("s.a"), graph.table("s.c")]).distances
        ```
        """
        starts = tuple(dict.fromkeys(tables))
        neighbors = _neighbors(self.relationships)
        found = {t: _distances(t, neighbors) for t in starts}
        nodes: set[Table] = set(starts)
        edges: set[Relationship] = set()
        unconnected: list[Table] = []
        for index, a in enumerate(starts):
            for b in starts[index + 1 :]:
                da, db = found[a], found[b]
                if b not in da:
                    unconnected += [t for t in (a, b) if t not in unconnected]
                    continue
                length = da[b]
                nodes |= {t for t in da if t in db and da[t] + db[t] == length}
                edges |= {
                    r
                    for t, others in neighbors.items()
                    for other, r in others
                    if t in da and other in db and da[t] + 1 + db[other] == length
                }
        distances: dict[Table | Report, int] = {
            t: min(d[t] for d in found.values() if t in d) for t in nodes
        }
        return Slice(
            "join path",
            starts,
            None,
            None,
            distances,
            {t: t.columns for t in nodes},
            tuple(r for r in self.relationships if r in edges),
            (),
            (),
            {},
            tuple(unconnected),
            self,
        )

    def upstream(
        self,
        start: Table | Column | Report | OutputColumn,
        indirect: Indirect = "first_hop",
    ) -> Slice:
        """Return where a start's values come from: the chain of dependencies to its upstream ends (ADR 0012).

        A report starts at all its output columns, and a table at all its columns.
        The walk continues only from a column it reaches through a direct dependency,
        and it visits each end once, so a cycle ends it.

        Parameters
        ----------
        start
            A table, a column, a report or an output column.
        indirect
            `"first_hop"`, the default, keeps the indirect dependencies of the queries that write the start only.
            `"all"` keeps every indirect dependency, and the walk also continues from a column it reaches through one.

        Returns
        -------
        :
            The slice, which `dbml` writes.

        Examples
        --------
        ```python
        import ichnos

        graph = ichnos.infer(
            {"r": "SELECT o.status AS state FROM sales.orders o WHERE o.total > 1"}
        )
        graph.upstream(graph.report("r")).dependencies
        ```
        """
        return _Walk(self, "upstream", start, indirect).slice()

    def downstream(
        self, start: Table | Column, indirect: Indirect = "first_hop"
    ) -> Slice:
        """Return what a start feeds, the other direction of `upstream` (ADR 0012).

        A downstream slice of a table writes only the rollups, over all hops, to every downstream table and report.

        Parameters
        ----------
        start
            A table or a column. A report is never an upstream end.
        indirect
            `"first_hop"`, the default, keeps the indirect dependencies of the queries that read the start only.
            `"all"` keeps every indirect dependency.

        Returns
        -------
        :
            The slice, which `dbml` writes.

        Examples
        --------
        ```python
        import ichnos

        graph = ichnos.infer(
            {"c": "CREATE TABLE m.t AS SELECT o.status FROM sales.orders o"}
        )
        graph.downstream(graph.table("sales.orders")).rollups
        ```
        """
        return _Walk(self, "downstream", start, indirect).slice()


type SliceKind = Literal["neighborhood", "join path", "upstream", "downstream"]
type Start = Table | Column | Report | OutputColumn
type Indirect = Literal["first_hop", "all"]


@dataclass(frozen=True, slots=True)
class Slice:
    """A part of the graph that one question selects, which `dbml` writes to paste into an LLM chat (ADR 0012).

    A slice holds what the writer needs and nothing the writer computes, so it never changes with the budget.

    Attributes
    ----------
    kind
        The walk that selected it.
    starts
        The walk's start: the centers of a neighborhood, the ends of a join path, or the start of a lineage walk.
    depth
        A neighborhood's depth, or `None`.
    indirect
        Which indirect dependencies a lineage walk keeps, or `None`.
    distances
        Each table's and report's distance from the nearest start.
    columns
        The columns and output columns that each table and report keeps.
    relationships
        The relationships between tables in the slice.
    dependencies
        The dependencies that a lineage slice writes.
    rollups
        The rollups that a downstream slice of a table writes.
    outside
        The tables and reports outside the slice that the header names, by why it names them.
    unconnected
        The tables of a join path that no relationship connects.
    graph
        The graph the slice comes from.

    Examples
    --------
    ```python
    import ichnos

    graph = ichnos.infer({"q": "SELECT o.status FROM sales.orders o"})
    graph.neighborhood([graph.table("sales.orders")])
    ```
    """

    kind: SliceKind
    starts: tuple[Table | Column | Report | OutputColumn, ...]
    depth: int | None = field(repr=False)
    indirect: Indirect | None = field(repr=False)
    distances: Mapping[Table | Report, int] = field(repr=False)
    columns: Mapping[Table | Report, tuple[Column | OutputColumn, ...]] = field(
        repr=False
    )
    relationships: tuple[Relationship, ...] = field(repr=False)
    dependencies: tuple[Dependency, ...] = field(repr=False)
    rollups: tuple[Rollup, ...] = field(repr=False)
    outside: Mapping[str, tuple[Table | Report, ...]] = field(repr=False)
    unconnected: tuple[Table, ...] = field(repr=False)
    graph: Graph = field(repr=False)


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
    evidence = _infer.combine(traces)
    return _Builder(read, evidence, _lineage.lineage(traces, evidence)).graph(unparsed)


_TYPES: tuple[Type, ...] = ("text", "number", "datetime", "interval")
_DIRECT: frozenset[Subtype] = frozenset({"IDENTITY", "TRANSFORMATION", "AGGREGATION"})
_SUBTYPES: tuple[Subtype, ...] = (
    "IDENTITY",
    "TRANSFORMATION",
    "AGGREGATION",
    "JOIN",
    "FILTER",
    "GROUP_BY",
    "SORT",
    "WINDOW",
    "CONDITIONAL",
)


class _Walk:
    """Follow the dependencies of a lineage slice, one hop at a time (ADR 0012)."""

    def __init__(
        self,
        graph: Graph,
        kind: Literal["upstream", "downstream"],
        start: Start,
        indirect: Indirect,
    ) -> None:
        self.graph = graph
        self.kind = kind
        self.start = start
        self.indirect = indirect
        self.ends: defaultdict[End, list[Dependency]] = defaultdict(list)
        for dependency in graph.dependencies:
            near = dependency.downstream if kind == "upstream" else dependency.upstream
            self.ends[near].append(dependency)

    def slice(self) -> Slice:
        if self.kind == "downstream" and isinstance(self.start, Table):
            return self._rollups(self.start)
        starts = _starts(self.start)
        self.distances: dict[Table | Report, int] = dict.fromkeys(
            map(_holder, starts), 0
        )
        self.kept: defaultdict[Table | Report, dict[Column | OutputColumn, None]] = (
            defaultdict(dict)
        )
        self.found: dict[Dependency, Dependency] = {}
        for end in starts:
            if isinstance(end, Column | OutputColumn):
                self.kept[_holder(end)][end] = None
        if self.kind == "upstream" and isinstance(self.start, Column | OutputColumn):
            self._first_rows(self.start)
        self._follow(starts)
        columns = {
            h: h.output_columns
            if isinstance(h, Report)
            else tuple(c for c in h.columns if c in self.kept[h])
            for h in self.distances
        }
        return Slice(
            self.kind,
            (self.start,),
            None,
            self.indirect,
            self.distances,
            columns,
            (),
            tuple(sorted(self.found.values(), key=_dependency_order)),
            (),
            {},
            (),
            self.graph,
        )

    def _follow(self, starts: list[End]) -> None:
        """Visit each end once, hop by hop, keeping the dependencies the slice writes."""
        visited = set(starts)
        frontier = starts
        hop = 0
        while frontier:
            following: list[End] = []
            for dependency in (d for end in frontier for d in self.ends[end]):
                kept = self._keep(dependency, first=hop == 0)
                if kept is None:
                    continue
                far = self._reach(dependency, kept, hop + 1)
                # The walk continues only from a column it reaches through a direct dependency.
                through = kept.direct or self.indirect == "all"
                if (
                    isinstance(far, Column | OutputColumn)
                    and through
                    and far not in visited
                ):
                    visited.add(far)
                    following.append(far)
                    # Every indirect dependency includes the rows that each query selects for that column's table.
                    holder = _holder(far)
                    if self.indirect == "all" and holder not in visited:
                        visited.add(holder)
                        following.append(holder)
            frontier = following
            hop += 1

    def _reach(self, dependency: Dependency, kept: Dependency, hop: int) -> End:
        """Record a dependency the slice writes, and return its far end."""
        self.found[dependency] = kept
        far = dependency.upstream if self.kind == "upstream" else dependency.downstream
        self.distances.setdefault(_holder(far), hop)
        if isinstance(far, Column | OutputColumn):
            self.kept[_holder(far)][far] = None
        return far

    def _first_rows(self, start: Column | OutputColumn) -> None:
        """Add the row filters of the queries that write a column, which state which rows it holds (ADR 0012)."""
        writing = {
            q for d in self.ends[start] for qs in d.subtypes.values() for q in qs
        }
        for dependency in self.ends[_holder(start)]:
            subtypes = {
                s: rows
                for s, q in dependency.subtypes.items()
                if (rows := tuple(x for x in q if x in writing))
            }
            if subtypes:
                self._reach(dependency, replace(dependency, subtypes=subtypes), 1)

    def _keep(self, dependency: Dependency, *, first: bool) -> Dependency | None:
        """Keep a dependency's subtypes: every one on the first hop, and past it only the direct ones."""
        if first or self.indirect == "all":
            return dependency
        subtypes = {s: q for s, q in dependency.subtypes.items() if s in _DIRECT}
        return replace(dependency, subtypes=subtypes) if subtypes else None

    def _rollups(self, start: Table) -> Slice:
        """Follow the rollups from a table to every downstream table and report, over all hops."""
        distances: dict[Table | Report, int] = {start: 0}
        found: list[Rollup] = []
        frontier: list[Table | Report] = [start]
        while frontier:
            following: list[Table | Report] = []
            for holder in frontier:
                for rollup in self.graph.rollups:
                    if rollup.upstream is holder and rollup not in found:
                        found.append(rollup)
                        if rollup.downstream not in distances:
                            distances[rollup.downstream] = distances[holder] + 1
                            following.append(rollup.downstream)
            frontier = following
        # Each block lists the columns and output columns that depend on the start table.
        depending: dict[Table | Report, dict[Column | OutputColumn, None]] = (
            defaultdict(dict)
        )
        pending: list[End] = [start, *start.columns]
        seen = set(pending)
        while pending:
            for dependency in self.ends[pending.pop()]:
                far = dependency.downstream
                if isinstance(far, Column | OutputColumn):
                    depending[_holder(far)][far] = None
                if far not in seen:
                    seen.add(far)
                    pending.append(far)
        columns = {h: tuple(depending[h]) for h in distances}
        return Slice(
            "downstream",
            (start,),
            None,
            self.indirect,
            distances,
            columns,
            (),
            (),
            tuple(
                sorted(
                    found,
                    key=lambda r: (_end_order(r.downstream), _end_order(r.upstream)),
                )
            ),
            {},
            (),
            self.graph,
        )


def _starts(start: Start) -> list[End]:
    """Return the ends a lineage walk starts at: a report's output columns and a table's columns, with the report or table."""
    match start:
        case Table():
            return [start, *start.columns]
        case Report():
            return [start, *start.output_columns]
        case _:
            return [start]


def _parts(name: str) -> list[str]:
    """Split a dotted name outside its quotes, and fold each part as Oracle does."""
    parts: list[str] = []
    current, quoted = "", False
    for char in name:
        if char == '"':
            quoted = not quoted
        if char == "." and not quoted:
            parts.append(current)
            current = ""
        else:
            current += char
    return [_fold(p) for p in [*parts, current]]


def _neighbors(
    relationships: Iterable[Relationship],
) -> defaultdict[Table, list[tuple[Table, Relationship]]]:
    """Return each table's neighbors over relationships, which a walk follows either way."""
    neighbors: defaultdict[Table, list[tuple[Table, Relationship]]] = defaultdict(list)
    for relationship in relationships:
        a, b = (side[0].table for side in relationship.sides)
        neighbors[a].append((b, relationship))
        neighbors[b].append((a, relationship))
    return neighbors


def _distances(
    start: Table, neighbors: Mapping[Table, list[tuple[Table, Relationship]]]
) -> dict[Table, int]:
    """Return each table's distance from a start over relationships, by breadth-first search."""
    distances = {start: 0}
    frontier = [start]
    level = 0
    while frontier:
        level += 1
        found = [
            n for t in frontier for n, _ in neighbors.get(t, ()) if n not in distances
        ]
        frontier = list(dict.fromkeys(found))
        distances.update(dict.fromkeys(frontier, level))
    return distances


def _ends(ends: Iterable[Table | Report]) -> tuple[Table | Report, ...]:
    """Sort tables by name before reports by name, without repeats."""

    def key(end: Table | Report) -> tuple[int, str, str]:
        return (1, "", end.name) if isinstance(end, Report) else (0, *_order(end))

    return tuple(sorted(set(ends), key=key))


def _fold(name: str) -> str:
    """Return a name in dictionary form: a quoted name keeps its case, and an unquoted one becomes uppercase."""
    if len(name) > 1 and name.startswith('"') and name.endswith('"'):
        return name[1:-1].replace('""', '"')
    return name.upper()


_SHAPES: tuple[KeyShape, ...] = ("generated", "merge", "single_row", "grouped")


def _order(table: Table) -> tuple[str, str]:
    return (table.owner or "", table.name)


def _holder(end: End) -> Table | Report:
    """Return the table or report that an end belongs to."""
    match end:
        case Column():
            return end.table
        case OutputColumn():
            return end.report
        case _:
            return end


def _end_order(end: End) -> tuple[int, str, str, int, str]:
    """Sort tables before reports, then by name, with a table or report before its columns."""
    holder = _holder(end)
    column = isinstance(end, Column | OutputColumn)
    if isinstance(holder, Table):
        return (
            0,
            holder.owner or "",
            holder.name,
            int(column),
            end.name if column else "",
        )
    return (1, "", holder.name, int(column), end.name if column else "")


def _dependency_order(dependency: Dependency) -> tuple[object, ...]:
    return (_end_order(dependency.downstream), _end_order(dependency.upstream))


def _rollups(dependencies: tuple[Dependency, ...]) -> tuple[Rollup, ...]:
    """Join two tables, or a table and a report, wherever a dependency joins them (ADR 0010)."""
    grouped: dict[tuple[Table, Table | Report], list[Dependency]] = defaultdict(list)
    for dependency in dependencies:
        upstream = _holder(dependency.upstream)
        assert isinstance(upstream, Table)  # noqa: S101 # an upstream end is a table or a column
        grouped[upstream, _holder(dependency.downstream)].append(dependency)
    rollups = [
        Rollup(
            upstream,
            downstream,
            tuple(
                sorted(
                    {q for d in found for qs in d.subtypes.values() for q in qs},
                    key=lambda q: q.name,
                )
            ),
            tuple(found),
        )
        for (upstream, downstream), found in grouped.items()
    ]
    return tuple(
        sorted(
            rollups, key=lambda r: (_end_order(r.downstream), _end_order(r.upstream))
        )
    )


def _key_of(columns: tuple[Column, ...]) -> Key | None:
    """Return the key of the columns' table whose columns equal them, or None."""
    names = {c.name for c in columns}
    table = columns[0].table
    return next((k for k in table.keys if {c.name for c in k.columns} == names), None)


def _bare_name(name: str) -> str:
    """Return a table's name without its database link, folded as Oracle folds an unquoted name."""
    return name.split("@", 1)[0].upper()


def _singulars(word: str) -> set[str]:
    """Return a word and every singular of it: without a final S, without a final ES, and with a final IES as Y."""
    found = {word}
    if word.endswith("S"):
        found.add(word[:-1])
    if word.endswith("ES"):
        found.add(word[:-2])
    if word.endswith("IES"):
        found.add(word[:-3] + "Y")
    return found


def _name_match(table: str, column: str, others: set[str]) -> NameMatch | None:
    """Return the key pattern that a column's name follows for its table, or None (ADR 0006)."""
    column = column.upper()
    if column == "ID":
        return "ID"
    stems = _singulars(table)
    if "_" in table:
        last = _singulars(table.rsplit("_", 1)[1])
        # `ROLE_ID` in `USER_ROLES` is a foreign key when a table `ROLES` exists.
        if not last & {s for o in others for s in _singulars(o)}:
            stems |= last
    for stem in stems:
        if column == f"{stem}_ID":
            return "<S>_ID"
        if column == f"{stem}_CODE":
            return "<S>_CODE"
    return None


def _name(owner: str | None, *names: str) -> str:
    return ".".join(n for n in (owner, *names) if n is not None)


class _Builder:
    """Turn combined evidence into linked records, whose cycles need each record built before the next."""

    def __init__(
        self, queries: list[Query], evidence: _infer.Evidence, lineage: _lineage.Lineage
    ) -> None:
        self.queries = queries
        self.evidence = evidence
        self.lineage = lineage
        self.ambiguities: dict[object, list[Ambiguity]] = defaultdict(list)

    def records(self, indices: Iterable[int]) -> tuple[Query, ...]:
        return tuple(self.queries[i] for i in sorted(indices))

    def graph(self, unparsed: list[UnparsedQuery]) -> Graph:
        ambiguities = [
            *self._column_ambiguities(),
            *self._owner_ambiguities(),
            *self._declaration_ambiguities(),
            *self._type_ambiguities(),
            *self._dependency_ambiguities(),
        ]
        # An ambiguity that spans queries sorts after every query's own.
        order = {query: index for index, query in enumerate(self.queries)}

        def position(ambiguity: Ambiguity) -> tuple[int, str]:
            index = len(order) if ambiguity.query is None else order[ambiguity.query]
            return (index, ambiguity.subject)

        for found in self.ambiguities.values():
            found.sort(key=position)
        ambiguities.sort(key=position)
        keys = sorted(self.evidence.tables, key=lambda k: (k[0] or "", k[1]))
        tables = tuple(self._table(key) for key in keys)
        relationships = self._relationships({(t.owner, t.name): t for t in tables})
        reports = tuple(self._report(r) for r in self.evidence.reports)
        dependencies = self._dependencies(tables, reports)
        return Graph(
            tables,
            relationships,
            reports,
            dependencies,
            _rollups(dependencies),
            tuple(self.queries),
            tuple(unparsed),
            tuple(ambiguities),
        )

    def _dependency_ambiguities(self) -> list[Ambiguity]:
        ambiguities: list[Ambiguity] = []
        for found in self.lineage.ambiguous:
            candidates: dict[str, tuple[Query, ...]] = {}
            for key in found.candidates:
                column = self.evidence.tables[key].columns.get(found.name)
                indices = (
                    set().union(column.declared, *column.references.values())
                    if column
                    else set()
                )
                candidates[_name(*key, found.name)] = self.records(
                    indices - {found.index}
                )
            ambiguity = Ambiguity(
                "dependency", self.queries[found.index], found.name, candidates
            )
            ambiguities.append(ambiguity)
            downstream = found.downstream
            match downstream:
                case ("column", key, name):
                    self.ambiguities[(key, name)].append(ambiguity)
                case ("table", key):
                    self.ambiguities[key].append(ambiguity)
                case _:
                    self.ambiguities[downstream].append(ambiguity)
        return ambiguities

    def _report(self, evidence: _infer.ReportEvidence) -> Report:
        query = self.queries[evidence.index]
        report = Report(
            query.name, query, (), tuple(self.ambiguities[("report", evidence.index)])
        )
        columns = tuple(
            OutputColumn(
                report,
                name,
                position,
                {} if fact.type is None else {fact.type: (query,)},
                tuple(self.ambiguities[("output", evidence.index, name)]),
            )
            for position, (name, fact) in enumerate(evidence.outputs, 1)
        )
        object.__setattr__(report, "output_columns", columns)
        return report

    def _dependencies(
        self, tables: tuple[Table, ...], reports: tuple[Report, ...]
    ) -> tuple[Dependency, ...]:
        by_key = {(t.owner, t.name): t for t in tables}
        by_index = {self.queries.index(r.query): r for r in reports}

        def end(found: _lineage.End) -> End:
            match found:
                case ("table", key):
                    return by_key[key]
                case ("column", key, name):
                    return next(c for c in by_key[key].columns if c.name == name)
                case ("report", index):
                    return by_index[index]
                case ("output", index, name):
                    return next(
                        c for c in by_index[index].output_columns if c.name == name
                    )

        dependencies = [
            Dependency(
                upstream,
                end(downstream),
                {s: self.records(found[s]) for s in _SUBTYPES if s in found},
            )
            for (up, downstream), found in self.lineage.dependencies.items()
            if isinstance(upstream := end(up), Table | Column)
        ]
        return tuple(sorted(dependencies, key=_dependency_order))

    def _relationships(
        self, tables: dict[_read.TableKey, Table]
    ) -> tuple[Relationship, ...]:
        found: list[Relationship] = []
        for sides, indices in self.evidence.relationships.items():
            columns = [tuple(tables[t].column(n) for n in names) for t, names in sides]
            keyed = [_key_of(c) for c in columns]
            direction = None
            if len([k for k in keyed if k is not None]) == 1:
                # The side whose columns equal a key of its table is the referenced side.
                referenced = 0 if keyed[0] is not None else 1
                direction = keyed[referenced]
                columns = [columns[1 - referenced], columns[referenced]]
            found.append(
                Relationship(
                    (columns[0], columns[1]), direction, None, self.records(indices)
                )
            )
        # A shared reference's sides both refer to one key of a third table (ADR 0002).
        refers = {(r.sides[0], r.direction) for r in found if r.direction is not None}
        for index, relationship in enumerate(found):
            first, second = relationship.sides
            tables_ = {first[0].table, second[0].table}
            for side, key in refers:
                if (
                    side == first
                    and key.columns[0].table not in tables_
                    and (second, key) in refers
                ):
                    found[index] = replace(relationship, shared=key)
        return tuple(
            sorted(
                found,
                key=lambda r: [
                    (_order(c.table), c.name) for side in r.sides for c in side
                ],
            )
        )

    def _column_ambiguities(self) -> list[Ambiguity]:
        ambiguities: list[Ambiguity] = []
        for found in self.evidence.ambiguous:
            candidates: dict[str, tuple[Query, ...]] = {}
            for key in found.candidates:
                column = self.evidence.tables[key].columns.get(found.name)
                indices = (
                    set().union(column.declared, *column.references.values())
                    if column
                    else set()
                )
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

    def _declaration_ambiguities(self) -> list[Ambiguity]:
        ambiguities: list[Ambiguity] = []
        for key, evidence in self.evidence.tables.items():
            if len(evidence.declarations) > 1:
                candidates = {
                    f"{d.kind} ({', '.join(d.columns)})": self.records(d.indices)
                    for d in evidence.declarations
                }
                ambiguity = Ambiguity("declaration", None, _name(*key), candidates)
                ambiguities.append(ambiguity)
                self.ambiguities[key].append(ambiguity)
        return ambiguities

    def _type_ambiguities(self) -> list[Ambiguity]:
        ambiguities: list[Ambiguity] = []
        for key, evidence in self.evidence.tables.items():
            for name, column in evidence.columns.items():
                declared = {
                    d.types[name] for d in evidence.declarations if name in d.types
                }
                # A declared column takes its declared type outright (ADR 0007).
                if len(column.types) > 1 and len(declared) != 1:
                    candidates: dict[str, tuple[Query, ...]] = {
                        t: self.records(column.types[t])
                        for t in _TYPES
                        if t in column.types
                    }
                    ambiguity = Ambiguity("type", None, _name(*key, name), candidates)
                    ambiguities.append(ambiguity)
                    self.ambiguities[(key, name)].append(ambiguity)
        return ambiguities

    def _table(self, key: _read.TableKey) -> Table:
        evidence = self.evidence.tables[key]
        kinds = {d.kind for d in evidence.declarations}
        declared = [c for d in evidence.declarations for c in d.columns]
        table = Table(
            key[0],
            key[1],
            (),
            self.records(evidence.read),
            self.records(evidence.write),
            self.records(set().union(*(d.indices for d in evidence.declarations))),
            tuple(
                Declaration(d.kind, d.columns, d.types, self.records(d.indices))
                for d in evidence.declarations
            ),
            kinds.pop() if len(kinds) == 1 else None,
            evidence.complete,
            tuple(
                Contradiction(self.queries[index], reason, column)
                for index, reason, column in evidence.contradictions
            ),
            (),
            tuple(self.ambiguities[key]),
        )
        # Declared order first, then each other column by name (ADR 0011).
        names = sorted(
            evidence.columns,
            key=lambda n: (
                n not in declared,
                declared.index(n) if n in declared else 0,
                n,
            ),
        )
        columns = tuple(
            Column(
                table,
                name,
                {
                    position: self.records(found)
                    for position, found in evidence.columns[name].references.items()
                },
                self.records(evidence.columns[name].declared),
                {
                    t: self.records(evidence.columns[name].types[t])
                    for t in _TYPES
                    if t in evidence.columns[name].types
                },
                self.records(evidence.columns[name].nullable),
                {
                    value: self.records(found)
                    for value, found in sorted(evidence.columns[name].observed.items())
                },
                bool(evidence.declarations) and name not in declared,
                tuple(self.ambiguities[(key, name)]),
            )
            for name in names
        )
        # The records are frozen, and a column needs its table before the table can hold it.
        object.__setattr__(table, "columns", columns)
        object.__setattr__(table, "keys", self._keys(table, evidence))
        return table

    def _keys(self, table: Table, evidence: _infer.TableEvidence) -> tuple[Key, ...]:
        by_name = {c.name: c for c in table.columns}
        others = {
            _bare_name(n)
            for o, n in self.evidence.tables
            if (o, n) != (table.owner, table.name)
        }
        found: dict[
            tuple[str, ...], tuple[NameMatch | None, dict[KeyShape, tuple[Query, ...]]]
        ] = {}
        for column in table.columns:
            match = _name_match(_bare_name(table.name), column.name, others)
            if match is not None:
                found[(column.name,)] = (match, {})
        for names, shapes in evidence.keys.items():
            match = found.get(names, (None, {}))[0]
            found[names] = (
                match,
                {s: self.records(shapes[s]) for s in _SHAPES if s in shapes},
            )
        order = {c.name: i for i, c in enumerate(table.columns)}
        return tuple(
            Key(tuple(by_name[n] for n in names), match, shapes)
            for names, (match, shapes) in sorted(
                found.items(), key=lambda k: (len(k[0]), [order[n] for n in k[0]])
            )
        )
