# Prior art for inferring schemas from query logs

Answers [issue 19](https://github.com/ozanozbeker/ichnos/issues/19).

## Summary

No source in this review returns a schema inferred from query text alone.
The join-mining tools and papers start from a known schema or catalog, from table data, or from fully qualified names.
The lineage tools return lineage, not a schema.
sqllineage comes closest: it collects which columns each table has from the column lineage of other statements and uses them to resolve unqualified references.

- **Join graphs from logs.**
  Uber Queryparser, OpenMetadata, Google Knowledge Catalog and Snowflake Semantic View Autopilot read joins between columns of different tables from queries.
  Petit et al. (ICDE 1996) do the same for database reverse engineering, then test each candidate against table data.
  Two 2026 papers (Tursio, Nexus) use query history as feedback on joins inferred from the database or its metadata.
  No source takes the direction of a relationship from the query text.
- **Keys.**
  The key signals from queries are weak: a column in a join predicate is a candidate key, and a column used under `sum` or `avg` is unlikely to be one (Elmeleegy et al., 2008).
  The other key evidence comes from declared constraints (Petit et al.) or from data (Snowflake, Tursio).
- **Lineage tools.**
  sqlglot, sqllineage, OpenLineage SQL and DataHub map output columns to source columns.
  Given an unqualified column in a multi-table query and no schema, they leave it unattributed, keep a set of candidate tables, or raise.
  OpenLineage SQL attributes it to the first table when the query uses `JOIN ... ON`.
- **Confidence.**
  Among the tools, only DataHub reports a score, and the score measures how many tables have a registered schema, not how strong the evidence is.
  OpenMetadata counts joins per column pair per day.
  The other tools report none; Uber reviewed its output by hand.
- **sqlglot lineage.**
  The `schema` argument of `lineage()` is required since 30.22.0.
  With an empty schema, `lineage()` attributes an unqualified column only when its scope has one named source.
  Otherwise it returns a `Placeholder` leaf, or raises `OptimizeError` when the column is inside a scalar or `IN` subquery.
- **Oracle.**
  OpenLineage SQL has no Oracle dialect and fails to parse `(+)`.
  OpenMetadata's join scan does not read `WHERE` predicates, so a comma join records no join.
  DataHub records a comma join as a table pair with no columns.

## Sources and versions

Probes ran on 2026-10-30 with Python 3.13.12 on macOS arm64.
A probe is one query run through one tool.
Source files were read at the tag or commit listed.
The probe scripts are not committed, and each probe query appears in a table below.

| Source | Version or commit | Read |
| --- | --- | --- |
| sqlglot | 30.26.0 (tag `v30.26.0`, released 2026-10-29); 30.12.0 for one comparison | `lineage.py`, `optimizer/qualify_columns.py`, `optimizer/resolver.py`, `CHANGELOG.md`, PR 8552 |
| sqllineage | 1.5.9 (tag `v1.5.9`, released 2026-09-05) | `core/models.py`, `core/holders.py` |
| openlineage-sql | 1.55.0 (released 2026-10-29); source at commit `bad2d7f` | `visitor.rs`, `dialect.rs`, `INTERFACE.md`, README |
| acryl-datahub | 1.7.0.19 (released 2026-10-30, pins sqlglot 30.12.0); source at commit `9ad8572` | `sqlglot_lineage.py`, SQL parsing docs |
| OpenMetadata | commit `6cea3f6` (2026-10-30) | `lineage/parser.py`, `bulksink/metadata_usage.py`, `table.json`, usage ingestion docs |
| Uber Queryparser | commit `6ae2e94` (2021-12-18) | README, blog post of 2018-03-01 |
| Google Knowledge Catalog | docs page, last updated 2026-10-26 | [View data relationships](https://docs.cloud.google.com/dataplex/docs/data-relationships) |
| Snowflake Semantic View Autopilot | docs page | [Semantic View Autopilot](https://docs.snowflake.com/en/user-guide/views-semantic/autopilot) |

## Tools

| Tool | Evidence it reads | Unqualified column, several tables, no schema | Confidence |
| --- | --- | --- | --- |
| sqlglot `lineage` | Output column to source columns of one query | `Placeholder` leaf; raises inside a subquery | None |
| sqllineage | Column lineage of statements that write a table | Keeps candidate tables; resolves from other statements or a metadata provider | None |
| openlineage-sql | Table and column lineage | `origin: None`; the first table when the query uses `JOIN ... ON` | None |
| DataHub `sqlglot_lineage` | Column lineage; joins from `ON` clauses | Empty `upstreams`; table lineage is still returned | `debug_info.confidence`, from schema coverage |
| OpenMetadata usage ingestion | Comparisons between dotted names in a query log | Comparison dropped | `joinCount` per column pair per day |
| Uber Queryparser | Columns compared for equality in a query stream | Resolved against a catalog | None; output reviewed by hand |
| Google Knowledge Catalog | Sampled BigQuery query history | Not documented | Not documented |
| Snowflake Semantic View Autopilot | Example SQL and query history | Not documented | Not documented |

### sqlglot lineage

`sqlglot.lineage.lineage(column, sql, schema, ...)` returns a `Node` tree from an output column to its source columns.
It calls `qualify` with `validate_qualify_columns=False`, so a column that stays unqualified does not fail validation.
Probes use `read="oracle"` and an empty schema unless stated.

| Query | Result |
| --- | --- |
| `SELECT empno, ename FROM emp` | Leaves `EMP.EMPNO` and `EMP.ENAME` |
| `SELECT e.ename FROM emp e` | Leaf `E.ENAME` on table `EMP E` |
| `SELECT ename, dname FROM emp e, dept d WHERE e.deptno = d.deptno(+)` | `Placeholder` leaves with no table |
| `WITH x AS (SELECT empno, sal FROM emp) SELECT sal FROM x` | `X.SAL`, then `EMP.SAL` |
| `SELECT ename FROM v_emp` | Leaf `V_EMP.ENAME`; the view name is treated as a table |
| The same query with `sources={"v_emp": "SELECT ename FROM emp WHERE job = 'CLERK'"}` | `V_EMP.ENAME`, then `EMP.ENAME` |
| `SELECT * FROM emp e, dept d WHERE e.deptno = d.deptno` | A `*` node with both tables as leaves |
| `SELECT e.ename, (SELECT MAX(sal) FROM bonus WHERE bonus.empno = e.empno) AS top FROM emp e` | Raises `OptimizeError: Cannot resolve 'SAL' due to missing source schemas` |
| `SELECT e.ename FROM emp e WHERE e.deptno IN (SELECT deptno FROM dept)` | Raises the same error for `DEPTNO`; the output column `e.ename` is qualified |
| Schema for `emp` and `dept`, the comma-join query above | `E.ENAME` and `D.DNAME` |
| Schema for `emp` only, the same query | `ename` resolves to `E`; `dname` stays a `Placeholder` |
| Both schemas contain `deptno`; `SELECT deptno FROM emp e, dept d WHERE ...` | `Placeholder` |

- The single-source rule is in `lineage()` itself ([lineage.py L403-L410](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/lineage.py#L403-L410)).
  A column with no matching source becomes a leaf with an `exp.Placeholder`, and the code comment says its lineage is unknown ([L493-L502](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/lineage.py#L493-L502)).
- The `OptimizeError` comes from `qualify_columns`.
  It raises for an unqualified column in a scope that can be correlated when any source schema is unknown ([qualify_columns.py L942-L943](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/optimizer/qualify_columns.py#L942-L943)).
  `validate_qualify_columns=False` does not suppress it.
- Release 30.22.0 removed `infer_schema` from the optimizer ([PR 8552](https://github.com/tobymao/sqlglot/pull/8552)).
  Before it, with an empty schema, an unqualified column went to the one source that had no schema.
  The PR description says the optimizer now requires a schema.
  The PR added the single-source rule to `lineage()` and made `schema` a required argument.
- Version drift: sqlglot 30.12.0, the version DataHub 1.7.0.19 pins, returns leaves for the scalar and `IN` probes instead of raising.
  For the scalar probe the leaf is named `E.BONUS`, which is not a column of the query.
- The scope API reads the same queries without raising.
  `traverse_scope` on the unqualified tree lists `sources` and `unqualified_columns` for each scope.
  An unqualified column in a subquery also appears in that scope's `external_columns` and in the enclosing scope's `unqualified_columns`.
  `external_columns` holds every column whose qualifier is not a source of the scope ([scope.py L489-L509](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/optimizer/scope.py#L489-L509)).
  A scope's `columns` include the `external_columns` of its subqueries ([L376-L396](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/optimizer/scope.py#L376-L396)).
  Identifiers carry line and column metadata, which `qualify` uses in its error messages (`Line: 1, Col: 12`).
- `lineage()` returns no confidence and no join graph.
  Join predicates come from walking `Join` and `Where` nodes, as in the [parser research](https://github.com/ozanozbeker/ichnos/blob/research/oracle-sql-parser/docs/research/oracle-sql-parser.md).

### sqllineage

`Column.parent_candidates` holds every table an unqualified column might belong to.
`Column.parent` returns a table only when there is exactly one candidate ([models.py L201-L264](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/models.py#L201-L264)).
`SQLLineageHolder.of` then resolves each column with several candidates.
It keeps the candidates that already have a column of that name in the graph, from a subquery or from a table written by another statement.
If none does, it reads the columns of each candidate that has a schema name from a `MetaDataProvider`, which can wrap a database through SQLAlchemy.
It links the column to every match, and a code comment says several matches are correct for `JOIN ... USING` ([holders.py L525-L563](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/holders.py#L525-L563)).

Probes use the `oracle` dialect (sqlfluff).

| Statements | Result for unqualified columns |
| --- | --- |
| `INSERT INTO t2 SELECT ename, dname FROM emp e, dept d WHERE e.deptno = d.deptno(+)` | `ename` and `dname` have no parent; the candidates are `emp` and `dept` |
| The same statement plus `INSERT INTO t1 SELECT e.ename FROM emp e`, in either order | `ename` resolves to `emp.ename`; `dname` stays unresolved |
| `emp.deptno` and `dept.deptno` each appear in a select list, then an unqualified `deptno` over both tables | Linked to both tables, with no flag |
| The only qualified use of `e.ename` is in a `WHERE` clause | `ename` stays unresolved |
| `INSERT INTO t1 WITH x AS (SELECT empno, sal FROM emp) SELECT sal FROM x, dept d WHERE ...` | `emp.sal`, `x.sal`, `t1.sal` |
| `CREATE VIEW v_emp AS SELECT e.ename, e.deptno FROM emp e`, then `INSERT INTO t1 SELECT ename FROM v_emp` | `emp.ename`, `v_emp.ename`, `t1.ename` |
| The `INSERT` alone | `v_emp` is a source table |
| A plain `SELECT` with no write target | No column lineage |

Resolution uses only columns that appear in column lineage, and only inside one run.
It reports no confidence.

### openlineage-sql

The README lists nine dialects, none of them Oracle.
`get_dialect` maps every other name, including `oracle`, to the generic dialect ([dialect.rs L33-L50](https://github.com/OpenLineage/OpenLineage/blob/bad2d7fc50c57d009ed58bb3643287aa1fe02631/integration/sql/impl/src/dialect.rs#L33-L50)).
The generic dialect fails on `(+)` with a parse error at the parenthesis.

The `SELECT` visitor sets a default table when the `FROM` list has one item ([visitor.rs L587-L602](https://github.com/OpenLineage/OpenLineage/blob/bad2d7fc50c57d009ed58bb3643287aa1fe02631/integration/sql/impl/src/visitor.rs#L587-L602)).
A query written `FROM emp e JOIN dept d ON ...` is one `FROM` item with a join, so the default is `emp`.
Probe: `INSERT INTO t1 SELECT ename, dname FROM emp e JOIN dept d ON e.deptno = d.deptno` attributes both columns to `emp`.
With a comma join (two `FROM` items) the same columns get `origin: None`.
Failed statements appear in `errors` with the statement index and text.

### DataHub

`sqlglot_lineage()` takes a `SchemaResolver` that holds the schemas registered in DataHub.
It runs the sqlglot optimizer with `validate_qualify_columns=False` and `allow_partial_qualification=True`.
An exception in column-level lineage goes to `debug_info.column_error`, and table lineage is still returned ([L2396-L2426](https://github.com/datahub-project/datahub/blob/9ad8572c455468f94cff613b38663d49ae2561aa/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L2396-L2426)).

Confidence is `0.9` when every discovered table has a registered schema.
Otherwise it is `0.2 + 0.3 * resolved / discovered` ([L2372-L2383](https://github.com/datahub-project/datahub/blob/9ad8572c455468f94cff613b38663d49ae2561aa/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L2372-L2383)).
The output table of an `INSERT` counts as a discovered table.
Measured values for two source tables:

| Statement | No schema | `emp` only | `emp` and `dept` |
| --- | --- | --- | --- |
| `INSERT INTO t1 SELECT ...` (no schema for `t1`) | 0.20 | 0.30 | 0.40 |
| Plain `SELECT` | 0.20 | 0.35 | 0.90 |

Column and join probes use release 1.7.0.19 with no schema unless stated.

| Statement | `column_lineage` | `joins` |
| --- | --- | --- |
| `INSERT ... SELECT ename, dname FROM emp e, dept d WHERE e.deptno = d.deptno(+)` | Empty `upstreams`; no error recorded | `JOIN` of `emp` and `dept`, no columns |
| The same with `emp e LEFT JOIN dept d ON e.deptno = d.deptno` | Empty `upstreams` | `LEFT JOIN`, columns `emp.DEPTNO` and `dept.DEPTNO` |
| The same with a qualified select list | `emp.ename`, `dept.dname` | Same |
| `INSERT ... SELECT e.ename FROM emp e WHERE e.deptno IN (SELECT deptno FROM dept)` | `emp.ename` | `LEFT JOIN`, columns `emp.DEPTNO` and `dept.DEPTNO` |
| Both schemas registered, comma join | `emp.ename`, `dept.dname` | `JOIN`, no columns |

- A column with no resolved table gets empty `upstreams` and no error.
  With both schemas registered, `SELECT deptno FROM emp e JOIN dept d ON ...` (both tables have `deptno`) also returns empty `upstreams`, no error and confidence 0.90.
  The score does not reflect unresolved columns.
- `_list_joins` reads `Join` nodes and their `ON` clauses, so a `WHERE` equality adds no columns ([L1719-L1883](https://github.com/datahub-project/datahub/blob/9ad8572c455468f94cff613b38663d49ae2561aa/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L1719-L1883)).
  The optimizer rules that DataHub runs include `unnest_subqueries` ([L276-L293](https://github.com/datahub-project/datahub/blob/9ad8572c455468f94cff613b38663d49ae2561aa/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L276-L293)), and the `IN` subquery appears in `joins` as a `LEFT JOIN`.
  A TODO in `_list_joins` asks for a confidence tracker.
- The [docs](https://docs.datahub.com/docs/lineage/sql_parsing) report 97 to 99% accuracy in the project's benchmarks and give no method.

### OpenMetadata

Usage ingestion reads a query log from database system views (for example `pg_stat_statements`) or a CSV file, and publishes `TableJoins` that the UI shows as "Frequently Joined With" ([docs](https://docs.open-metadata.org/v1.13.x/developers/contribute/codebase-deep-dives/usage-ingestion)).
The join scan is separate from the lineage parser.
It parses each statement with `sqlparse`, keeps `Comparison` tokens whose two sides both contain a dot, and maps each qualifier through the query's alias table.
It drops a comparison with an unqualified side, or with a qualifier that matches no table of the query ([parser.py L387-L425](https://github.com/open-metadata/OpenMetadata/blob/6cea3f629e093b99f8253fa9f2df000c5a23e888/ingestion/src/metadata/ingestion/lineage/parser.py#L387-L425)).

Replaying that loop with sqlparse 0.6.0 gives:

| Query | Comparisons kept |
| --- | --- |
| `... orders o JOIN customers c ON o.customer_id = c.id` | `o.customer_id = c.id` |
| `... ON o.customer_id = c.id AND o.region = c.region` | Both |
| `... FROM orders o, customers c WHERE o.customer_id = c.id` | None |
| The same with `c.id(+)` | None |
| `... ON customer_id = id` | None |
| `... ON o.created < c.created` | `o.created < c.created`; the code does not check the operator |

The sink adds 1 to `joinCount` for each occurrence of a column pair ([metadata_usage.py L355](https://github.com/open-metadata/OpenMetadata/blob/6cea3f629e093b99f8253fa9f2df000c5a23e888/ingestion/src/metadata/ingestion/bulksink/metadata_usage.py#L355)).
A `TableJoins` record has a `startDate` within the last 29 days and a `dayCount` ([table.json L429-L457](https://github.com/open-metadata/OpenMetadata/blob/6cea3f629e093b99f8253fa9f2df000c5a23e888/openmetadata-spec/src/main/resources/json/schema/entity/data/table.json#L429-L457)).
A code comment says the parser sends each pair once, from left to right, and the backend prepares the reverse pair.

### Uber Queryparser

Uber needed every foreign key in its warehouse to migrate to UUID identifiers.
It collected the SQL submitted to the warehouse and looked at which columns were joined ([blog post, 2018](https://www.uber.com/blog/queryparser/)).
[Queryparser](https://github.com/uber/queryparser/tree/6ae2e94567189cf842f7134d65b14e1089f06970) parses a query, resolves names against a catalog that lists every column of every table, then lists the columns compared for equality.

- The catalog was hard-coded at first.
  Later the team kept it in configuration files.
  Deriving schema changes from the query stream needed an ordering of the whole stream, which was too hard.
- The post grades its examples: `JOIN ... ON` is obvious, an `IN` subquery is less obvious, and `UNION` columns are debatable.
  The team counted all three because it reviewed the output by hand.
- The `joins` analysis pairs every column on one side of an equality with every column on the other.
  The README shows `ON a=x AND b+c = y+z` giving the pairs `x <-> a`, `y <-> b`, `y <-> c`, `z <-> b` and `z <-> c`.
- The worst case was a primary key with foreign keys under more than 50 different column names.

### Hosted products

- Google Knowledge Catalog (preview) analyzes a sample of BigQuery query history for `JOIN` patterns.
  The console shows the joined columns, the origin `Query history` and a sample query for each relationship.
  Discovery can take up to 72 hours.
- Snowflake Semantic View Autopilot extracts relationships from example SQL and from the query history visible to the role that creates the view.
  It derives keys from metadata or distinct counts.
- Neither page documents how it treats unqualified columns or confidence.

## Papers

| Paper | Input and evidence | Check and confidence | Ambiguity |
| --- | --- | --- | --- |
| Petit, Toumani, Boulicaut, Kouloumdjian, [ICDE 1996](https://perso.liris.cnrs.fr/jean-francois.boulicaut/icde96.pdf) (read in full) | Schema with declared unique and not null constraints, table data, and a set of equi-joins taken from application programs | Counts distinct values of both attribute sets and of their join. Equal to one side: inclusion dependency. Empty: none. Partial overlap: an expert decides. No score | Equi-join extraction is not trivial (nested and unnested queries, `WHERE`, `INTERSECT`); multi-attribute joins are assumed given; an expert validates |
| Elmeleegy, Ouzzani, Elmagarmid, [ICDE 2008](https://www.cs.purdue.edu/homes/ake/pub/icdeusage2008.pdf) | Query logs of two schemas: clause role of each attribute (select, where or having, group by, order by) and co-occurrence in a query; a join predicate marks a candidate key; use with `count`, `min` or `max`, and `sum` or `avg` | 16 graphs of attribute pairs, weighted by occurrence count divided by the largest weight in the graph; a genetic algorithm searches for the best match between schemas | Not discussed; both schemas are given. Transactions are not handled |
| Khoussainova, Kwon, Balazinska, Suciu, SnipSuggest, [PVLDB 2010](https://homes.cs.washington.edu/~magda/papers/khoussainova-vldb11.pdf) | Query log: tables, columns and predicates of past queries as features | Marginal and conditional probabilities of a feature given the partial query; up to 93.7% average precision on two logs. The task is autocomplete, not inference | Canonicalizes each query (constants removed, `FROM` tables ordered) and keeps the last query of each session, so repeated edits count once |
| Tripathi, Shetye, Qiao, Jindal, [arXiv 2603.04176](https://arxiv.org/abs/2603.04176) (2026) | Database with data, plus join paths parsed from query history by a relaxed ANTLR grammar | The system executes each parsed join on the database and keeps it if it returns rows, then merges the kept joins with joins inferred from statistics and an LLM. No score for this step; 78 to 100% precision reported for the whole pipeline | An LLM chooses the table for a join column that is not qualified; two joins on one table pair are shown to the user |
| Cong et al., [arXiv 2602.08186](https://arxiv.org/abs/2602.08186) (2026), Nexus | Metadata only; query logs optional | Joins known from logs get probability 1.0 in the join matrix. Other pairs get ML or LLM probabilities. F1 rises as more true joins are known (sampled from ground truth) | Not discussed |
| Lindner, Ritter, Naumann, [arXiv 2406.06886](https://arxiv.org/abs/2406.06886) (2024), after Kossmann et al. (CIDR 2022) | Executed query plans in a DBMS (Hyrise) | Candidate rules mirror the optimizer rules and return the dependencies that would let a rule apply; each candidate is validated on stored data | A plan has resolved columns, because the DBMS has bound them |

Not read in full:

- Andersson ([ER 1994](https://doi.org/10.1007/3-540-58786-1_93), abstract only) analyzes data manipulation statements in application code and uses the knowledge of which attributes link tables to examine the database extension selectively.
- Petit et al. ([ER 1994](https://doi.org/10.1007/3-540-58786-1_91), IJCIS 1995) are earlier versions of the 1996 method, listed in its references.
  Only their bibliographic records were read.
- Lopes, Petit, Toumani (Information Systems 27(1), 2002) are known through other papers.
  Zhang et al. ([PVLDB 2010](https://vldb.org/pvldb/vol3/R72.pdf)) say the method finds foreign keys from a query workload on the assumption that SQL joins use foreign and primary keys.
  Zhang et al. add that inclusion alone yields many spurious keys.
  De Marchi, Lopes, Petit ([JIIS 2009](https://liris.cnrs.fr/Documents/Liris-3034.pdf)) say it considers only the attributes found in SQL join statements that ran on the database server during a period.
  The [HAL record](https://hal.archives-ouvertes.fr/hal-00286638) could not be opened because it blocks automated fetches.
- Cleve and Hainaut ([WCRE 2008](https://doi.org/10.1109/WCRE.2008.38), portal summary only) analyze SQL statements captured by tracing a running program, to recover implicit information about the database structure.
- Kossmann et al. (CIDR 2022) returned HTTP 403, so the 2024 follow-up above was read instead.

## Evidence signals in use

| Signal | Used by |
| --- | --- |
| A join predicate between columns of two tables | Petit, Andersson, Queryparser, OpenMetadata, DataHub `joins`, Elmeleegy, Tursio |
| Equality in `WHERE` (comma join) | Petit names the form and Queryparser reads any equality; OpenMetadata and DataHub do not read it (tested) |
| `IN (subquery)` | Queryparser; DataHub, through the optimizer rewrite |
| `UNION` column positions | Queryparser, graded debatable |
| A qualified reference implies that a table has a column | sqllineage, from select-list columns only |
| Clause role and co-occurrence | Elmeleegy, SnipSuggest |
| Use under `sum` or `avg` argues against a key | Elmeleegy |
| Repeat count | OpenMetadata, Elmeleegy, SnipSuggest |
| Inclusion or join result on data | Petit, Tursio |

## Confidence in use

- None: sqlglot, sqllineage, OpenLineage SQL, Queryparser.
  The hosted products document none.
- Schema coverage: DataHub, as measured above.
  The score stays the same when a column is unresolved.
- Counts: OpenMetadata (`joinCount`, in records for dates within the last 29 days) and Elmeleegy (counts divided by the largest weight).
- Tests on data with expert review: Petit.
- Probabilities: SnipSuggest (conditional probabilities over the workload) and Nexus (ML or LLM scores, 1.0 for joins found in logs).
- Execution plus LLM: Tursio.

## Ambiguity in use

- **Aliases.**
  Each tool builds an alias map per statement or scope.
  In sqllineage, a qualifier that is not an alias becomes a table name.
  In OpenMetadata, a qualifier that matches no table of the query drops the comparison.
- **Views.**
  A bare view name is a table in sqlglot, sqllineage and OpenLineage SQL.
  sqlglot expands a view only when `sources` supplies its query.
  sqllineage follows a view whose `CREATE VIEW` is in the same run.
- **Subqueries and CTEs.**
  sqlglot and sqllineage trace CTEs and derived tables.
  sqlglot 30.26.0 raises on an unqualified column in a scalar or `IN` subquery when a schema is missing.
- **Schema prefixes.**
  sqlglot (`db`, `catalog`), DataHub (`default_db`, `default_schema`) and OpenLineage SQL (`default_database`, `default_schema`) take defaults as inputs.
  sqllineage uses `<default>`.
- The material read does not mention Oracle synonyms or database links.

## Implications for ichnos

These are inferences from the findings above, not claims from the sources.
They bear on [#9](https://github.com/ozanozbeker/ichnos/issues/9) and [#10](https://github.com/ozanozbeker/ichnos/issues/10).

- Oracle raises ORA-00918 when a query leaves a column name unqualified and more than one joined table has it ([Oracle error help](https://docs.oracle.com/en/error-help/db/ora-00918/)).
  The queries are valid, so an unqualified column in a flat join belongs to one table, except a `JOIN ... USING` column (the sqllineage code comment makes the same exception).
  In a subquery it can also belong to an enclosing query, which is why sqlglot lists it under `external_columns`.
  A set of candidate tables per column fits this.
  When other queries show that one candidate has the column, uniqueness removes the others, and sqllineage does this.
  When two candidates are both known to have the column outside `USING`, the evidence conflicts, and sqllineage links both without a flag.
- With an empty schema, `qualify()` in sqlglot 30.26.0 raises on any unqualified column unless `validate_qualify_columns=False`, and `lineage()` raises inside subqueries.
  The scope API reports unqualified columns and the sources of their scope without raising.
  The behavior also changed between 30.12.0 and 30.26.0 for the same input, which supports the regression corpus that the parser research proposed.
- None of the join extractors tested handles Oracle comma joins.
  OpenMetadata does not read `WHERE` equalities, OpenLineage SQL cannot parse `(+)`, and DataHub reports comma joins without columns.
  ichnos has to read equalities from `ON` and `WHERE` itself.
- No source derives direction from the query text.
  Petit tests inclusion on data.
  Queryparser prints unordered pairs, and OpenMetadata records a pair in the order written.
  A direction rule in ichnos would be new.
- DataHub's coverage score would be constant for ichnos, because no table has a registered schema.
  The strength measures in the query-based sources are counts or frequency-based probabilities (OpenMetadata, Elmeleegy, SnipSuggest).
- Query logs repeat queries.
  SnipSuggest canonicalizes queries and keeps the last one of each session.
  OpenMetadata counts every execution.

## Gaps

- No accuracy was measured against a known schema.
  The probes are short single-feature queries.
  The only accuracy figures come from the sources: DataHub (97 to 99%, no method), Tursio (78 to 100% for the whole pipeline) and SnipSuggest (a different task).
- DataHub probes ran on release 1.7.0.19 while the source was read at the `master` commit above.
  Every probe matched the confidence formula in that source.
- The OpenMetadata probe replays the traversal and the dotted-name filter, not the whole class.
- Elmeleegy et al. were read for the abstract, feature extraction and experiment setup, SnipSuggest in part, and Tursio and Nexus only where they use query logs.
- The Google and Snowflake pages document inputs, not mechanisms.

## Not covered

- Tools that need a live database to resolve names, such as index advisors and workload analyzers.
- Data-driven foreign key discovery beyond the papers that cite query workloads.
- Closed-source catalogs.
  A web search found no documentation of join inference from query logs for Alation, Atlan or Select Star.
- Commercial SQL parsers.
