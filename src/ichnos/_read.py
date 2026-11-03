"""Split each file into queries, parse each with sqlglot's Oracle dialect, and trace it into records ichnos owns.

This module is the only one that imports sqlglot (ADR 0004), and `_infer` combines its traces across queries.
sqlglot's `optimizer.scope` covers no statement level of an `UPDATE` or `MERGE` (ADR 0010), so the module walks every scope itself.
"""

import logging
from dataclasses import dataclass, field, replace
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
type Type = Literal["text", "number", "datetime", "interval"]
type KeyShape = Literal["generated", "merge", "single_row", "grouped"]
type Item = str | TableKey
"""One position of a select list: its name, or a table whose `*` the query alone cannot expand."""

type Value = Fact | TableKey
"""What one assigned value shows about its column, or a table whose `*` the query alone cannot expand."""

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
class Fact:
    """What one column reference, or one value a statement assigns, shows about a column (ADR 0003, ADR 0007)."""

    type: Type | None = None
    observed: tuple[str, ...] = ()
    nullable: bool = False
    # The value is a sequence's NEXTVAL or SYS_GUID(), which gives `generated` key evidence (ADR 0006).
    generated: bool = False


@dataclass(frozen=True, slots=True)
class KeyEvidence:
    """A set of columns that one query's shape shows identifies at most one row (ADR 0006)."""

    table: TableKey
    columns: tuple[str, ...]
    shape: KeyShape


@dataclass(frozen=True, slots=True)
class ColumnRef:
    """One reference to a column of a table, with the tables it can belong to.

    `candidates` holds one layer per scope, from the reference's own scope outwards.
    The reference resolves when its first layer holds one table.
    """

    name: str
    candidates: tuple[tuple[TableKey, ...], ...]
    position: Position
    fact: Fact = Fact()


_NOTHING = Fact()


@dataclass(frozen=True, slots=True)
class Write:
    """A table that a DML statement writes.

    `values` holds what each value of an `INSERT` with no column list shows, or the table of a `*` among them.
    It is `None` for a statement that names every column it writes.
    """

    table: TableKey
    values: tuple[Value, ...] | None


@dataclass(frozen=True, slots=True)
class Creation:
    """The table that a creating query creates, with its kind and its column list (ADR 0008)."""

    table: TableKey
    kind: TableKind
    columns: tuple[Item, ...]
    types: tuple[Type | None, ...]


@dataclass(frozen=True, slots=True)
class Join:
    """Every bare `=` between two table references of one query, which together give one relationship (ADR 0002).

    A `NATURAL JOIN` holds no columns, because only declarations can name them (ADR 0008).
    """

    left: TableKey
    right: TableKey
    columns: tuple[tuple[str, str], ...]
    natural: bool = False


@dataclass(frozen=True, slots=True)
class Trace:
    """What one query shows about the tables it reads and writes."""

    statement: Statement
    reads: frozenset[TableKey]
    writes: tuple[Write, ...]
    creation: Creation | None
    refs: tuple[ColumnRef, ...]
    keys: tuple[KeyEvidence, ...]
    joins: tuple[Join, ...]


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
    # The null-supplying side of an outer join, where `IS NULL` tests for an absent row (ADR 0007).
    optional: bool = False


@dataclass(slots=True)
class _LocalSource:
    columns: tuple[Item, ...]
    values: tuple[Value, ...] = ()


type _Source = _TableSource | _LocalSource


@dataclass(slots=True)
class _Scope:
    parent: _Scope | None
    sources: dict[str, _Source] = field(default_factory=dict)
    # An unaliased table is also reachable by its qualified name, as in `sales.orders.order_id`.
    unaliased: dict[TableKey, _TableSource] = field(default_factory=dict)
    using: dict[str, list[_Source]] = field(default_factory=dict)
    aliases: set[str] = field(default_factory=set)
    # The CTEs that a subquery anywhere in the scope can read.
    ctes: dict[str, _LocalSource] = field(default_factory=dict)


class _Walker:
    """Walk one statement's scopes and collect its table and column references."""

    def __init__(self) -> None:
        self.reads: set[TableKey] = set()
        self.writes: list[Write] = []
        self.creation: Creation | None = None
        self.refs: list[ColumnRef] = []
        # What a bare column learns from its parent expression, keyed by the column node's id.
        self.facts: dict[int, Fact] = {}
        self.keys: list[KeyEvidence] = []
        # The equalities between each pair of table references, keyed by the two sources' ids.
        self.pairs: dict[
            tuple[int, int], tuple[_TableSource, _TableSource, list[tuple[str, str]]]
        ] = {}
        self.naturals: list[Join] = []

    def result(self, statement: Statement) -> Trace:
        reads = frozenset(self.reads)
        return Trace(
            statement,
            reads,
            tuple(self.writes),
            self.creation,
            tuple(self.refs),
            tuple(dict.fromkeys(self.keys)),
            (
                *(
                    Join(a.key, b.key, tuple(dict.fromkeys(c)))
                    for a, b, c in self.pairs.values()
                ),
                *self.naturals,
            ),
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
        listed = isinstance(insert.this, exp.Schema)
        target = _table_key(insert.this.this if listed else insert.this)
        values: tuple[Value, ...] = source.values if source is not None else ()
        if isinstance(insert.expression, exp.Values):
            [row] = insert.expression.expressions
            self.expression(row, scope, "select")
            values = tuple(assigned(v) for v in row.expressions)
        self._targets(insert.this, target, values)
        self.writes.append(Write(target, None if listed else values))

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
        source = self._add_source(scope, tree.args["using"], {})
        self.expression(tree.args["on"], scope, "join")
        self._equalities(tree.args["on"], scope)
        target_source = (
            _lookup(scope, target[0], target[1])
            if tree.this.alias == ""
            else scope.sources[_name(tree.this.args["alias"].this)]
        )
        compared = _compared(tree.args["on"], scope, target_source, source)
        if compared:
            self.keys.append(KeyEvidence(target, compared, "merge"))
        values: tuple[Value, ...] | None = None
        for when in tree.args["whens"].expressions:
            self.expression(when.args.get("condition"), scope, "where")
            action = when.args["then"]
            if isinstance(action, exp.Update):
                self._assignments(action.expressions, scope, target)
            elif isinstance(action, exp.Insert):
                row = tuple(assigned(v) for v in action.expression.expressions)
                self._targets(action.this, target, row)
                self.expression(action.expression, scope, "select")
                if not isinstance(action.this, exp.Tuple):
                    values = row
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
        # Oracle gives a declared column the data type of its expression (ADR 0007).
        types = tuple(v.type if isinstance(v, Fact) else None for v in source.values)
        if len(types) != len(columns):
            types = (None,) * len(columns)
        self.creation = Creation(target, kind, columns, types)
        grouped = _grouped(tree.expression, columns)
        if grouped:
            self.keys.append(KeyEvidence(target, grouped, "grouped"))
        return "create"

    def _target(self, scope: _Scope, node: exp.Table) -> TableKey:
        source = self._add_source(scope, node, {})
        if not isinstance(source, _TableSource):
            message = "the statement writes a query, not a table"
            raise ReadError(message)
        return source.key

    def _targets(
        self, node: exp.Expression, target: TableKey, values: tuple[Value, ...]
    ) -> None:
        """Record each column that a column list names, with what the value at its position shows."""
        if isinstance(node, exp.Schema | exp.Tuple):
            for index, column in enumerate(node.expressions):
                name = _name(column.this if isinstance(column, exp.Column) else column)
                value = values[index] if index < len(values) else Fact()
                fact = value if isinstance(value, Fact) else Fact()
                self.refs.append(ColumnRef(name, ((target,),), "insert", fact))

    def _assignments(
        self, assignments: list[exp.Expression], scope: _Scope, target: TableKey
    ) -> None:
        for assignment in assignments:
            columns = (
                assignment.this.expressions
                if isinstance(assignment.this, exp.Tuple)
                else [assignment.this]
            )
            fact = assigned(assignment.expression) if len(columns) == 1 else Fact()
            for column in columns:
                ref = ColumnRef(_name(column.this), ((target,),), "set", fact)
                self.refs.append(ref)
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
            ctes[name] = _LocalSource(tuple(declared) or body.columns, body.values)
        match node:
            case exp.Subquery():
                return self.query(node.this, parent, ctes)
            case exp.SetOperation():
                self._same_type_positions(node)
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

    def _same_type_positions(self, node: exp.SetOperation) -> None:
        """Give a bare column the fixed type that another branch has at its position (ADR 0007)."""
        branches: list[exp.Expr] = []
        pending: list[exp.Expr] = [node]
        while pending:
            current = _unparen(pending.pop(0))
            if isinstance(current, exp.SetOperation):
                pending[:0] = [current.left, current.right]
            elif isinstance(current, exp.Select):
                branches.append(current)
        for position in zip(*(b.expressions for b in branches), strict=False):
            shared = next(filter(None, map(_fixed_type, position)), None)
            for projection in position:
                bare = _bare(projection)
                if bare is not None and shared is not None:
                    self.facts[id(bare)] = Fact(shared)

    def _select(
        self, node: exp.Select, parent: _Scope | None, ctes: dict[str, _LocalSource]
    ) -> _LocalSource:
        scope = _Scope(parent, ctes=ctes)
        from_ = node.args.get("from_")
        if from_:
            self._add_source(scope, from_.this, ctes)
        for join in node.args.get("joins") or ():
            self._join(scope, join, ctes)
        where = node.args.get("where")
        for column in where.find_all(exp.Column) if where else ():
            # Oracle's `(+)` marks the null-supplying table of an outer join.
            source = (
                scope.sources.get(column.table.upper())
                if column.args.get("join_mark")
                else None
            )
            if isinstance(source, _TableSource):
                source.optional = True
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
            self._equalities(connect.args["connect"], scope)
        for join in node.args.get("joins") or ():
            self._equalities(join.args.get("on"), scope)
        self._equalities(where and where.this, scope)
        self.expression(node.args.get("order"), scope, "order_by")
        return _LocalSource(*_expand(node, scope))

    def _join(
        self, scope: _Scope, join: exp.Join, ctes: dict[str, _LocalSource]
    ) -> None:
        before = list(scope.sources.values())
        source = self._add_source(scope, join.this, ctes)
        natural = join.args.get("method") == "NATURAL" and len(before) == 1
        if (
            natural
            and isinstance(before[0], _TableSource)
            and isinstance(source, _TableSource)
        ):
            self.naturals.append(Join(before[0].key, source.key, (), natural=True))
        side = join.args.get("side")
        for optional in [
            *(before if side in {"RIGHT", "FULL"} else ()),
            *((source,) if side in {"LEFT", "FULL"} else ()),
        ]:
            if isinstance(optional, _TableSource):
                optional.optional = True
        self.expression(join.args.get("on"), scope, "join")
        for identifier in join.args.get("using") or ():
            name = _name(identifier)
            left = [s for s in before if _holds(s, name)]
            self._emit(name, source, "join")
            if len(left) == 1:
                self._emit(name, left[0], "join")
                if isinstance(left[0], _TableSource) and isinstance(
                    source, _TableSource
                ):
                    self._pair(left[0], source, name, name)
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
                self.query(node, scope, scope.ctes)
                self._single_row(node, scope)
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
                for column, fact in _child_facts(node):
                    self.facts[id(column)] = fact
                for child in node.iter_expressions():
                    self.expression(child, scope, position)

    def _equalities(self, clause: exp.Expr | None, scope: _Scope) -> None:
        """Record each AND-connected bare `=` between columns of two table references (ADR 0002)."""
        for conjunct in _conjuncts(clause) if clause is not None else ():
            if not isinstance(conjunct, exp.EQ):
                continue
            sides = [_unparen(conjunct.this), _unparen(conjunct.expression)]
            # `CONNECT BY PRIOR a = b` compares a column of one row with a column of another row.
            prior = any(isinstance(s, exp.Prior) for s in sides)
            a, b = (_bare(s.this if isinstance(s, exp.Prior) else s) for s in sides)
            if a is None or b is None:
                continue
            left, right = self._resolve(a, scope), self._resolve(b, scope)
            if not (isinstance(left, _TableSource) and isinstance(right, _TableSource)):
                continue
            if left is not right or prior:
                self._pair(left, right, _name(a.this), _name(b.this))

    def _resolve(self, column: exp.Column, scope: _Scope) -> _Source | None:
        """Return the one source that a column belongs to, or None when the query alone cannot tell."""
        qualifier = column.args.get("table")
        if qualifier is not None:
            owner = column.args.get("db")
            return _lookup(scope, _name(owner) if owner else None, _name(qualifier))
        current: _Scope | None = scope
        name = _name(column.this)
        while current is not None:
            holders = [s for s in current.sources.values() if _holds(s, name)]
            if holders:
                return holders[0] if len(holders) == 1 else None
            current = current.parent
        return None

    def _pair(self, left: _TableSource, right: _TableSource, a: str, b: str) -> None:
        if (id(right), id(left)) in self.pairs and left is not right:
            left, right, a, b = right, left, b, a
        entry = self.pairs.setdefault((id(left), id(right)), (left, right, []))
        entry[2].append((a, b))

    def _single_row(self, node: exp.Expr, scope: _Scope) -> None:
        """Record the key that a single-row subquery shows, because Oracle raises ORA-01427 when it returns two rows."""
        parent = node.parent
        many = isinstance(parent, exp.In | exp.Exists | exp.Any | exp.All)
        if many or not isinstance(
            parent, exp.Binary | exp.Alias | exp.Select | exp.Func
        ):
            return
        select = _unparen(node.this if isinstance(node, exp.Subquery) else node)
        if not isinstance(select, exp.Select) or select.args.get("joins"):
            return
        from_ = select.args.get("from_")
        table = from_.this if from_ else None
        if not isinstance(table, exp.Table) or _table_key(table)[1] == "DUAL":
            return
        shown = any(select.args.get(a) for a in ("group", "distinct", "limit", "with_"))
        if shown or any(p.find(exp.AggFunc) for p in select.expressions):
            return
        if any(c.name.upper() == "ROWNUM" for c in select.find_all(exp.Column)):
            return
        inner = _Scope(scope)
        source = self._add_source(inner, table, scope.ctes)
        where = select.args.get("where")
        compared = _compared(where and where.this, inner, source, None)
        if compared and isinstance(source, _TableSource):
            self.keys.append(KeyEvidence(source.key, compared, "single_row"))

    def _column(self, node: exp.Column, scope: _Scope, position: Position) -> None:
        if isinstance(node.this, exp.Star):
            return
        name = _name(node.this)
        fact = self.facts.pop(id(node), Fact())
        if not node.this.quoted and name in _PSEUDOCOLUMNS:
            return
        qualifier = node.args.get("table")
        if qualifier is not None:
            owner = node.args.get("db")
            source = _lookup(scope, _name(owner) if owner else None, _name(qualifier))
            self._emit(name, source, position, fact)
        elif node.this.quoted or name not in _FUNCTIONS_READ_AS_COLUMNS:
            if not (position == "order_by" and name in scope.aliases):
                self._unqualified(name, scope, position, fact)

    def _unqualified(
        self, name: str, scope: _Scope, position: Position, fact: Fact
    ) -> None:
        layers: list[tuple[_TableSource, ...]] = []
        current: _Scope | None = scope
        while current is not None:
            if name in current.using:
                for source in current.using[name]:
                    self._emit(name, source, position, fact)
                return
            holders = [s for s in current.sources.values() if _holds(s, name)]
            if any(isinstance(s, _LocalSource) for s in holders):
                # A local relation whose names are known holds the name alone, because Oracle raises ORA-00918 otherwise.
                # One whose names a `*` hides may hold it, so the reference gives no evidence.
                return
            if holders:
                layers.append(tuple(s for s in holders if isinstance(s, _TableSource)))
            current = current.parent
        if layers:
            if len(layers[0]) == 1 and layers[0][0].optional:
                fact = replace(fact, nullable=False)
            keys = tuple(tuple(s.key for s in layer) for layer in layers)
            self.refs.append(ColumnRef(name, keys, position, fact))

    def _emit(
        self, name: str, source: _Source, position: Position, fact: Fact = _NOTHING
    ) -> None:
        if isinstance(source, _TableSource):
            if source.optional:
                fact = replace(fact, nullable=False)
            self.refs.append(ColumnRef(name, ((source.key,),), position, fact))


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


def _conjuncts(node: exp.Expr) -> list[exp.Expr]:
    node = _unparen(node)
    if isinstance(node, exp.And):
        return [*_conjuncts(node.this), *_conjuncts(node.expression)]
    return [node]


def _compared(
    clause: exp.Expr | None, scope: _Scope, table: _Source, source: _Source | None
) -> tuple[str, ...]:
    """Return the columns of `table` that a clause compares, when every conjunct is a bare `=` to a key value.

    A key value is a bind variable, a column of an outer query, or a column of `source`.
    A literal, a range, `IS NULL`, a function or an `OR` can make the columns unique in part of the table only (ADR 0006).
    """
    if clause is None or not isinstance(table, _TableSource):
        return ()
    columns: list[str] = []
    for conjunct in _conjuncts(clause):
        if not isinstance(conjunct, exp.EQ):
            return ()
        sides = [
            _side(_unparen(s), scope, table, source)
            for s in conjunct.iter_expressions()
        ]
        column = next((s for s in sides if s not in {None, "value"}), None)
        if column is None or "value" not in sides:
            return ()
        columns.append(column)
    return tuple(dict.fromkeys(columns))


def _side(
    node: exp.Expr, scope: _Scope, table: _TableSource, source: _Source | None
) -> str | None:
    """Return a compared column of `table` by name, `"value"` for a key value, or None for anything else."""
    if isinstance(node, exp.Placeholder):
        return "value"
    if not isinstance(node, exp.Column) or isinstance(node.this, exp.Star):
        return None
    owner = node.args.get("db")
    qualifier = node.args.get("table")
    if qualifier is None:
        # An unqualified column belongs to `table` only when it is the scope's one source.
        return _name(node.this) if list(scope.sources.values()) == [table] else None
    # The walk has looked the qualifier up already, so it names a source.
    found = _lookup(scope, _name(owner) if owner else None, _name(qualifier))
    if found is table:
        return _name(node.this)
    outer = found not in scope.sources.values()
    return "value" if outer or found is source else None


def _grouped(query: exp.Expr, columns: tuple[Item, ...]) -> tuple[str, ...]:
    """Return the declared columns that a creating query's rows are unique on (ADR 0006)."""
    names = [c for c in columns if isinstance(c, str)]
    if len(names) != len(columns):
        return ()
    query = _unparen(query)
    if isinstance(query, exp.SetOperation):
        # `UNION ALL` keeps repeated rows, and the other set operations remove them.
        return tuple(names) if query.args.get("distinct") else ()
    if not isinstance(query, exp.Select) or len(query.expressions) != len(names):
        return ()
    if query.args.get("distinct"):
        return tuple(names)
    group = query.args.get("group")
    if group is None or any(
        group.find(exp.Rollup, exp.Cube, exp.GroupingSets) for _ in [0]
    ):
        return ()
    expressions = list(group.expressions)
    return tuple(
        name
        for name, projection in zip(names, query.expressions, strict=True)
        if (projection.this if isinstance(projection, exp.Alias) else projection)
        in expressions
    )


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


def _expand(
    node: exp.Select, scope: _Scope
) -> tuple[tuple[Item, ...], tuple[Value, ...]]:
    """Return a select's items and what each value shows, expanding a `*` over local relations.

    A `*` over a table keeps one item, the table, which a declaration can expand later (ADR 0008).
    """
    items: list[Item] = []
    values: list[Value] = []
    for projection in node.expressions:
        match projection:
            case exp.Star():
                sources = list(scope.sources.values())
            case exp.Column(this=exp.Star()):
                sources = [_lookup(scope, None, _name(projection.args["table"]))]
            case _:
                items.append(_projection_name(projection))
                values.append(
                    assigned(
                        projection.this
                        if isinstance(projection, exp.Alias)
                        else projection
                    )
                )
                continue
        for source in sources:
            if isinstance(source, _TableSource):
                items.append(source.key)
                values.append(source.key)
            else:
                items.extend(source.columns)
                values.extend(source.values or (Fact(),) * len(source.columns))
    return tuple(items), tuple(values)


# --- types, nullable and observed values (ADR 0003, ADR 0007) -------------------------------

_TEXT_RESULT = (
    exp.Upper,
    exp.Lower,
    exp.Trim,
    exp.Substring,
    exp.Replace,
    exp.Pad,
    exp.Initcap,
    exp.ToChar,
    exp.DPipe,
    exp.GroupConcat,
)
_NUMBER_RESULT = (
    exp.Count,
    exp.Sum,
    exp.Avg,
    exp.Mul,
    exp.Div,
    exp.Neg,
    exp.Mod,
    exp.Abs,
    exp.Floor,
    exp.Ceil,
    exp.Length,
    exp.StrPosition,
    exp.ToNumber,
    exp.MonthsBetween,
    exp.Extract,
)
_DATETIME_RESULT = (
    exp.CurrentTimestamp,
    exp.Systimestamp,
    exp.CurrentDate,
    exp.AddMonths,
    exp.LastDay,
    exp.StrToDate,
    exp.DateStrToDate,
    exp.StrToTime,
    exp.DateTrunc,
)
# Each typed parameter takes one type, so a bare column there shows it (ADR 0007).
_NUMBER_PARAMETERS = (
    exp.Mul,
    exp.Div,
    exp.Neg,
    exp.Mod,
    exp.Sum,
    exp.Avg,
    exp.Abs,
    exp.Floor,
    exp.Ceil,
)
_TEXT_PARAMETERS = (
    exp.Upper,
    exp.Lower,
    exp.Trim,
    exp.Substring,
    exp.StrPosition,
    exp.Length,
    exp.Replace,
    exp.Pad,
)
_DATETIME_PARAMETERS = (exp.AddMonths, exp.MonthsBetween, exp.LastDay, exp.DateTrunc)
_SAME_TYPE_FUNCTIONS = (exp.Coalesce, exp.Nvl2, exp.Nullif, exp.Greatest, exp.Least)
_RESULT_TYPES: tuple[tuple[tuple[type[exp.Expr], ...], Type], ...] = (
    (_TEXT_RESULT, "text"),
    (_NUMBER_RESULT, "number"),
    (_DATETIME_RESULT, "datetime"),
    ((exp.Interval,), "interval"),
)


def _unparen(node: exp.Expr) -> exp.Expr:
    while isinstance(node, exp.Paren):
        node = node.this
    return node


def _bare(node: exp.Expr | None) -> exp.Column | None:
    """Return the column that a node is, when it is a bare column of a table and not a pseudocolumn."""
    if node is None:
        return None
    node = _unparen(node)
    if isinstance(node, exp.Alias):
        node = _unparen(node.this)
    if not isinstance(node, exp.Column) or isinstance(node.this, exp.Star):
        return None
    pseudo = not node.this.quoted and node.name.upper() in _PSEUDOCOLUMNS
    return None if pseudo else node


def _fixed_type(node: exp.Expr | None) -> Type | None:  # noqa: C901, PLR0911, PLR0912 # one case per kind of expression
    """Return the type of an expression whose type ichnos can name without knowing any column's type."""
    for classes, result in _RESULT_TYPES:
        if isinstance(node, classes):
            return result
    match node:
        case exp.Paren() | exp.Alias() | exp.Max() | exp.Min():
            return _fixed_type(node.this)
        case exp.Literal():
            return "text" if node.is_string else "number"
        case exp.Column():
            # A sequence's NEXTVAL is the one column-shaped value with a fixed type.
            return (
                "number"
                if node.name.upper() in {"NEXTVAL", "CURRVAL"} and node.table
                else None
            )
        case exp.Add() | exp.Sub():
            return _arithmetic(node)
        case exp.Round() | exp.Trunc():
            unit = node.args.get("decimals")
            if isinstance(unit, exp.Literal):
                return "datetime" if unit.is_string else "number"
            return _fixed_type(node.this)
        case exp.Cast():
            return _cast_type(node.args["to"])
        case _ if isinstance(node, _SAME_TYPE_FUNCTIONS):
            return next(filter(None, map(_fixed_type, _arguments(node))), None)
        case exp.Case() | exp.DecodeCase():
            return next(filter(None, map(_fixed_type, _results(node))), None)
        case exp.Anonymous() if (
            node.name.upper() == "TRUNC" and len(node.expressions) == 1
        ):
            return _fixed_type(node.expressions[0])
        case _:
            return None


def _arithmetic(node: exp.Add | exp.Sub) -> Type | None:
    left, right = _fixed_type(node.this), _fixed_type(node.expression)
    if left is None or right is None:
        return None
    if isinstance(node, exp.Sub) and left == right == "datetime":
        return "number"
    return (
        "datetime" if "datetime" in {left, right} else left if left == right else None
    )


def _cast_type(to: exp.DataType) -> Type | None:
    if to.is_type(*exp.DataType.TEXT_TYPES):
        return "text"
    if to.is_type(*exp.DataType.NUMERIC_TYPES):
        return "number"
    if to.is_type(*exp.DataType.TEMPORAL_TYPES):
        return "datetime"
    return None


def _arguments(node: exp.Expr) -> list[exp.Expr | None]:
    """Return the arguments of a function whose arguments Oracle converts to one type."""
    if isinstance(node, exp.Nvl2):
        return [node.args["true"], node.args.get("false")]
    if isinstance(node, exp.Nullif):
        return [node.this, node.expression]
    return [node.this, *node.expressions]


def _results(node: exp.Case | exp.DecodeCase) -> list[exp.Expr | None]:
    """Return the result branches of a `CASE` or a `DECODE`."""
    if isinstance(node, exp.DecodeCase):
        rest = node.expressions[1:]
        return [*rest[1::2], *rest[len(rest) - len(rest) % 2 :]]
    return [*(i.args["true"] for i in node.args["ifs"]), node.args.get("default")]


def _searches(
    node: exp.Case | exp.DecodeCase,
) -> tuple[exp.Expr | None, list[exp.Expr]]:
    """Return the expression that a simple `CASE` or a `DECODE` compares, and the values it compares it with."""
    if isinstance(node, exp.DecodeCase):
        pairs = (len(node.expressions) - 1) // 2
        return node.expressions[0], node.expressions[1 : 1 + 2 * pairs : 2]
    return node.this, [i.this for i in node.args["ifs"]]


def _observed(node: exp.Expr | None) -> str | None:
    """Return a text or number literal as its SQL literal text."""
    if (
        isinstance(node, exp.Neg)
        and isinstance(node.this, exp.Literal)
        and not node.this.is_string
    ):
        return f"-{node.this.name}"
    if not isinstance(node, exp.Literal):
        return None
    return "'" + node.name.replace("'", "''") + "'" if node.is_string else node.name


def assigned(node: exp.Expr | None) -> Fact:
    """Return what a column learns from a value assigned to it."""
    node = None if node is None else _unparen(node)
    observed = _observed(node)
    generated = (
        isinstance(node, exp.Column)
        and node.name.upper() == "NEXTVAL"
        and bool(node.table)
    ) or (isinstance(node, exp.Anonymous) and node.name.upper() == "SYS_GUID")
    return Fact(
        _fixed_type(node),
        () if observed is None else (observed,),
        isinstance(node, exp.Null),
        generated,
    )


def _child_facts(node: exp.Expr) -> list[tuple[exp.Column, Fact]]:  # noqa: C901, PLR0912 # one case per position
    """Return what each bare column below a node learns from the expressions beside it."""
    facts: list[tuple[exp.Expr | None, Fact]] = []
    match node:
        case (
            exp.EQ()
            | exp.NEQ()
            | exp.GT()
            | exp.GTE()
            | exp.LT()
            | exp.LTE()
            | exp.Like()
        ):
            equality = isinstance(node, exp.EQ | exp.NEQ)
            for column, other in (
                (node.this, node.expression),
                (node.expression, node.this),
            ):
                bare = _bare(column)
                if bare is not None and _bare(other) is None:
                    fact = assigned(other)
                    facts.append(
                        (bare, Fact(fact.type, fact.observed if equality else ()))
                    )
        case exp.Between():
            types = [
                _fixed_type(node.args.get("low")),
                _fixed_type(node.args.get("high")),
            ]
            facts.append((node.this, Fact(next(filter(None, types), None))))
        case exp.In() if not node.args.get("query"):
            values = [assigned(_unparen(v)) for v in node.expressions]
            types = [v.type for v in values if v.type is not None]
            facts.append(
                (
                    node.this,
                    Fact(
                        types[0] if types else None,
                        tuple(o for v in values for o in v.observed),
                    ),
                )
            )
        case exp.Is() if isinstance(node.expression, exp.Null):
            facts.append((node.this, Fact(nullable=True)))
        case exp.Case() | exp.DecodeCase():
            result = next(filter(None, map(_fixed_type, _results(node))), None)
            facts.extend((r, Fact(result)) for r in _results(node))
            searched, searches = _searches(node)
            values = [assigned(s) for s in searches]
            types = [v.type for v in values if v.type is not None]
            observed = tuple(o for v in values for o in v.observed)
            facts.append((searched, Fact(types[0] if types else None, observed)))
        case _ if isinstance(node, _SAME_TYPE_FUNCTIONS):
            arguments = _arguments(node)
            shared = next(filter(None, map(_fixed_type, arguments)), None)
            first_nullable = isinstance(node, exp.Coalesce | exp.Nvl2)
            for index, argument in enumerate(arguments):
                facts.append(
                    (argument, Fact(shared, nullable=first_nullable and index == 0))
                )
            if isinstance(node, exp.Nvl2):
                facts.append((node.this, Fact(nullable=True)))
        case _ if isinstance(node, _NUMBER_PARAMETERS):
            facts.extend(
                (a, Fact("number")) for a in (node.this, node.args.get("expression"))
            )
        case _ if isinstance(node, _TEXT_PARAMETERS):
            facts.append((node.this, Fact("text")))
        case _ if isinstance(node, _DATETIME_PARAMETERS):
            facts.extend(
                (a, Fact("datetime")) for a in (node.this, node.args.get("expression"))
            )
        case exp.Extract():
            facts.append((node.expression, Fact("datetime")))
        case exp.Round() | exp.Trunc():
            unit = node.args.get("decimals")
            if isinstance(unit, exp.Literal):
                facts.append(
                    (node.this, Fact("datetime" if unit.is_string else "number"))
                )
        case _:
            pass
    return [
        (bare, fact)
        for column, fact in facts
        if (bare := _bare(column)) is not None and fact != Fact()
    ]
