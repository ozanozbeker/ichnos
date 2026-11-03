"""Split each file into queries, parse each with sqlglot's Oracle dialect, and trace it into records ichnos owns.

This module is the only one that imports sqlglot (ADR 0004), and `_infer` combines its traces across queries.
sqlglot's `optimizer.scope` covers no statement level of an `UPDATE` or `MERGE` (ADR 0010), so the module walks every scope itself.
"""

import logging
from dataclasses import dataclass, field
from typing import Literal

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.tokens import Token, TokenType

# sqlglot logs a warning for each `Command` it falls back to, which `trace` lists as unparsed instead.
# A handler on its logger stops Python's last-resort handler printing the warning to stderr.
logging.getLogger("sqlglot").addHandler(logging.NullHandler())

type TableKey = tuple[str | None, str]
type Position = Literal[
    "select", "where", "join", "group_by", "order_by", "aggregate", "insert", "set"
]
type Statement = Literal["select", "insert", "update", "merge", "delete", "create"]
type TableKind = Literal["base table", "view", "materialized view"]
type Item = str | TableKey
"""One position of a select list: its name, or a table whose `*` the query alone cannot expand."""

# A `*` over a source whose names nothing can show, such as a recursive CTE before its body is read.
_ANY: TableKey = (None, "")

# Oracle reads these like columns, and none is a column of a table.
_PSEUDOCOLUMNS = frozenset(
    {
        "CONNECT_BY_ISCYCLE",
        "CONNECT_BY_ISLEAF",
        "CURRVAL",
        "LEVEL",
        "NEXTVAL",
        "ORA_ROWSCN",
        "ROWID",
        "ROWNUM",
    }
)
# sqlglot 30.26.0 reads these functions as columns when they stand unqualified (ADR 0004).
_FUNCTIONS_READ_AS_COLUMNS = frozenset(
    {
        "DBTIMEZONE",
        "ORA_INVOKING_USER",
        "ORA_INVOKING_USERID",
        "SESSIONTIMEZONE",
        "UID",
        "USER",
    }
)


class ReadError(Exception):
    """A query that ichnos cannot read whole."""


@dataclass(frozen=True, slots=True)
class ColumnRef:
    """One reference to a column of a table, with the tables it can belong to.

    `candidates` holds one layer per scope, from the reference's own scope outwards.
    The reference resolves when its first layer holds one table.
    """

    name: str
    candidates: tuple[tuple[TableKey, ...], ...]
    position: Position


@dataclass(frozen=True, slots=True)
class Write:
    """A table that a DML statement writes.

    `values` holds one item per value of an `INSERT` with no column list, and is `None` otherwise.
    """

    table: TableKey
    values: tuple[Item, ...] | None


@dataclass(frozen=True, slots=True)
class Creation:
    """The table that a creating query creates, with its kind and its column list (ADR 0008)."""

    table: TableKey
    kind: TableKind
    columns: tuple[Item, ...]


@dataclass(frozen=True, slots=True)
class Trace:
    """What one query shows about the tables it reads and writes."""

    statement: Statement
    reads: frozenset[TableKey]
    writes: tuple[Write, ...]
    creation: Creation | None
    refs: tuple[ColumnRef, ...]


def split(text: str) -> list[str]:
    """Split a file's text into queries at `;` tokens and at lines that hold only `/`."""
    try:
        tokens = sqlglot.Dialect.get_or_raise("oracle").tokenize(text)
    except SqlglotError:
        # Text that does not tokenize stays one query, which `trace` lists as unparsed.
        tokens: list[Token] = []
    cuts = [(t.start, t.end + 1) for t in tokens if t.token_type == TokenType.SEMICOLON]
    offset = 0
    for line in text.splitlines(keepends=True):
        if line.strip() == "/" and not _inside_token(tokens, offset + line.index("/")):
            cuts.append((offset, offset + len(line)))
        offset += len(line)
    queries: list[str] = []
    start = 0
    for end, next_start in [*sorted(cuts), (len(text), len(text))]:
        query = text[start:end].strip()
        if query:
            queries.append(query)
        start = next_start
    return queries


def _inside_token(tokens: list[Token], offset: int) -> bool:
    return any(
        t.start <= offset <= t.end and t.token_type != TokenType.SLASH for t in tokens
    )


def trace(text: str) -> Trace:
    """Parse one query and trace it.

    Raises
    ------
    ReadError
        When sqlglot raises or returns a `Command`, the statement is not a `SELECT`, DML or a creating query, or a later step raises.
    """
    try:
        tree = sqlglot.parse_one(text, read="oracle")
    except SqlglotError as error:
        raise ReadError(str(error)) from error
    if isinstance(tree, exp.Command):
        message = "sqlglot reads the statement as an opaque command"
        raise ReadError(message)
    try:
        return _trace(tree)
    except ReadError:
        raise
    # A query is read whole or skipped, never in part (ADR 0004). No known query reaches this clause.
    except Exception as error:  # pragma: no cover
        message = f"{type(error).__name__}: {error}"
        raise ReadError(message) from error


def _trace(tree: exp.Expr) -> Trace:
    walker = _Walker()
    statement: Statement
    match tree:
        case exp.Query():
            walker.query(tree, None, {})
            statement = "select"
        case exp.Insert():
            statement = walker.insert(tree)
        case exp.MultitableInserts():
            statement = walker.insert_all(tree)
        case exp.Update():
            statement = walker.update(tree)
        case exp.Merge():
            statement = walker.merge(tree)
        case exp.Delete():
            statement = walker.delete(tree)
        case exp.Create(kind="TABLE" | "VIEW", expression=exp.Query()):
            statement = walker.create(tree)
        case _:
            message = f"not a SELECT, DML or a creating query: {tree.key.upper()}"
            raise ReadError(message)
    return walker.result(statement)


def _name(identifier: exp.Expression) -> str:
    """Return an identifier in dictionary form: uppercase unless quoted."""
    if isinstance(identifier, exp.Identifier) and identifier.quoted:
        return identifier.name
    return identifier.name.upper()


def _table_key(table: exp.Table) -> TableKey:
    owner = table.args.get("db")
    return (_name(owner) if owner else None, _name(table.this))


@dataclass(slots=True)
class _TableSource:
    key: TableKey


@dataclass(slots=True)
class _LocalSource:
    columns: tuple[Item, ...]


type _Source = _TableSource | _LocalSource


@dataclass(slots=True)
class _Scope:
    parent: _Scope | None
    sources: dict[str, _Source] = field(default_factory=dict)
    # An unaliased table is also reachable by its qualified name, as in `sales.orders.order_id`.
    unaliased: dict[TableKey, _TableSource] = field(default_factory=dict)
    using: dict[str, list[_Source]] = field(default_factory=dict)
    aliases: set[str] = field(default_factory=set)


class _Walker:
    """Walk one statement's scopes and collect its table and column references."""

    def __init__(self) -> None:
        self.reads: set[TableKey] = set()
        self.writes: list[Write] = []
        self.creation: Creation | None = None
        self.refs: list[ColumnRef] = []

    def result(self, statement: Statement) -> Trace:
        reads = frozenset(self.reads)
        return Trace(
            statement, reads, tuple(self.writes), self.creation, tuple(self.refs)
        )

    # --- statements ---------------------------------------------------------------------------

    def insert(self, tree: exp.Insert) -> Statement:
        source = (
            self.query(tree.expression, None, {})
            if isinstance(tree.expression, exp.Query)
            else None
        )
        self._insert(tree, _Scope(None), source)
        return "insert"

    def insert_all(self, tree: exp.MultitableInserts) -> Statement:
        source = self.query(tree.args["source"], None, {})
        scope = _Scope(None, {"": source})
        for conditional in tree.expressions:
            self.expression(conditional.args.get("expression"), scope, "where")
            self._insert(conditional.this, scope, source)
        return "insert"

    def _insert(
        self, insert: exp.Insert, scope: _Scope, source: _LocalSource | None
    ) -> None:
        """Record one `INSERT` or one `INTO` of an `INSERT ALL`, whose values come from `source` or a `VALUES` list."""
        target = _table_key(
            insert.this.this if isinstance(insert.this, exp.Schema) else insert.this
        )
        self._targets(insert.this, target, "insert")
        values = insert.expression
        if isinstance(values, exp.Values):
            [row] = values.expressions
            self.expression(row, scope, "select")
            items: tuple[Item, ...] = ("",) * len(row.expressions)
        else:
            items = source.columns if source is not None else ()
        listed = isinstance(insert.this, exp.Schema)
        self.writes.append(Write(target, None if listed else items))

    def update(self, tree: exp.Update) -> Statement:
        scope = _Scope(None)
        target = self._target(scope, tree.this)
        self.writes.append(Write(target, None))
        self._assignments(tree.expressions, scope, target)
        self.expression(tree.args.get("where"), scope, "where")
        return "update"

    def merge(self, tree: exp.Merge) -> Statement:
        scope = _Scope(None)
        target = self._target(scope, tree.this)
        self._add_source(scope, tree.args["using"], {})
        self.expression(tree.args["on"], scope, "join")
        values: tuple[Item, ...] | None = None
        for when in tree.args["whens"].expressions:
            self.expression(when.args.get("condition"), scope, "where")
            action = when.args["then"]
            if isinstance(action, exp.Update):
                self._assignments(action.expressions, scope, target)
            elif isinstance(action, exp.Insert):
                self._targets(action.this, target, "insert")
                self.expression(action.expression, scope, "select")
                if not isinstance(action.this, exp.Tuple):
                    values = ("",) * len(action.expression.expressions)
            self.expression(action.args.get("where"), scope, "where")
        self.writes.append(Write(target, values))
        return "merge"

    def delete(self, tree: exp.Delete) -> Statement:
        scope = _Scope(None)
        target = self._target(scope, tree.this)
        self.writes.append(Write(target, None))
        self.expression(tree.args.get("where"), scope, "where")
        return "delete"

    def create(self, tree: exp.Create) -> Statement:
        listed = isinstance(tree.this, exp.Schema)
        target = _table_key(tree.this.this if listed else tree.this)
        source = self.query(tree.expression, None, {})
        properties = tree.args.get("properties")
        materialized = properties is not None and any(
            isinstance(p, exp.MaterializedProperty) for p in properties.expressions
        )
        kind: TableKind = (
            "base table"
            if tree.kind == "TABLE"
            else "materialized view"
            if materialized
            else "view"
        )
        columns = (
            tuple(_name(c) for c in tree.this.expressions) if listed else source.columns
        )
        self.creation = Creation(target, kind, columns)
        return "create"

    def _target(self, scope: _Scope, node: exp.Table) -> TableKey:
        source = self._add_source(scope, node, {})
        if not isinstance(source, _TableSource):
            message = "the statement writes a query, not a table"
            raise ReadError(message)
        return source.key

    def _targets(
        self, node: exp.Expression, target: TableKey, position: Position
    ) -> None:
        if isinstance(node, exp.Schema | exp.Tuple):
            for column in node.expressions:
                self.refs.append(
                    ColumnRef(
                        _name(
                            column.this if isinstance(column, exp.Column) else column
                        ),
                        ((target,),),
                        position,
                    )
                )

    def _assignments(
        self, assignments: list[exp.Expression], scope: _Scope, target: TableKey
    ) -> None:
        for assignment in assignments:
            columns = (
                assignment.this.expressions
                if isinstance(assignment.this, exp.Tuple)
                else [assignment.this]
            )
            for column in columns:
                self.refs.append(ColumnRef(_name(column.this), ((target,),), "set"))
            self.expression(assignment.expression, scope, "select")

    # --- queries ------------------------------------------------------------------------------

    def query(
        self, node: exp.Expr, parent: _Scope | None, ctes: dict[str, _LocalSource]
    ) -> _LocalSource:
        """Walk a query and return its output column names as a local relation."""
        ctes = dict(ctes)
        with_ = node.args.get("with_")
        for cte in with_.expressions if with_ else ():
            name = _name(cte.args["alias"].this)
            declared = [_name(c) for c in cte.args["alias"].columns]
            # A recursive CTE reads itself, so its name is visible inside its own body.
            ctes[name] = _LocalSource(tuple(declared) or _output_names(cte.this))
            body = self.query(cte.this, parent, ctes)
            ctes[name] = _LocalSource(tuple(declared) or body.columns)
        match node:
            case exp.Subquery():
                return self.query(node.this, parent, ctes)
            case exp.SetOperation():
                first = self.query(node.left, parent, ctes)
                self.query(node.right, parent, ctes)
                # A set operation's `ORDER BY` names its output columns only.
                self.expression(
                    node.args.get("order"),
                    _Scope(
                        parent, aliases={c for c in first.columns if isinstance(c, str)}
                    ),
                    "order_by",
                )
                return first
            case exp.Select():
                return self._select(node, parent, ctes)
            case _:
                message = f"unsupported query: {node.key.upper()}"
                raise ReadError(message)

    def _select(
        self, node: exp.Select, parent: _Scope | None, ctes: dict[str, _LocalSource]
    ) -> _LocalSource:
        scope = _Scope(parent)
        from_ = node.args.get("from_")
        if from_:
            self._add_source(scope, from_.this, ctes)
        for join in node.args.get("joins") or ():
            self._join(scope, join, ctes)
        for projection in node.expressions:
            self.expression(projection, scope, "select")
            if isinstance(projection, exp.Alias):
                scope.aliases.add(_name(projection.args["alias"]))
        self.expression(node.args.get("where"), scope, "where")
        self.expression(node.args.get("group"), scope, "group_by")
        self.expression(node.args.get("having"), scope, "where")
        connect = node.args.get("connect")
        if connect:
            self.expression(connect.args.get("start"), scope, "where")
            self.expression(connect.args["connect"], scope, "join")
        self.expression(node.args.get("order"), scope, "order_by")
        return _LocalSource(_expand(node, scope))

    def _join(
        self, scope: _Scope, join: exp.Join, ctes: dict[str, _LocalSource]
    ) -> None:
        before = list(scope.sources.values())
        source = self._add_source(scope, join.this, ctes)
        self.expression(join.args.get("on"), scope, "join")
        for identifier in join.args.get("using") or ():
            name = _name(identifier)
            left = [s for s in before if _holds(s, name)]
            self._emit(name, source, "join")
            if len(left) == 1:
                self._emit(name, left[0], "join")
            else:
                tables = tuple(s.key for s in left if isinstance(s, _TableSource))
                self.refs.append(ColumnRef(name, (tables,), "join"))
            scope.using[name] = [*left, source]

    def _add_source(
        self, scope: _Scope, node: exp.Expression, ctes: dict[str, _LocalSource]
    ) -> _Source:
        alias = node.args.get("alias")
        if isinstance(node, exp.Table):
            key = _table_key(node)
            if key[0] is None and key[1] in ctes:
                local = ctes[key[1]]
                scope.sources[_name(alias.this) if alias else key[1]] = local
                return local
            if key == (None, "DUAL"):
                # DUAL is not a table, and its one column is never a column reference.
                return _LocalSource(())
            self.reads.add(key)
            table = _TableSource(key)
            if alias:
                scope.sources[_name(alias.this)] = table
            else:
                scope.sources[key[1]] = table
                scope.unaliased[key] = table
            return table
        local = self.query(node, scope.parent, ctes)
        scope.sources[_name(alias.this) if alias else f"#{len(scope.sources)}"] = local
        return local

    # --- expressions --------------------------------------------------------------------------

    def expression(
        self, node: exp.Expr | None, scope: _Scope, position: Position
    ) -> None:
        """Collect the column references of one expression, and walk each subquery inside it."""
        match node:
            case None:
                pass
            case exp.Query() | exp.Subquery():
                self.query(node, scope, {})
            case exp.Column():
                self._column(node, scope, position)
            case exp.Window():
                self.expression(node.this, scope, position)
                for partition in node.args.get("partition_by") or ():
                    self.expression(partition, scope, "group_by")
                self.expression(node.args.get("order"), scope, "order_by")
            case exp.Order() if not isinstance(node.parent, exp.Query):
                # The `ORDER BY` inside `LISTAGG ... WITHIN GROUP`.
                self.expression(node.this, scope, position)
                for ordered in node.expressions:
                    self.expression(ordered, scope, "order_by")
            case _:
                position = _inner_position(node, position)
                for child in node.iter_expressions():
                    self.expression(child, scope, position)

    def _column(self, node: exp.Column, scope: _Scope, position: Position) -> None:
        if isinstance(node.this, exp.Star):
            return
        name = _name(node.this)
        if not node.this.quoted and name in _PSEUDOCOLUMNS:
            return
        qualifier = node.args.get("table")
        if qualifier is not None:
            owner = node.args.get("db")
            self._emit(
                name,
                _lookup(scope, _name(owner) if owner else None, _name(qualifier)),
                position,
            )
        elif node.this.quoted or name not in _FUNCTIONS_READ_AS_COLUMNS:
            if not (position == "order_by" and name in scope.aliases):
                self._unqualified(name, scope, position)

    def _unqualified(self, name: str, scope: _Scope, position: Position) -> None:
        layers: list[tuple[TableKey, ...]] = []
        current: _Scope | None = scope
        while current is not None:
            if name in current.using:
                for source in current.using[name]:
                    self._emit(name, source, position)
                return
            holders = [s for s in current.sources.values() if _holds(s, name)]
            if any(isinstance(s, _LocalSource) for s in holders):
                # A local relation whose names are known holds the name alone, because Oracle raises ORA-00918 otherwise.
                # One whose names a `*` hides may hold it, so the reference gives no evidence.
                return
            if holders:
                layers.append(
                    tuple(s.key for s in holders if isinstance(s, _TableSource))
                )
            current = current.parent
        if layers:
            self.refs.append(ColumnRef(name, tuple(layers), position))

    def _emit(self, name: str, source: _Source, position: Position) -> None:
        if isinstance(source, _TableSource):
            self.refs.append(ColumnRef(name, ((source.key,),), position))


def _lookup(scope: _Scope, owner: str | None, qualifier: str) -> _Source:
    current: _Scope | None = scope
    while current is not None:
        if owner is None and qualifier in current.sources:
            return current.sources[qualifier]
        table = current.unaliased.get((owner, qualifier))
        if table is not None:
            return table
        current = current.parent
    message = f"unknown table or alias {qualifier if owner is None else f'{owner}.{qualifier}'}"
    raise ReadError(message)


def _holds(source: _Source, name: str) -> bool:
    if isinstance(source, _TableSource):
        return True
    return any(not isinstance(c, str) or c == name for c in source.columns)


def _inner_position(node: exp.Expr, position: Position) -> Position:
    """Return the position of the column references inside a node."""
    if position == "where" and isinstance(node, exp.EQ) and _equates_two_tables(node):
        return "join"
    if position in {"select", "where"} and isinstance(node, exp.AggFunc):
        return "aggregate"
    return position


def _equates_two_tables(node: exp.EQ) -> bool:
    """Return whether a `WHERE` conjunct compares bare columns of two table references with `=`."""
    left, right = node.this, node.expression
    return (
        isinstance(left, exp.Column)
        and isinstance(right, exp.Column)
        and left.table != right.table
    )


def _output_names(node: exp.Expr) -> tuple[Item, ...]:
    """Return a query's output names before it is walked, with `_ANY` for each `*`."""
    while isinstance(node, exp.Subquery | exp.SetOperation):
        node = node.this if isinstance(node, exp.Subquery) else node.left
    return tuple(
        _ANY
        if isinstance(p, exp.Star) or isinstance(p.this, exp.Star)
        else _projection_name(p)
        for p in node.expressions
    )


def _projection_name(projection: exp.Expr) -> str:
    """Return the name that a local relation's select list gives one position."""
    match projection:
        case exp.Alias():
            return _name(projection.args["alias"])
        case exp.Column():
            return _name(projection.this)
        case _:
            # Only an alias or a column name can refer to the position from outside.
            return ""


def _expand(node: exp.Select, scope: _Scope) -> tuple[Item, ...]:
    """Return a select's items, expanding a `*` over local relations and keeping one item per table a `*` covers."""
    items: list[Item] = []
    for projection in node.expressions:
        match projection:
            case exp.Star():
                sources = list(scope.sources.values())
            case exp.Column(this=exp.Star()):
                sources = [_lookup(scope, None, _name(projection.args["table"]))]
            case _:
                items.append(_projection_name(projection))
                continue
        for source in sources:
            items.extend(
                (source.key,) if isinstance(source, _TableSource) else source.columns
            )
    return tuple(items)
