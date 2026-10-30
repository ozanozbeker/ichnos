# How sqloxide performs on valid Oracle queries

Answers [issue 18](https://github.com/ozanozbeker/ichnos/issues/18).
It builds on [the parser comparison](oracle-sql-parser.md) and does not repeat it.

## Answer

- **Speed.**
  In 419 ms, sqloxide 0.61.1 parses 4,647 synthetic Oracle statements (3.2 MB).
  Pure-Python sqlglot 30.26.0 needs 2,151 ms for the same statements (5.1x).
  The compiled build, `sqlglot[c]`, needs 544 ms (1.3x).
  The 5x gap in [issue 17](https://github.com/ozanozbeker/ichnos/issues/17) holds only against the pure-Python build.
- **Parse plus resolution.**
  With alias, scope and CTE resolution added, the totals are 588 ms (sqloxide), 3,133 ms (pure sqlglot, 5.3x) and 1,058 ms (`sqlglot[c]`, 1.8x).
- **Work on the raw tree.**
  A resolver over sqloxide's dicts takes 359 code lines.
  The glue over `sqlglot.optimizer.scope` takes 136 lines, on top of the 701 code lines in `scope.py`.
  Both match the generator's answer key on 4,642 of 4,647 statements, and both miss the same five.
  The estimate for a tested first version is 2 to 4 engineer-days.
  Real queries then add rules for as long as new constructs appear.
- **Constructs that raise.**
  Of 360 single-construct probes, sqloxide raises on 61 and sqlglot on 24; 19 raise in both.
  The sets differ.
  sqlglot raises on positional binds (`:1`).
  sqloxide raises on `ORDER SIBLINGS BY`, `KEEP (DENSE_RANK ...)`, `DBMS_LOB.SUBSTR(...)`, `CREATE OR REPLACE FORCE VIEW` and `INSERT ALL`.
- **Constructs that return a wrong tree.**
  sqloxide does so for `SELECT UNIQUE a, b` and `JSON_OBJECT('k' : v)`.
  sqlglot does so for `FOR UPDATE OF a.x` and `IS NAN`, and its `optimizer.scope` lists the self-reference of an Oracle recursive CTE as a base table.
  Both return a wrong tree for `t@lnk.world`, `ONLY (t)` and `1D`.
- **Limits.**
  sqloxide's recursion limit is 50 and its API cannot change it.
  Twenty-five nested derived tables raise.
  A chain of about 25,000 `OR` terms ends the Python process with SIGSEGV.
- **Coverage with both parsers.**
  On the synthetic mix, sqlglot parses 96.4% of statements, sqloxide 96.2% and either one 99.7%.
  The mix is an assumption, so the shares change with how often real queries use each construct.
  Two parsers need two adapters, which are 359 and 136 code lines here.

## Versions and method

All numbers come from runs on 2026-10-30 with Python 3.13.12 on macOS arm64 (Apple M4 Max).

| Package | Version | Notes |
| --- | --- | --- |
| sqloxide | 0.61.1 | Released 2026-04-06. Its `Cargo.lock` pins sqlparser-rs 0.61.0. Wheel 4.9 MB, 14 MB installed. |
| sqlglot | 30.26.0 | Pure-Python wheel, 0.8 MB, 5.3 MB installed. |
| sqlglotc | 30.26.0 | Installed by `sqlglot[c]`. It compiles 104 modules with mypyc, among them the parser, `optimizer.scope` and the Oracle generator. Wheel 33.9 MB on macOS, 130 MB installed with sqlglot. |

Three corpora supply the evidence.
No Oracle server ran any statement.
Syntax comes from the [Oracle Database 19c SQL Language Reference](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/SELECT.html).

- **Synthetic corpus.**
  A seeded generator (seed 20261030) wrote 5,000 statements over a schema of 33 tables, 200 columns and 60 foreign keys in four owners.
  It has 15 statement shapes: ANSI and comma joins with `(+)`, subqueries, CTEs, inline views, analytic functions, set operations, `CONNECT BY`, INSERT, UPDATE, DELETE, MERGE, views, PIVOT and wide reports.
  Size: median 355 characters, p95 3.2 KB, p99 8.7 KB, largest 22.7 KB, total 3.9 MB.
  Style varies: keyword and identifier case, comments, quoted identifiers, `schema.table.column`, reused aliases and alias case that differs between definition and use.
  The generator records an answer key per statement: the base tables, every base-table column reference, every reference to a CTE or derived table, and every equality predicate between two sources.
  4,647 statements parse in both parsers, and all timings use those.
  The mix and the rates of rare constructs are the generator's choice, not a measurement of real code.
  Read the per-construct counts, not the totals.
- **Probes and repros.**
  360 single-construct statements written from the syntax diagrams (6 need Oracle 23ai and 1 is a SQL*Plus terminator), and 83 further minimal repros.
  The repros are the rows in the tables below.
- **Third-party fixtures.**
  913 query-like statements split from the Oracle fixtures of three open-source projects: [sqlfluff 4.4.0](https://github.com/sqlfluff/sqlfluff/tree/0348222a3bcdb0226563f7349c5a39beb0641955/test/fixtures/dialects/oracle) (243), [JSqlParser](https://github.com/JSQLParser/JSqlParser/tree/a0e0861d00b9eda2b1448a83da6827b41d3b8458/src/test/resources/net/sf/jsqlparser/statement/select/oracle-tests) (272) and [antlr/grammars-v4 `sql/plsql`](https://github.com/antlr/grammars-v4/tree/b96e04db9d54bb313e542cc3e6ee913900a21520/sql/plsql) (398).
  These files test syntax edges, so their failure rates are far above production rates.
  They show which constructs fail, not how often.

## Parse speed

Pure-Python sqlglot is 5.1x slower than sqloxide, and `sqlglot[c]` is 1.3x slower.
Total is the time for all 4,647 statements in the fastest of seven passes.
Mean, p50, p95 and p99 are per statement, and each statement counts with its fastest time over the seven passes.

| Parser | Total | Mean | p50 | p95 | p99 | Statements per second | MB per second |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sqloxide 0.61.1 | 419 ms | 87 µs | 46 µs | 321 µs | 666 µs | 11,104 | 7.8 |
| sqloxide, Rust parse only | 210 ms | 44 µs | 24 µs | 171 µs | 318 µs | 22,164 | 15.5 |
| sqlglot 30.26.0, pure Python | 2,151 ms | 440 µs | 247 µs | 1,674 µs | 3,078 µs | 2,161 | 1.5 |
| sqlglot, tokenizer only | 839 ms | 174 µs | 91 µs | 711 µs | 1,357 µs | 5,538 | 3.9 |
| `sqlglot[c]` | 544 ms | 113 µs | 54 µs | 445 µs | 940 µs | 8,537 | 6.0 |
| `sqlglot[c]`, tokenizer only | 167 ms | 34 µs | 19 µs | 129 µs | 268 µs | 27,909 | 19.5 |

- Half of the time in `parse_sql` goes to building Python objects.
  The function in [`lib.rs`](https://github.com/wseaton/sqloxide/blob/v0.61.1/src/lib.rs) calls `Parser::parse_sql` and then `pythonize`.
  The "Rust parse only" row appends a stray `)` to each statement, so the call raises after the parse and before `pythonize`.
- sqloxide trees are larger.
  A statement becomes 976 dict and list nodes on average, against 121 sqlglot nodes.
  Trees for 2,000 statements hold 275 MB, against 112 MB for sqlglot.
  Every identifier carries a `span` of two line and column pairs.
- Time grows linearly with input size in both parsers.
  A select list of 50,000 columns takes 67 ms in sqloxide and 270 ms in pure sqlglot.
  An `IN` list of 100,000 numbers takes 125 ms in sqloxide and 438 ms in pure sqlglot.
  A script of 10,000 statements in one call takes 138 ms in sqloxide and 351 ms in pure sqlglot.
- Neither parser releases the GIL.
  400 large statements take 194 ms on one thread and 198 ms on four with sqloxide, and 950 ms and 980 ms with sqlglot.
  Parallel parsing needs processes.
- Start-up is faster with sqloxide.
  Import plus the first Oracle parse takes 9.5 ms in a fresh process.
  The same step takes 46 ms with pure sqlglot and 76 ms with `sqlglot[c]`.
  A bare interpreter takes 8.8 ms, so the import and first parse add 0.7 ms (sqloxide), 37 ms (pure sqlglot) and 67 ms (`sqlglot[c]`).
- Install size and platforms differ.
  The `sqlglotc` wheel is 2.4 to 6.9 times larger than the sqloxide wheel for Python 3.13 (macOS 33.9 MB against 4.9 MB, Linux x86_64 28.6 MB against 5.5 MB, Windows 11.8 MB against 5.0 MB).
  Both ship wheels for macOS, glibc Linux (x86_64 and aarch64) and Windows x86_64, and neither ships one for musl Linux or Windows arm64.
  The `sqlglotc` Linux wheels need glibc 2.28 (`manylinux_2_28`); the sqloxide Linux wheels need glibc 2.17.
  Without a wheel, installation falls back to the sdist, which needs a Rust toolchain for sqloxide and a C compiler for `sqlglotc`.
  Sources: the PyPI JSON API for [sqloxide](https://pypi.org/pypi/sqloxide/json), [sqlglot](https://pypi.org/pypi/sqlglot/json) and [sqlglotc](https://pypi.org/pypi/sqlglotc/json).

## Work to resolve aliases, scopes, CTEs and unqualified columns

A resolver over sqloxide's raw tree is a small piece of code.
The first version takes 359 code lines and matches `optimizer.scope` on the synthetic corpus.
The open-ended part is the set of Oracle constructs outside that corpus, and the third-party fixtures show some of them.
Code lines exclude blank lines, comments and docstrings.

### The yardstick

[`sqlglot/optimizer/scope.py`](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/optimizer/scope.py) has 1,159 lines, 701 of them code.
`traverse_scope` returns one `Scope` per query block, CTE, derived table and set operation, with `selected_sources` (alias to table or child scope), `columns`, `external_columns` (correlated references) and `unqualified_columns`.
It handles CTEs, derived tables, subqueries, set operations, lateral sources, pivots and semi joins.
It does not do three things the pipeline needs.

- It does not fold identifier case.
  `normalize_identifiers` does, in one call.
- It does not attribute an unqualified column.
  `qualify_columns` does, and it needs a schema.
- It scopes only queries.
  An UPDATE, DELETE, MERGE or INSERT target and its direct columns need code outside `scope.py`.

Both pipelines return the same record and apply one rule to unqualified columns: attribute the column when the scope has exactly one source, and leave it unresolved otherwise.
The record holds the base tables, the column references attributed to base tables, the references to CTEs and derived tables, the equality predicates between two base tables and the number of SELECT blocks.

### The sqloxide resolver

The resolver walks the dicts and tuples that `parse_sql` returns, builds a scope per query block, and resolves names after the walk.
It handles: the 7 statement kinds that hold queries, 3 set expression kinds, 5 table factor kinds, join `ON` and `USING`, and `Subquery`, `Exists` and `InSubquery` expressions.
Every other expression kind is walked generically.
sqlparser-rs 0.61.0 defines 127 statement kinds, 63 expression kinds and 13 table factor kinds, counted from the enums in `src/ast`.
The rules that took code:

1. `pythonize` turns tuple variants into Python tuples (`group_by`, `Number`), so a check for `list` misses them.
2. `{"Identifier": Ident}` means a column in an expression and a name part in an `ObjectName`.
   A skip list of keys (`name`, `data_type`, `alias`, `QualifiedWildcard`, `of`) separates the two.
3. Unquoted identifiers fold to upper case and quoted ones stay as written (`quote_style` is null for unquoted).
4. A database link is part of the identifier, because the Oracle dialect treats `@` as an identifier character.
   `T@LINK` needs stripping before a lookup by table name.
5. A CTE name must be visible in its own body, because Oracle writes recursive subquery factoring without `RECURSIVE`.
6. `(+)` is a wrapper node (`OuterJoin`), and `PRIOR` is a unary node.
7. A name in `ORDER BY` that equals a select-list name is not a column.
8. `ROWNUM`, `LEVEL`, `SYSDATE` and `seq.NEXTVAL` look like columns and need a filter.
9. INSERT, UPDATE, DELETE and MERGE each have their own shape (`TableName`, `ColumnName`, `clauses[].action`).
10. PIVOT and UNPIVOT rename the source, and the `UNPIVOT` value and name are new columns, not references.

### Results

| | sqlglot pipeline | sqloxide resolver |
| --- | --- | --- |
| Code lines | 136, over `scope.py` with 701 | 359 |
| Statements equal to the key (of 4,647) | 4,642 | 4,642 |
| Table sets equal | 4,647 | 4,647 |
| Base-table column references (expected, found, missed, extra) | 69,793, 69,787, 6, 6 | 69,793, 69,787, 6, 6 |
| References to CTEs and derived tables (expected, found) | 18,321, 18,321 | 18,321, 18,321 |
| Join predicates (expected, found) | 6,360, 6,357 | 6,360, 6,357 |
| Parse plus resolve, total | 3,133 ms pure, 1,058 ms compiled | 588 ms |
| Parse plus resolve, mean per statement | 644 µs pure, 211 µs compiled | 121 µs |

Both pipelines miss the same five statements.
Each has an unqualified reference to an outer column inside a correlated subquery.
Oracle binds the name outward when the inner source has no such column, and the single-source rule attributes it to the inner source instead.
A schema is the only fix.
Across the corpus, 4,272 references (5.8% of base-table references) are unqualified in a scope with several sources.
Neither pipeline attributes them.
The generator sets that share, so it is not a measurement.

### Where the two pipelines differ

On the 543 third-party statements that both parsers read, 529 run through both pipelines.
The other 14 raise `OptimizeError: Alias already used` in `Scope.selected_sources` because they join one table twice without aliases, such as `dual CROSS JOIN dual`.
The pipelines agree on 489 of the 529 (92.4%).
The 40 differences by cause:

| Count | Cause |
| --- | --- |
| 14 | sqlglot returns `TABLE(...)`, `XMLTABLE` and `JSON_TABLE` sources as a `Table` with an empty name, and the `COLUMNS` entries look like columns. |
| 7 | The sqloxide resolver reads the element-name argument of `XMLELEMENT` as a column. |
| 6 | `optimizer.scope` counts the self-reference in an Oracle recursive CTE as a base table, because it handles self-reference only when `RECURSIVE` is present. |
| 4 | PIVOT and UNPIVOT: alias handling, and a subquery in the `IN` list. |
| 3 | `DELETE t WHERE ...` without `FROM` (the glue misses the target). |
| 2 | sqlglot drops a column in `ORDER BY` or `GROUP BY` when a select-list output has the same name. |
| 1 | The sqloxide resolver does not treat `CROSS APPLY` as lateral, so the correlated reference is lost. |
| 1 | `JSON_OBJECT('k' : v)` is a wrong tree in sqloxide (see below), so the column is lost. |
| 2 | Other (a function named `SET`). |

The sqloxide side accounts for 9 of the 40 (XML names 7, `APPLY` 1, `JSON_OBJECT` 1).
The sqlglot side accounts for 22 (table-function sources 14, recursive CTE 6, name filter 2), and the sqlglot glue for 3.
The 4 PIVOT cases and the 2 others differ in how each side reads the construct.
sqlglot's tree has an `XMLElement` node that stores the name apart from the argument list.
The raw tree has a generic function call, so the resolver needs a list of such functions.

### Estimate

The estimate for a tested first version of the sqloxide resolver is 2 to 4 engineer-days.
The basis is the 359 code lines, about a dozen node shapes to read from dumps, and one corpus with answer keys to test against.
The generator and its schema have 1,119 lines, and the resolver file has 414.
Four costs recur after the first version.

- **Rules from real queries.**
  Each new corpus adds a few rules.
  The 529 third-party statements exposed three gaps: the element-name argument of `XMLELEMENT`, `CROSS APPLY` as a lateral join, and a subquery in a `PIVOT ... IN` list.
- **Version drift.**
  The raw tree has no schema checks, because the stub `sqloxide/__init__.pyi` has 38 `TypedDict` classes and every other node is `dict[str, Any]`.
  Between sqlparser-rs 0.61.0 and 0.63.0, `Statement` grows from 127 to 140 kinds, `JoinOperator` from 18 to 21 and `TableFactor` from 13 to 14 (`UnpivotExpr`).
  The resolver treats an unknown table factor as a source with no columns, so a new kind yields fewer column references and no error.
- **Statement splitting.**
  `parse_sql` raises for a whole script when one statement is unsupported, and returns nothing.
  The caller must split scripts first.
  The splitter in the harness has 131 lines, and has to handle `/` terminators, `q'[...]'` strings and PL/SQL blocks.
  sqlglot's tokenizer (`Dialect.tokenize`) gives the semicolon positions.
- **What is out of scope.**
  The estimate excludes column lineage through CTE and derived-table outputs (`sqlglot.lineage` does it separately) and attribution of ambiguous unqualified columns from inferred schemas.

## Constructs where each parser raises or returns a wrong tree

Each row is a minimal repro of valid Oracle SQL.
A "Command" result means sqlglot returns an opaque `exp.Command` node that holds the text and no tables or columns.

### sqloxide raises, sqlglot parses

| Construct | Repro | Oracle source |
| --- | --- | --- |
| `ORDER SIBLINGS BY` | `... CONNECT BY PRIOR id = p ORDER SIBLINGS BY n` | [Hierarchical queries](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Hierarchical-Queries.html) |
| `KEEP (DENSE_RANK ...)` | `MAX(x) KEEP (DENSE_RANK LAST ORDER BY d)` | [FIRST](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/FIRST.html) |
| Package function named like a keyword | `DBMS_LOB.SUBSTR(c, 4000, 1)`; `pkg.TRIM`, `pkg.CEIL` and `pkg.FLOOR` also raise | |
| View options and `EXPLAIN PLAN` | `CREATE OR REPLACE FORCE VIEW v AS ...`; `... WITH READ ONLY`. `EDITIONABLE`, `CREATE MATERIALIZED VIEW ... BUILD IMMEDIATE ...` and `EXPLAIN PLAN FOR ...` give a Command in sqlglot. | [CREATE VIEW](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/CREATE-VIEW.html) |
| Multitable insert, `RETURNING INTO`, insert alias | `INSERT ALL INTO t (a) VALUES (b.a) SELECT ...`; `... RETURNING a INTO :out`; `INSERT INTO t a (c) VALUES (1)` (fixed in sqlparser-rs 0.62) | [INSERT](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/INSERT.html) |
| Table clauses | `t SAMPLE (10) a`; `t PARTITION (p1) a`; `t AS OF SCN 123 a`; `t AS OF TIMESTAMP ... a` | [SELECT](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/SELECT.html) |
| Recursive CTE clauses | `WITH w (...) AS (...) SEARCH DEPTH FIRST BY i SET o SELECT ...` | [SELECT](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/SELECT.html) |
| Lock wait | `FOR UPDATE WAIT 5` | [SELECT](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/SELECT.html) |
| `HAVING` before `GROUP BY` | `SELECT g FROM t HAVING COUNT(*) > 1 GROUP BY g` | [SELECT](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/SELECT.html) |
| Operators and predicates | `x ^= 1`; `x = ANY (1, 2, 3)`; `x IS JSON` | [Comparison conditions](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Comparison-Conditions.html) |
| Casts and constructors | `CAST(x AS INTERVAL DAY TO SECOND)`; `TREAT(x AS t)`; `TO_NUMBER(x DEFAULT 0 ON CONVERSION ERROR)`; `CURSOR(SELECT ...)`; `CAST(MULTISET(SELECT ...) AS t)`; `XMLATTRIBUTES(c AS "x")` | |
| `JSON_OBJECT` key form | `JSON_OBJECT(KEY 'k' VALUE v)` | [JSON_OBJECT](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/JSON_OBJECT.html) |
| Unreserved keyword as table alias | `FROM t a, u format`; `settings`, `sort` and `open` also raise | [Reserved words](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Oracle-SQL-Reserved-Words.html) |

### sqlglot raises, sqloxide parses

| Construct | Repro | Cause or source |
| --- | --- | --- |
| Positional bind | `WHERE a.y = :1` | `COLON_PLACEHOLDER_TOKENS` in [`parser.py`](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/parser.py) holds identifier tokens only. The Snowflake parser adds `NUMBER`, the Oracle parser does not. [python-oracledb](https://python-oracledb.readthedocs.io/en/latest/user_guide/bind.html) binds by position with `:1`. |
| `MERGE` with `DELETE WHERE` | `... WHEN MATCHED THEN UPDATE SET d.x = s.x DELETE WHERE (d.y = 1)` | [MERGE](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/MERGE.html) |
| UPDATE of an inline view | `UPDATE (SELECT a.x ax, b.x bx FROM t a JOIN u b ON a.id = b.id) SET ax = bx` | [UPDATE](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/UPDATE.html) |
| JSON function clause | `JSON_QUERY(j, '$.a' RETURNING VARCHAR2(100))` | |

Two small subclasses (five lines) fix the positional bind in pure-Python sqlglot.
The parser subclass sets `COLON_PLACEHOLDER_TOKENS = OracleParser.ID_VAR_TOKENS | {TokenType.NUMBER}`, and the dialect subclass sets `Parser` to it.
With `sqlglot[c]` the same code raises `TypeError: interpreted classes cannot inherit from compiled`.
The compiled build needs an upstream change, or a rewrite of `:1` before parsing.

### Both raise

`PIVOT XML`; a partitioned outer join (`t PARTITION BY (c) RIGHT OUTER JOIN u ON ...`); `MODEL`; `WITH FUNCTION`; `x MEMBER OF c`; `c IS A SET`; `INSERT INTO (SELECT ...) VALUES ...` (fixed in sqlparser-rs 0.62, not yet in sqloxide); `LOG ERRORS INTO`; a quoted name followed by a database link (`"S"."T"@lnk`); `limit`, `qualify` and `top` as table aliases; `TOP` as a column name.
A `/` terminator on its own line raises too.
It is SQL*Plus syntax, not SQL, but script files hold it often.

### Wrong tree without an error

| Construct | sqloxide | sqlglot |
| --- | --- | --- |
| `SELECT UNIQUE a, b FROM t` | Column `UNIQUE` with alias `a`; `a` is lost. Oracle documents `UNIQUE` as a synonym of `DISTINCT` ([SELECT](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/SELECT.html)). | Correct |
| `JSON_OBJECT('k' : v)` | A `JsonAccess` node with `v` as a path key, so the column is lost. | Correct |
| `FOR UPDATE OF a.x` | Correct (`locks[].of`) | Table `x` in schema `a` |
| `IS NAN`, `IS INFINITE` | Raises | Column `NAN` |
| `t PARTITION (p1) a` | Raises | Column `p1` |
| `t@lnk.world` | Table `world` in schema `t@lnk` | Same |
| `ONLY (t)` | Table `ONLY` with argument `t` | Column `t`, no table |
| `1D`, `2F` (binary float and double literals) | Number with alias `D` or `F` | Same |
| `a.addr.city` | Keeps the three parts; the resolver chooses | `Column(table=addr, db=a)`: the qualifier is the middle part |
| Oracle recursive CTE in `optimizer.scope` | | The CTE name appears as a base table |

The Oracle dialect in sqlparser-rs makes `@` an identifier character ([`oracle.rs`](https://github.com/apache/datafusion-sqlparser-rs/blob/v0.61.0/src/dialect/oracle.rs)).
That is why `t@lnk` is one name and `t@lnk.world` splits at the dot.

### Identifiers that Oracle does not reserve

Oracle reserves 110 words ([reserved words](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Oracle-SQL-Reserved-Words.html)).
Other keywords "are not reserved" ([keywords](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Oracle-SQL-Keywords.html)).
The test used the 1,019 keywords from the two parsers' lists that are not among the 110.

| Position | sqloxide raises on | sqlglot raises on |
| --- | --- | --- |
| Column name | 4: `CONNECT_BY_ROOT`, `INTERVAL`, `TOP`, `TRIM` | 31, including `TOP`, `CASE`, `JOIN`, `INNER`, `OUTER`, `USING` |
| Implicit column alias | 24, including `END`, `LIMIT`, `OFFSET`, `SORT`, `TOP`, `XOR` | 24, including `FETCH`, `JOIN`, `QUALIFY`, `USING`, `XOR` |
| Table alias | 20, including `FORMAT`, `LIMIT`, `OPEN`, `QUALIFY`, `SETTINGS`, `SORT`, `TOP` | 20, including `LIMIT`, `QUALIFY`, `TOP` |
| CTE name | 2 | 23 |

Neither parser raises after `AS` or on a qualified column (`a.limit`).
Oracle reserves some of these words in some positions (`V$RESERVED_WORDS`), so the counts are upper bounds.

### Totals by corpus

On the synthetic corpus, sqloxide raises on 188 of 5,000 statements and sqlglot on 179.
The causes in sqloxide are `ORDER SIBLINGS BY` (30 of 30 statements that use it), `KEEP` (29 of 29), `DBMS_LOB.SUBSTR` (78 of 78), `FORCE` and `WITH READ ONLY` views (44 of 127 views), and `SELECT UNIQUE` (6 of 6).
All six `SELECT UNIQUE` statements use qualified columns, which raise.
A list of plain column names (`SELECT UNIQUE a, b`) parses with the wrong tree instead.
In sqlglot, 178 of the 180 statements with a positional bind raise, and so does one statement with a quoted name and a database link.
In the third-party fixtures, sqlglot fails on 208 of 913 statements (176 exceptions and 32 Command results) and sqloxide on 347.
Both fail on 185, only sqloxide on 162 and only sqlglot on 23.
Pure and compiled sqlglot give the same status for all 913.

## Size and nesting limits

The inputs are generated strings run in a fresh process each.
Cells show the largest size tested that parsed, and the smallest size tested that raised.
sqlparser-rs counts depth in four functions (`parse_statement`, `parse_query`, `parse_subexpr`, `parse_table_factor`) against `DEFAULT_REMAINING_DEPTH = 50` ([`parser/mod.rs`](https://github.com/apache/datafusion-sqlparser-rs/blob/v0.61.0/src/parser/mod.rs#L209)).
`Parser::with_recursion_limit` exists, and sqloxide's `lib.rs` calls `Parser::parse_sql`, so no option reaches it.
Pure sqlglot uses Python recursion, so `sys.setrecursionlimit` raises its limit.

| Input, n levels or terms | sqloxide | pure sqlglot | `sqlglot[c]` |
| --- | --- | --- | --- |
| Derived tables, `FROM (SELECT x FROM (... t))` | 20 parses, 25 raises | 100 parses, 250 `RecursionError` | 1,000 parses |
| Nested `IN (SELECT ... IN (SELECT ...))` | 20 parses, 25 raises | 50 parses, 100 `RecursionError` | 250 parses |
| Parentheses, or `NVL(NVL(...))` | 40 parses, 49 or 50 raises | 40 parses, 49 or 50 `RecursionError` | 1,000 parses |
| Nested `CASE` | 25 parses, 50 raises | 50 parses, 100 `RecursionError` | 250 parses |
| `a OR b OR ...`, or `a + b + ...` | 24,767 parses, 25,157 ends the process with SIGSEGV | 100,000 parses | 100,000 parses |

- The error text for 50 nested `CASE` levels in sqloxide is `Expected: end of statement`, not a recursion message.
- The SIGSEGV is a return code of -11 for the Python process on macOS arm64 with an 8 MB main-thread stack.
  The threshold depends on the stack size.
- `sqlglot[c]` raised no `RecursionError` at any tested size, so a deeper input could overflow the C stack.
  That was not tested.
- Input of 10 MB in a string literal, 100,000 items in an `IN` list and 10,000 statements in a script parse in both parsers.

## Release state

- sqloxide 0.61.1 is the latest release (2026-04-06).
  The repository's last commit is 2026-04-09.
  It pins sqlparser-rs 0.61.0 (2026-02-06).
  Releases 0.62.0 (2026-05-02) and 0.63.0 (2026-09-08) exist upstream.
- sqlparser-rs introduced its Oracle dialect in [0.60.0](https://github.com/apache/datafusion-sqlparser-rs/blob/v0.63.0/changelog/0.60.0.md) (2025-12-02).
  0.61.0 added MERGE predicates, `||` precedence, quote-delimited strings, optimizer hints and hierarchical queries.
  0.62.0 added the INSERT table alias and `INSERT INTO (<sub-query>)`.
- The 0.63.0 source of `src/parser/mod.rs` has no `SIBLINGS`, `KEEP`, `DENSE_RANK`, `EDITIONABLE` or `BUILD`.
  A sqloxide release that tracks 0.63.0 would therefore keep the first failures in the "sqloxide raises" table.
  This was read from the source and not run, because sqloxide has no release for 0.62 or 0.63.
- sqlglot 30.26.0 was released on 2026-10-29.

## Limits of this note

- No Oracle server checked any statement, so validity rests on the SQL Language Reference.
- The synthetic mix is the generator's.
  The per-construct counts hold, and the totals depend on the mix.
- The third-party fixtures test syntax edges and several are not queries a person would write.
- Everything ran on one machine with Python 3.13.12.
  Linux and Windows wheels, and `sqlglotc` outside macOS, were not run.
- The estimate covers the resolver on the constructs in the two corpora.
- The harness (generator, probes, both pipelines, splitter) is not committed.
  It has 77 Python files and about 5,500 lines, most of them one-off drivers.
  The generator and the answer-key scorer are the part to reuse once issue 7 produces the in-repo corpus.

## Reproduce

Install the pure-Python build with `uv pip install sqloxide==0.61.1 sqlglot==30.26.0`, and the compiled one with `uv pip install sqloxide==0.61.1 "sqlglot[c]==30.26.0"` in a second environment.
The timing loop is:

```python
import sqlglot
from sqloxide import parse_sql

for sql in statements:
    sqlglot.parse(sql, read="oracle")
    parse_sql(sql, "oracle")
```
