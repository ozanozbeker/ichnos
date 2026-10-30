# Which SQL parser handles Oracle queries

Answers [issue 6](https://github.com/ozanozbeker/ichnos/issues/6).

## Recommendation

Use sqlglot with `read="oracle"`.
It is the only candidate that parses every Oracle construct in the corpus except Oracle `MODEL` and PL/SQL, marks the `(+)` operator on the column node, and recovers a partial tree from invalid SQL.
It is one pure-Python wheel with no runtime dependencies, so `uvx ichnos` needs no extra step.
Tables, aliases and columns come from `find_all` on the tree, and `sqlglot.optimizer.scope` resolves aliases, CTEs and correlated subqueries.

sqloxide is the second choice.
It is 5x faster and its Oracle dialect covers `(+)`, `CONNECT BY` and `MERGE`.
It fails on `ORDER SIBLINGS BY`, raises on any invalid SQL, and returns a raw JSON tree with no alias or scope helpers.

## Versions tested

All results come from experiments run on 2026-10-30 with Python 3.13.12 on macOS arm64.

| Package | Version | Released | Wheel | Runtime dependencies |
| --- | --- | --- | --- | --- |
| sqlglot | 30.26.0 | 2026-10-29 | pure Python (`py3-none-any`) | none |
| sqlglotc | 30.26.0 | 2026-10-29 | compiled, optional (`sqlglot[c]`) | `sqlglot` |
| sqloxide | 0.61.1 | 2026-04-06 | compiled, 49 files on PyPI | none |
| sqlparse | 0.6.0 | 2026-08-13 | pure Python | none |
| sql-metadata | 3.0.1 | 2026-06-30 | pure Python | `sqlglot>=30.12.0,<31` |
| sqlfluff | 4.4.0 | 2026-10-02 | pure Python | 11 packages, including `Jinja2`, `click` and `diff-cover` |

Sources: the [PyPI JSON API](https://pypi.org/pypi/sqlglot/json) for each package.
sqlglot's README states "no-dependency SQL parser" and describes `sqlglot[c]` as a mypyc build that is 3-5x faster.
The `[rs]` extra is deprecated in favor of `sqlglotc`; importing it warns `sqlglot[rs] is deprecated and no longer compatible with sqlglot`.
This run used the pure Python build, so `sqlglotc` behavior is untested.

## Oracle support by parser

The corpus is `corpus.py` in the experiment directory: 25 short queries, one construct each.
"Parses" means the parser returned a tree without raising.

| Construct | sqlglot | sqloxide (`oracle`) | sqlparse | sql-metadata | sqlfluff (`oracle`) |
| --- | --- | --- | --- | --- | --- |
| `(+)` outer join | Parses; `Column.join_mark=True` | Parses; `OuterJoin` expression wraps the column | Tokenizes; no semantics | Tables found; the join column is lost from `join` | Parses |
| `CONNECT BY` / `START WITH` | Parses; `Connect` node, `PRIOR` kept | Parses; `ConnectBy` and `StartWith` | Tokenizes; `CTE` misdetected | Tables and columns found | Parses |
| `ORDER SIBLINGS BY` | Parses | Raises | Tokenizes | Tables found | Parses |
| `MERGE` | Parses; `Merge` node | Parses; `Merge` statement | Type `MERGE` | Tables found; aliases partly lost | Parses |
| `PIVOT` / `UNPIVOT` | Parses; `Pivot` node | Parses | Tokenizes | Tables found; columns include `*` | Parses |
| Analytic functions | Parses; `Window` node | Parses | Tokenizes | Columns found | Parses |
| CTEs | Parses; scope resolves CTE names | Parses | Tokenizes | Real tables only, CTE names removed | Parses |
| Subqueries | Parses; scope reports correlated columns | Parses | Tokenizes | Tables and aliases found | Parses |
| `hr.t@dblink` | Parses; `@dblink` stays in the table name | Parses; same | Tokenizes | Drops `@dblink` | not run |
| `FETCH FIRST`, `ROWNUM`, hints, bind variables | Parses | Parses | Tokenizes | Parses | not run |
| `CROSS APPLY` | Parses | Parses | Tokenizes | Parses | Fails (`PRS`) |
| `MODEL` clause | Raises | Raises | Tokenizes | Wrong: treats `MODEL` as an alias | Fails (`PRS`) |
| PL/SQL block (`BEGIN ... END;`) | Raises (`Block` node only with `IGNORE`) | Raises | not run | Raises | Parses |

sqlparse and sql-metadata are not Oracle parsers.
sqlparse has no dialects and returns a flat token list with grouping, so it cannot tell a join predicate from any other comparison without custom code.
sql-metadata 3.0.1 is a wrapper over sqlglot (its README: "Uses `sqlglot` to parse SQL queries"), so it inherits sqlglot's grammar and hides the tree.
It returns the flat lists `tables`, `tables_aliases` and `columns`, and no join predicate pairs.

Evidence for sqloxide's Oracle dialect: `OracleDialect` in [`src/dialect/oracle.rs`](https://github.com/apache/datafusion-sqlparser-rs/blob/main/src/dialect/oracle.rs) of sqlparser-rs sets `supports_outer_join_operator`, `supports_connect_by` and `supports_match_recognize` to true.
sqloxide 0.61.1 pins `sqlparser = 0.61`, per its [`Cargo.toml`](https://github.com/wseaton/sqloxide/blob/main/Cargo.toml).

## How each parser exposes the inputs ichnos needs

### sqlglot

- Tables: `tree.find_all(exp.Table)` gives `name`, `alias` and `db`.
  A database link stays inside `name` (`departments@dblink`).
- Columns: `tree.find_all(exp.Column)` gives `name` and `table` (the qualifier or alias).
  An unqualified column has an empty `table`.
- Join predicates: an ANSI join has `Join.args["on"]`.
  An Oracle comma join has no `Join.on`, so the predicates are `exp.EQ` nodes in `Where`.
  A `(+)` side is `Column.args["join_mark"]`.
- Scope: `traverse_scope(tree)` yields one scope per `SELECT`, with `sources` (alias to table or CTE scope), `unqualified_columns` and `external_columns`.
  `external_columns` lists the outer columns that a correlated subquery uses (for example `e.id`).
- `Merge` is not a `Select`, so `traverse_scope` yields only the `USING` subquery.
  The merge target, `ON` condition and `WHEN` actions need direct tree walks (`Merge.this`, `on`, `whens`).
- `JOIN ... USING (id)` and `NATURAL JOIN` produce a `Join` with no `on` and no column nodes.
  A schema-free parser cannot name the join columns of a natural join.
- `qualify()` upper-cases Oracle identifiers.
  Without a schema, it cannot attribute an unqualified column to a table when the query joins two tables (`validate_qualify_columns=True` raises `Column 'ENAME' could not be resolved`).

### sqloxide

- Returns `list[dict]` that mirrors sqlparser-rs enums, with a `span` on every identifier (line and column).
  The spans give source positions for evidence.
- `extract_relations` returns table names but not aliases.
  Aliases come from `Table.alias.name.value` in the tree.
- `(+)` is `{"OuterJoin": <expr>}` inside a `BinaryOp`.
  The ANSI join predicate is `joins[].join_operator.Join.On`.
- No scope resolution.
  ichnos would write its own alias, CTE and correlated-column logic over untyped dicts.

### sqlparse and sql-metadata

- sqlparse groups tokens into `Identifier`, `IdentifierList`, `Where` and `Comparison`.
  `get_real_name()` and `get_alias()` work on simple identifiers.
  Subqueries, CTEs and `MERGE` need manual recursion.
- sql-metadata returns `tables`, `tables_aliases`, `columns` and `columns_dict` (keys such as `join`, `where`, `select`).
  It qualifies a column with its table when the alias is known.
  It drops the `(+)` marker, `@dblink` and `PIVOT` output columns.

## Behavior on invalid or partial SQL

| Input | sqlglot (default) | sqlglot (`error_level=IGNORE`) | sqloxide | sqlparse | sql-metadata |
| --- | --- | --- | --- | --- | --- |
| `... WHERE` (trailing) | `ParseError` with line and column | Tree; table `t` found | `ParserError` | Tokens | Tables and columns found |
| `... ON a = b AND` | `ParseError` | Tree; `t1`, `t2` found | `ParserError` | Tokens | Tables and columns found |
| `FROM (SELECT b FROM t2` (unbalanced) | `ParseError` | Tree; closes the parenthesis, `t2` found | `ParserError` | Tokens | Tables found |
| `SELEC a FROM t` | `ParseError` | Wrong tree (`SELEC AS a`), no tables | `ParserError` | Type `UNKNOWN` | Raises |
| `a; b;` (two statements) | `parse` returns 2 trees | n/a | 2 statements | 2 statements | First statement only |

sqlglot's `ErrorLevel.IGNORE` and `WARN` (defined in `sqlglot/errors.py`) build a best-effort tree and keep the tables, which fits the ichnos goal of reading messy query files.
`WARN` logs each error to the `sqlglot` logger.
The recovered tree is silently wrong for a mistyped keyword, so ichnos must treat any recovered query as lower confidence.
The `ParseError` message carries line and column (for example `Line: 1, Col: 24`), which ichnos can attach to evidence.

sqloxide raises on all five and returns no partial tree.
sqlparse and sql-metadata never reject input, so they report tables from SQL that is not valid.

sqlfluff marks the failing region as an `unparsable` segment and keeps the rest of the tree (`... WHERE`: table `t` found).
It raises `AssertionError: Root variant not successfully parsed` on the unbalanced input.
It is a linter with 11 runtime dependencies, which is heavy for a parsing step, and its tree is a concrete syntax tree without alias or scope helpers.

## Speed

300 parses of the `subquery` case, mean per parse: sqloxide 0.05 ms, sqlglot (pure Python) 0.27 ms, sqlparse 0.92 ms.
A folder of thousands of queries parses in seconds with any of them.
Speed does not decide the choice.

## Gaps to plan for

- Oracle `MODEL` and PL/SQL blocks do not parse in sqlglot.
  `IGNORE` returns a partial tree for `MODEL`; ichnos should flag the query as partly read.
- A schema-free parse cannot attribute an unqualified column when a query joins several tables.
  ichnos must record these as ambiguous, whatever parser it uses.
- sqlglot releases often (30.26.0 appeared the day before this run) and changes its tree between minor versions.
  sql-metadata 3.0.1 pins `sqlglot<31`.
  ichnos should pin a compatible range in its own dependencies and keep a regression corpus.
- The experiments use short single-construct queries.
  Real Oracle queries are not available yet, so the results must be rerun on the synthetic corpus once it exists.

## Not covered

- Commercial parsers (for example General SQL Parser) and parsers in other languages need a separate executable or runtime.
  They fail the `uvx` constraint.
- `sqlglotc` behavior, and sqlglot's `lineage` and `optimizer` modules beyond scope analysis, were not tested.
