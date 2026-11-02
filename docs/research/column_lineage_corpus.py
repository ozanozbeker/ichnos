# /// script
# requires-python = ">=3.13"
# dependencies = ["sqlglot==30.26.0"]
# ///
# ruff: noqa: T201, C901, PLR0912
"""Measure `sqlglot.lineage` on every query of the synthetic Oracle corpus, in four schema modes.

Run it from the repo root with `uv run --no-project --python 3.13 --with sqlglot==30.26.0 python -I docs/research/column_lineage_corpus.py`.
Only the `answer_key` mode, the `wrong` outcome and the `sources` run read `answer_key/schema.sql`.
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import sqlglot
from sqlglot import exp
from sqlglot.lineage import Node, lineage
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.scope import traverse_scope
from sqlglot.schema import MappingSchema

DIALECT = "oracle"
CORPUS = Path("tests/fixtures/oracle_synthetic")
PSEUDOCOLUMNS = {"ROWNUM", "ROWID", "LEVEL", "NEXTVAL", "CURRVAL"}
MODES = ("empty", "query", "corpus", "answer_key")
# An output column with leaves of several kinds takes the kind with the lowest rank.
RANK = {"raises": 0, "placeholder": 1, "wrong": 2, "star": 3, "resolved": 4, "none": 5}

type Mapping = dict[str, dict[str, dict[str, str]]]


def load_statements() -> list[tuple[str, exp.Expr]]:
    """Return every statement in the corpus, labelled by file number and position."""
    out = []
    for path in sorted((CORPUS / "queries").glob("*.sql")):
        stmts = [
            s for s in sqlglot.parse(path.read_text(), read=DIALECT) if s is not None
        ]
        for i, stmt in enumerate(stmts):
            label = path.stem[:3] + ("abcdefgh"[i] if len(stmts) > 1 else "")
            out.append((label, stmt))
    return out


def norm(ident: exp.Identifier | str) -> str:
    """Fold an identifier as Oracle does: unquoted to upper case, quoted as written."""
    if isinstance(ident, str):
        return ident.upper()
    return ident.name if ident.quoted else ident.name.upper()


def table_key(table: exp.Table) -> tuple[str, str]:
    """Return the (owner, name) pair of a table reference, owner empty when absent."""
    db = table.args.get("db")
    return (norm(db) if db else "", norm(table.this))


def answer_key_schema() -> tuple[Mapping, dict[str, str]]:
    """Build the true schema, and the view queries keyed by qualified name."""
    text = (CORPUS / "answer_key" / "schema.sql").read_text()
    mapping: Mapping = defaultdict(dict)
    views: dict[str, str] = {}
    for stmt in sqlglot.parse(text, read=DIALECT):
        if not isinstance(stmt, exp.Create):
            continue
        kind = stmt.args.get("kind", "")
        if kind == "TABLE" and isinstance(stmt.this, exp.Schema):
            owner, name = table_key(stmt.this.this)
            mapping[owner][name] = {
                norm(c.this): c.args["kind"].sql(DIALECT)
                for c in stmt.this.expressions
                if isinstance(c, exp.ColumnDef)
            }
        elif kind == "VIEW" and isinstance(stmt.expression, exp.Query):
            owner, name = table_key(stmt.this)
            mapping[owner][name] = {
                norm(n): "UNKNOWN" for n in stmt.expression.named_selects
            }
            views[f"{owner}.{name}"] = stmt.expression.sql(DIALECT)
    # sqlglot reads CREATE MATERIALIZED VIEW and CREATE PUBLIC SYNONYM as Command nodes.
    for m in re.finditer(
        r"CREATE MATERIALIZED VIEW (\w+)\.(\w+) AS\s+(SELECT.*?);", text, re.DOTALL
    ):
        query = sqlglot.parse_one(m.group(3), read=DIALECT)
        mapping[norm(m.group(1))][norm(m.group(2))] = {
            norm(n): "UNKNOWN" for n in query.named_selects
        }
        views[f"{norm(m.group(1))}.{norm(m.group(2))}"] = m.group(3)
    names = {name for tables in mapping.values() for name in tables}
    for m in re.finditer(r"CREATE PUBLIC SYNONYM (\w+) FOR (\w+)\.(\w+);", text):
        # A synonym named like its table resolves through sqlglot's unqualified lookup already.
        if norm(m.group(1)) not in names:
            mapping["PUBLIC"][norm(m.group(1))] = mapping[norm(m.group(2))][
                norm(m.group(3))
            ]
    # sqlglot keeps `@archive` in the table name, and the linked table has the same columns.
    mapping["SALES"]["ORDERS@ARCHIVE"] = mapping["SALES"]["ORDERS"]
    return dict(mapping), views


def target_of(stmt: exp.Expr) -> exp.Table | None:
    """Return the table a writing query writes."""
    if isinstance(stmt, exp.Insert):
        return stmt.this.this if isinstance(stmt.this, exp.Schema) else stmt.this
    if isinstance(stmt, (exp.Update, exp.Merge, exp.Delete)):
        return stmt.this
    return None


def query_schema(stmt: exp.Expr) -> dict[tuple[str, str], set[str]]:
    """Collect the columns one query attributes to each table, with no other query's help.

    A column counts when its qualifier names a table, or when it is unqualified in a scope
    with one source. Every other column stays out, as ADR-0001 requires.
    """
    tree = normalize_identifiers(stmt.copy(), dialect=DIALECT)
    cols: dict[tuple[str, str], set[str]] = defaultdict(set)
    cte_names = {norm(c.args["alias"].this) for c in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if table.name and not (not table.args.get("db") and table.name in cte_names):
            cols.setdefault(table_key(table), set())
    for scope in traverse_scope(tree):
        named = {k: v for k, v in scope.sources.items() if k}
        if isinstance(scope.expression, exp.Select):
            # Oracle requires a USING column in both sides, so it names a column of each.
            left = (
                [scope.expression.args["from_"].this]
                if scope.expression.args.get("from_")
                else []
            )
            for join in scope.expression.args.get("joins") or []:
                sides = [t for t in [*left, join.this] if isinstance(t, exp.Table)]
                if join.args.get("using") and len(left) == 1 and len(sides) == 2:  # noqa: PLR2004
                    for side in sides:
                        cols[table_key(side)] |= {norm(i) for i in join.args["using"]}
                left.append(join.this)
        for col in scope.columns:
            if col.name in PSEUDOCOLUMNS:
                continue
            source = scope.sources.get(col.table) if col.table else None
            if not col.table and len(named) == 1:
                source = next(iter(named.values()))
            if isinstance(source, exp.Table):
                cols[table_key(source)].add(col.name)
    target = target_of(tree)
    if target is not None:
        key = table_key(target)
        names = {target.alias_or_name, target.name}
        if isinstance(tree.this, exp.Schema):
            cols[key] |= {norm(i) for i in tree.this.expressions}
        for col in tree.find_all(exp.Column):
            if col.table in names and col.name not in PSEUDOCOLUMNS:
                cols[key].add(col.name)
        if isinstance(tree, exp.Update):
            cols[key] |= {eq.this.name for eq in tree.expressions}
        if isinstance(tree, exp.Merge):
            for when in tree.args["whens"].expressions:
                then = when.args.get("then")
                if isinstance(then, exp.Insert):
                    cols[key] |= {c.name for c in then.this.expressions}
                if isinstance(then, exp.Update):
                    cols[key] |= {eq.this.name for eq in then.expressions}
    return cols


def to_mapping(cols: dict[tuple[str, str], set[str]]) -> Mapping:
    """Turn (owner, table) to column sets into the nested dict sqlglot reads."""
    mapping: Mapping = defaultdict(dict)
    for (owner, name), names in cols.items():
        # Unprefixed names go under a placeholder owner, because sqlglot needs one nesting depth.
        mapping[owner or "_NO_OWNER_"][name] = dict.fromkeys(sorted(names), "UNKNOWN")
    return dict(mapping)


def schema_for(mapping: Mapping) -> MappingSchema:
    """Wrap a nested dict of already folded names as a schema."""
    return MappingSchema(mapping, dialect=DIALECT, normalize=False)


def dml_selects(stmt: exp.Expr) -> list[exp.Select]:
    """Rewrite a writing query as `SELECT` queries whose output names are the written columns.

    This is the step ichnos would add: sqlglot's lineage() reads only a query's own SELECT.
    """
    out: list[exp.Select] = []
    if isinstance(stmt, exp.Insert):
        names = (
            [i.name for i in stmt.this.expressions]
            if isinstance(stmt.this, exp.Schema)
            else []
        )
        src = stmt.expression
        if isinstance(src, exp.Values):
            row = src.expressions[0].expressions
            out.append(
                exp.select(*[
                    exp.alias_(v.copy(), n) for v, n in zip(row, names, strict=True)
                ]).from_("dual")
            )
        elif isinstance(src, exp.Select):
            select = src.copy()
            if names:
                select.set(
                    "expressions",
                    [
                        exp.alias_(e.unalias().copy(), n)
                        for e, n in zip(src.expressions, names, strict=True)
                    ],
                )
            out.append(select)
    elif isinstance(stmt, exp.Update):
        projections = [
            exp.alias_(eq.expression.copy(), eq.this.name) for eq in stmt.expressions
        ]
        select = exp.select(*projections).from_(stmt.this.copy())
        if stmt.args.get("where"):
            select.set("where", stmt.args["where"].copy())
        out.append(select)
    elif isinstance(stmt, exp.Merge):
        for when in stmt.args["whens"].expressions:
            then = when.args.get("then")
            if isinstance(then, exp.Insert):
                names = [c.name for c in then.this.expressions]
                values = then.expression.expressions
                projections = [
                    exp.alias_(v.copy(), n) for v, n in zip(values, names, strict=True)
                ]
                out.append(exp.select(*projections).from_(stmt.args["using"].copy()))
            elif isinstance(then, exp.Update):
                projections = [
                    exp.alias_(eq.expression.copy(), eq.this.name)
                    for eq in then.expressions
                ]
                select = exp.select(*projections).from_(stmt.this.copy())
                out.append(
                    select.join(stmt.args["using"].copy(), on=stmt.args["on"].copy())
                )
    return out


def leaf_kind(leaf: Node, truth: MappingSchema) -> str:
    """Classify one leaf of a lineage graph."""
    if isinstance(leaf.expression, exp.Placeholder):
        return "placeholder"
    if leaf.name.endswith("*"):
        return "star"
    if isinstance(leaf.expression, exp.Table):
        column = leaf.name.rsplit(".", 1)[-1].strip('"')
        known = truth.column_names(leaf.expression)
        return "resolved" if column in known else "wrong"
    return "none"


def describe(node: Node, truth: MappingSchema) -> dict:
    """Return the outcome and the leaves of one output column."""
    leaves = [n for n in node.walk() if not n.downstream and n is not node]
    kinds = [leaf_kind(n, truth) for n in leaves] or ["none"]
    names = sorted(
        f"{n.expression.sql(DIALECT) if isinstance(n.expression, exp.Table) else type(n.expression).__name__}:{n.name}"
        for n in leaves
    )
    return {"outcome": min(kinds, key=RANK.__getitem__), "leaves": names}


def run(stmt: exp.Expr, schema: MappingSchema, truth: MappingSchema) -> dict:
    """Run lineage() for every output column of one statement."""
    try:
        result = lineage(None, stmt.copy(), schema, dialect=DIALECT)
    except Exception as e:  # noqa: BLE001 - the error is the measurement
        return {"raises": f"{type(e).__name__}: {str(e).splitlines()[0]}"}
    return {name: describe(node, truth) for name, node in result.items()}


def signature(result: dict) -> str:
    """Serialize a run so two runs compare by value."""
    return json.dumps(result, sort_keys=True)


def minimal_tables(stmt: exp.Expr, full: Mapping, truth: MappingSchema) -> list[str]:
    """Drop answer-key tables one at a time while the lineage result stays the same."""
    baseline = signature(run(stmt, schema_for(full), truth))
    keep = [(o, t) for o, tables in full.items() for t in tables]
    for key in list(keep):
        trial = [k for k in keep if k != key]
        mapping: Mapping = defaultdict(dict)
        for o, t in trial:
            mapping[o][t] = full[o][t]
        if signature(run(stmt, schema_for(dict(mapping)), truth)) == baseline:
            keep = trial
    return [f"{o}.{t}" for o, t in keep]


CLAUSES = {
    "expressions": "select list",
    "where": "WHERE",
    "on": "JOIN ON",
    "using": "JOIN USING",
    "group": "GROUP BY",
    "having": "HAVING",
    "order": "ORDER BY",
    "connect": "CONNECT BY",
    "start": "START WITH",
}


def written_columns(tree: exp.Expr) -> set[int]:
    """Return the ids of column nodes that name a written column, not a read one."""
    ids = set()
    for eq in tree.find_all(exp.EQ):
        if isinstance(eq.parent, exp.Update) and eq.arg_key == "expressions":
            ids.add(id(eq.this))
    for insert in tree.find_all(exp.Insert):
        if isinstance(insert.this, exp.Tuple):
            ids |= {id(c) for c in insert.this.expressions}
    return ids


def clause_of(col: exp.Column) -> str:
    """Name the clause of the nearest query block or writing query that reads a column."""
    node: exp.Expr = col
    while node.parent is not None:
        parent = node.parent
        if isinstance(
            parent,
            (exp.Select, exp.Join, exp.Connect, exp.Update, exp.Merge, exp.Delete),
        ):
            if isinstance(parent, exp.Update) and node.arg_key == "expressions":
                return "UPDATE SET"
            if isinstance(parent, exp.Merge):
                return "MERGE ON" if node.arg_key == "on" else "MERGE WHEN"
            return CLAUSES.get(node.arg_key, node.arg_key)
        if isinstance(parent, exp.Values):
            return "VALUES"
        node = parent
    return "other"


def main() -> None:
    """Print the measurement as JSON lines, then a summary."""
    statements = load_statements()
    full, views = answer_key_schema()
    truth = schema_for(full)
    per_query = {label: query_schema(stmt) for label, stmt in statements}
    corpus_cols: dict[tuple[str, str], set[str]] = defaultdict(set)
    for cols in per_query.values():
        for key, names in cols.items():
            corpus_cols[key] |= names
    names_only = {
        o: {t: dict.fromkeys(c, "UNKNOWN") for t, c in ts.items()}
        for o, ts in full.items()
    }

    records = []
    clause_counts: Counter[str] = Counter()
    for label, stmt in statements:
        schemas = {
            "empty": schema_for({}),
            "query": schema_for(to_mapping(per_query[label])),
            # Every column any query attributes to the tables this query names.
            "corpus": schema_for(
                to_mapping({k: corpus_cols[k] for k in per_query[label]})
            ),
            "answer_key": truth,
        }
        kind = type(stmt).__name__.lower()
        record = {
            "label": label,
            "kind": "report" if kind in {"select", "union"} else kind,
        }
        record["default"] = {mode: run(stmt, s, truth) for mode, s in schemas.items()}
        record["names_only_same"] = signature(
            run(stmt, schema_for(names_only), truth)
        ) == signature(record["default"]["answer_key"])
        selects = dml_selects(stmt)
        if selects:
            record["rewrite"] = {
                mode: [run(sel, s, truth) for sel in selects]
                for mode, s in schemas.items()
            }
        record["needs"] = minimal_tables(stmt, full, truth)
        tree = normalize_identifiers(stmt.copy(), dialect=DIALECT)
        written = written_columns(tree)
        record["clauses"] = Counter(
            clause_of(c)
            for c in tree.find_all(exp.Column)
            if c.name not in PSEUDOCOLUMNS and id(c) not in written
        )
        clause_counts.update(record["clauses"])
        records.append(record)
        print(json.dumps(record, sort_keys=True))

    with_sources = {}
    for label, stmt in statements:
        if label in {"017", "018", "019"}:
            try:
                res = lineage(None, stmt.copy(), truth, sources=views, dialect=DIALECT)
                with_sources[label] = {n: describe(v, truth) for n, v in res.items()}
            except Exception as e:  # noqa: BLE001
                with_sources[label] = {"raises": f"{type(e).__name__}: {e}"}
    print(json.dumps({"sources": with_sources}, sort_keys=True))
    print(json.dumps({"clauses": clause_counts}, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
