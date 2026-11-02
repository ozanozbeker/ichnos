# Prior art for column lineage from SQL

Answers [Prior art for column lineage from SQL](https://github.com/ozanozbeker/ichnos/issues/31).
It builds on [Which SQL parser handles Oracle queries](https://github.com/ozanozbeker/ichnos/blob/research/oracle-sql-parser/docs/research/oracle-sql-parser.md), [How does sqloxide perform on valid Oracle queries](https://github.com/ozanozbeker/ichnos/blob/research/sqloxide-valid-queries/docs/research/sqloxide-valid-queries.md) and [Prior art for inferring schemas from query logs](https://github.com/ozanozbeker/ichnos/blob/research/schema-inference-prior-art/docs/research/schema-inference-prior-art.md), and does not repeat them.

## Answer

- **Writing queries.**
  No tool maps all five forms.
  sqllineage maps an `INSERT`, `CREATE VIEW` or `MERGE ... INSERT` column list by position.
  It drops the column list when the `INSERT` also reads its own table, as 023 does, and it maps an `UPDATE` value only when the value is one bare column.
  DataHub rewrites `UPDATE ... SET` as a `SELECT`, maps an `INSERT` column list only for T-SQL, and names `MERGE` columns after the `USING` subquery.
  sqlglot's `lineage()` and openlineage-sql read only a `SELECT`.
  They name the downstream columns after that `SELECT`, which for `UPDATE` and `MERGE` is a subquery.
- **`SELECT *`, CTEs, derived tables, set operations and correlated subqueries.**
  All four tools trace CTEs and derived tables.
  With no column list, `SELECT *` becomes a table-level `*` node in sqlglot, a `t1.*` column in sqllineage, and nothing in openlineage-sql and DataHub.
  sqlglot, sqllineage and DataHub map a set operation by position, and openlineage-sql maps each branch by its own names.
  A scalar subquery in a select list gives its own projection's upstream in all four tools.
- **Indirect lineage.**
  None of the four tools records a dependency from a column in `WHERE`, `JOIN`, `GROUP BY` or `ORDER BY`.
  A column in a `CASE` condition or a window's `PARTITION BY` is an ordinary upstream in all four.
  Of the sources read, only OpenLineage's column lineage facet names kinds: `DIRECT` with `IDENTITY`, `TRANSFORMATION` and `AGGREGATION`, and `INDIRECT` with `JOIN`, `GROUP_BY`, `FILTER`, `SORT`, `WINDOW` and `CONDITIONAL`.
  In the corpus, 159 of 332 column reads (48%) are in clauses that no tool reads for lineage.
- **`COUNT(*)`.**
  sqlglot and DataHub return the output column with no upstream, so neither records a dependency on the table.
  sqllineage links it to a `*` column of every table in `FROM`, joined tables included.
  openlineage-sql drops it.
  OpenLineage's column lineage facet cannot express it, because an input field requires a `field`; its newer Lineage facet makes `field` optional.
- **sqlglot's `lineage()` on the corpus.**
  The 40 reports have 140 output columns.
  120 resolve with an empty schema, 125 with a schema built from each query alone, and 129 with the answer key.
  Two reports raise with an empty schema.
  The 11 columns that never resolve are 3 `COUNT(*)` columns, a literal, `SYSDATE`, a sequence's `NEXTVAL`, 3 columns whose pseudocolumn sqlglot reads as a table column, and 2 columns that it traces to the name of a recursive CTE as if that were a table.
  For the 5 writing queries, `lineage()` raises on 022, and for 023 to 026 it returns the output of a `SELECT` inside the statement under that `SELECT`'s names.
  After ichnos-side rewriting into a `SELECT` per written column set, 7 of the 20 written columns resolve; the other 13 take bind variables, literals, `SYSDATE` or `NEXTVAL`.
- **The `schema` argument.**
  Column names are enough; types change nothing.
  Only 3 of 40 reports need a schema at all: 014 and 041 raise without one, and 016 has 4 unqualified columns over two tables.
  A schema built from each query alone stops both raises and leaves 016 as 4 unresolved columns, which [ADR-0001](../adr/0001-evidence-counts-and-no-attribution-on-ambiguity.md) requires.
  A schema built from the whole corpus resolves 3 of the 4 from other queries, which ADR-0001 rejects.
- **The sqloxide resolver.**
  It would need each scope's output names and positions, a link from each reference to a CTE or derived table to that scope's output column, set operations by position, `*` expansion, the four writing forms, clause tags for indirect dependencies, and a rule for `COUNT(*)`.
  sqlglot's `lineage()` and `to_node()` hold 320 code lines for the `SELECT` part.
  The writing-query mapping and the clause tags are extra work with either parser.

## Versions and method

All runs took place on 2026-11-02 with Python 3.13.12 on macOS arm64.

| Tool | Version run | Source read |
| --- | --- | --- |
| sqlglot | 30.26.0 (2026-10-29), as chosen in [Which SQL parser handles Oracle queries](https://github.com/ozanozbeker/ichnos/issues/6). 30.27.0 has the same `lineage.py`. | `lineage.py`, `optimizer/scope.py` and `optimizer/qualify_columns.py` at tag `v30.26.0` |
| sqllineage | 1.5.9, with sqlfluff 4.5.0 and `dialect="oracle"` | `core/` at tag `v1.5.9` |
| openlineage-sql | 1.55.0, with `dialect="generic"`, because it has no Oracle dialect | `visitor.rs` and `lineage.rs` at commit `bcc7b97` |
| OpenLineage spec | ColumnLineageDatasetFacet 1-2-0, LineageFacet 1-0-0 | Facet JSON and docs at commit `bcc7b97` |
| DataHub | acryl-datahub 1.7.0.19, which pins sqlglot 30.12.0 | `sqlglot_lineage.py` at commit `017b478` on `master`, which pins sqlglot 30.22.0 |

Release 1.7.0.19 has the same code for every DataHub behavior cited here, except `_LineageInferenceGuard`, which only `master` has.

Two scripts are in this folder.

- [`column_lineage_corpus.py`](column_lineage_corpus.py) calls `lineage(None, query, schema, dialect="oracle")` on all 45 queries in the 44 corpus files.
  File 038 holds two reports, called 038a and 038b here.
  It also rewrites the writing queries, finds the answer-key tables each query needs, and counts column reads by clause.
- [`column_lineage_probes.py`](column_lineage_probes.py) runs 16 single-construct probes through each tool, and writing queries 022 to 026 through the other three tools.
  The probes read `t1 (k, x, y)` and `t3 (k, w)` and write `t2 (a, b)`.

Each output column of `lineage()` gets one outcome, from the leaves of its graph:

- **resolved**: every leaf names a table column, and the answer key says the table has that column.
- **placeholder**: a leaf has no table (sqlglot's `exp.Placeholder`).
- **wrong**: a leaf names a table that has no such column in the answer key.
- **none**: the graph has no leaf, so the column derives from no column.

Only the `answer_key` schema mode, the **wrong** outcome and the `sources` run read `answer_key/schema.sql`.

In the tables below, `a ← b` means that `a` derives from `b`.
sqlglot's `Node.downstream` lists the nodes a column derives from, which are its upstream ends in the glossary's terms.
DataHub's `downstream` and `upstreams` mean what the glossary means.

## How each tool names the written columns

Probe results:

| Probe | sqlglot `lineage()` | sqllineage | openlineage-sql | DataHub |
| --- | --- | --- | --- | --- |
| `INSERT INTO t2 (a, b) SELECT x, y + 1 FROM t1` | `X ← T1.X`, `_COL_1 ← T1.Y` | `t2.a ← t1.x`, `t2.b ← t1.y` | `x`, `_0`, with no table | `t2.x`, and `t2."t1"."y" + 1` named by its text |
| `INSERT INTO t2 SELECT x, y FROM t1` | `X`, `Y` | `t2.x`, `t2.y` | `x`, `y` | `t2.x`, `t2.y` |
| `CREATE TABLE t2 AS SELECT x AS a, y FROM t1` | `A`, `Y` | `t2.a`, `t2.y` | `a`, `y` | `t2.a`, `t2.y` |
| `CREATE VIEW v2 (a, b) AS SELECT x, y FROM t1` | `X`, `Y` | `v2.a ← t1.x`, `v2.b ← t1.y` | `x`, `y` | `v2.x`, `v2.y` |
| `UPDATE t2 SET a = b` | Raises `Cannot build lineage, sql must be SELECT` | `t2.a ← b`, with no table for `b` | Nothing | `t2.a ← t2.b` |
| `UPDATE t2 SET a = a + 1, b = (SELECT MAX(t1.y) FROM t1 WHERE ...)` | `_COL_0 ← T1.Y`, the subquery's output | Nothing | `_0 ← t1.y`, the subquery's output | `t2.a ← t2.a`, `t2.b ← t1.y` |
| `MERGE INTO t2 tgt USING (SELECT k, y FROM t1) src ... UPDATE SET tgt.b = src.y ... INSERT (a, b) VALUES (src.k, src.y + 1)` | Raises `Cannot resolve 'K' due to missing source schemas`; with a schema, `K`, `Y` of `USING` | `t2.a ← src.k ← t1.k`, `t2.b ← src.y ← t1.y` | `src.k`, `src.y`, the `USING` outputs | `t2.k`, `t2.y` |

The writing queries in the corpus:

| Query | sqlglot `lineage()` | sqllineage | openlineage-sql | DataHub |
| --- | --- | --- | --- | --- |
| 022, `INSERT ... VALUES` | Raises `Cannot build lineage, sql must be SELECT` | Nothing | Nothing | Nothing |
| 023, `INSERT INTO sales.order_lines (order_id, line_no, product_id, quantity, unit_price) SELECT ...` | `_COL_0`, `LINE_NO`, `PRODUCT_ID`, `QUANTITY`, `LIST_PRICE` | Four columns named after the `SELECT`, including `list_price ← inv.products.list_price` | The same four, with no table | `:new_order_id`, `list_price` and three same-name columns |
| 024, `UPDATE inv.stock_levels sl SET ...` | `WAREHOUSE_ID ← INV.SHIPMENTS.WAREHOUSE_ID`, the `WHERE` subquery's output | Nothing, and no read tables | `_0 ← shipment_lines.qty_shipped` and `warehouse_id ← shipments.warehouse_id`, both subquery outputs | `qty_on_hand ← shipment_lines.qty_shipped, stock_levels.qty_on_hand`, and `updated_at` with no upstream |
| 025, `MERGE INTO inv.stock_levels ...` | `PRODUCT_ID`, `WAREHOUSE_ID` of the `USING` subquery | `stock_levels.product_id ← src.product_id ← inv.products.product_id`, and the same for `warehouse_id ← inv.warehouses.id` | `src.product_id`, `src.warehouse_id` | `product_id`, `warehouse_id`, correct only because the `USING` aliases match the written names |
| 026, `DELETE` | `1`, the `NOT EXISTS` subquery's output | Nothing, not even tables | Tables only | Tables only |

The causes, from the source:

- **sqlglot.**
  `lineage()` qualifies the statement and takes the root scope from `build_scope` ([lineage.py L143-L157](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/lineage.py#L143-L157)).
  `build_scope` returns the last scope that `traverse_scope` yields ([scope.py L708-L718](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/optimizer/scope.py#L708-L718)).
  For a `CREATE` that is the inner query ([L739-L744](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/optimizer/scope.py#L739-L744)), so `lineage()` ignores the column list of `CREATE VIEW v2 (a, b)`.
  For `INSERT`, `UPDATE`, `MERGE` and `DELETE` it is the last query inside the statement ([L745-L788](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/optimizer/scope.py#L745-L788)), and with no query inside, `lineage()` raises.
- **sqllineage.**
  It reads a bracketed column list as the write columns ([create_insert.py L81-L112](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/parser/sqlfluff/extractors/create_insert.py#L81-L112)), and maps by position only when that list is as long as the select list ([parser/\_\_init\_\_.py L33-L39](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/parser/__init__.py#L33-L39)).
  sqllineage reads the write columns through `_get_target_table`, which returns the written tables minus the read ones ([holders.py L263-L267](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/holders.py#L263-L267)).
  So when an `INSERT` reads its own table, as 023 does, the list is empty and the `SELECT` names apply.
  A probe confirms it: `INSERT INTO t2 (a, b) SELECT t1.x, t2.b FROM t1 JOIN t2 ...` gives `t2.x ← t1.x`.
  `UPDATE` and `MERGE ... UPDATE SET` give lineage only for `col = other_col` ([update.py L56-L77](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/parser/sqlfluff/extractors/update.py#L56-L77), [merge.py L40-L73](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/parser/sqlfluff/extractors/merge.py#L40-L73)).
  `MERGE ... INSERT` maps values by position and keeps those that hold a column reference ([merge.py L74-L123](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/parser/sqlfluff/extractors/merge.py#L74-L123)).
  `DELETE` goes to the no-op extractor ([noop.py L13-L14](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/parser/sqlfluff/extractors/noop.py#L13-L14)).
- **openlineage-sql.**
  `INSERT` visits the query and adds the output table, and never reads the column list ([visitor.rs L771-L784](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/integration/sql/impl/src/visitor.rs#L771-L784)).
  `MERGE` visits `USING` and `ON` and skips the `WHEN` clauses ([L785-L792](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/integration/sql/impl/src/visitor.rs#L785-L792)).
  `UPDATE` visits each assigned value but sets no output column for it ([L827-L857](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/integration/sql/impl/src/visitor.rs#L827-L857)).
- **DataHub.**
  `_try_extract_select` turns each writing query into a `SELECT` ([sqlglot_lineage.py L2311-L2394](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L2311-L2394)).
  `MERGE` becomes its `USING` subquery, with a TODO to map column renames ([L2318-L2324](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L2318-L2324)).
  `INSERT` maps its column list by position only for T-SQL ([L2325-L2378](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L2325-L2378)).
  `UPDATE` becomes `SELECT value AS column FROM target` ([L2245-L2308](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L2245-L2308)), and the target also counts as a read table ([L1059-L1061](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L1059-L1061)), so 024 gives a self-dependency.
  `CREATE` uses its inner query, with another TODO for column renames ([L2382-L2385](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L2382-L2385)).

## `SELECT *`, CTEs, derived tables, set operations and correlated subqueries

| Probe | sqlglot `lineage()` | sqllineage | openlineage-sql | DataHub |
| --- | --- | --- | --- | --- |
| `INSERT INTO t2 SELECT * FROM t1`, no schema | One `*` node on table `T1` | `t2.* ← t1.*` | Nothing | Nothing |
| The same, with a schema for `t1` | `K`, `X`, `Y` | Not run | Nothing | `t2.k`, `t2.x`, `t2.y` |
| `WITH c AS (SELECT x AS z FROM t1) SELECT z FROM c` | `Z ← T1.X` | `t2.a ← c.z ← t1.x` | `z ← t1.x` | `t2.z ← t1.x` |
| `SELECT d.z FROM (SELECT x AS z FROM t1) d` | `Z ← T1.X` | `t2.a ← d.z ← t1.x` | `z ← t1.x` | `t2.z ← t1.x` |
| `SELECT x FROM t1 UNION ALL SELECT w FROM t3` | `X ← T1.X, T3.W` | `t2.a ← t1.x, t3.w` | `x ← t1.x` and `w ← t3.w` | `t2.x ← t1.x, t3.w` |
| `SELECT t1.x, (SELECT MAX(t3.w) FROM t3 WHERE t3.k = t1.k) FROM t1` | `_COL_1 ← T3.W` | `t2.b ← t3.w` | `_1 ← t3.w` | `"_u_0"."_col_0" ← t3.w` |
| `SELECT w FROM t1 JOIN t3 ON t3.k = t1.k`, no schema | `W` with a placeholder leaf | `t2.a ← w`, with no table | `w ← t1.w`, the wrong table | `t2.w` with no upstream |

- **sqlglot.**
  A `*` projection gets one leaf per source table ([lineage.py L358-L365](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/lineage.py#L358-L365)), and a set operation maps each branch by position ([L272-L312](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/lineage.py#L272-L312)).
  When the single-source rule picks a derived table that does not project the column, `to_node` falls back to the whole inner `SELECT` ([L249](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/lineage.py#L249)).
  `SELECT x FROM (SELECT a FROM t WHERE b = 1) d` then gives `T.A` and `T.B`, a `WHERE` column.
  Oracle rejects that query, so a valid query takes this path only for a column that belongs to an outer scope.
  DataHub's `_LineageInferenceGuard` exists to block this guess ([sqlglot_lineage.py L1478-L1495](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L1478-L1495)).
  Correlation also makes sqlglot raise: an unqualified column in a scope that can be correlated raises when any source lacks a schema ([qualify_columns.py L942-L943](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/optimizer/qualify_columns.py#L942-L943)).
  In the corpus, this raises for the `IN` and `NOT IN` subqueries in the `WHERE` of 014 and 041, a clause that `lineage()` never reads.
- **sqllineage.**
  An unqualified `*` becomes a `*` column of every table in scope ([models.py L245-L248](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/models.py#L245-L248)).
  `expand_wildcard` replaces it with real columns only from a subquery or a `MetaDataProvider` ([holders.py L211-L240](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/holders.py#L211-L240)).
- **openlineage-sql.**
  It skips a wildcard projection ([visitor.rs L642](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/integration/sql/impl/src/visitor.rs#L642)) and visits each branch of a set operation on its own ([L710-L718](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/integration/sql/impl/src/visitor.rs#L710-L718)), so a `UNION` gets one output column per branch name.
- **DataHub.**
  It skips `*` when no schema expands it ([L1323-L1326](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L1323-L1326)).
  Its optimizer rules include `unnest_subqueries`, which rewrites the scalar subquery as a join, so the output column takes a generated name.

## Indirect dependencies and their kinds

No tool records a dependency from a column outside the select list:

- sqlglot's `to_node` collects the columns inside the projection only ([lineage.py L367-L368](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/lineage.py#L367-L368)).
- sqllineage builds a column from each select-list element only ([select.py L158-L164](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/parser/sqlfluff/extractors/select.py#L158-L164)).
- openlineage-sql clears the output column before it visits `WHERE`, so those columns add tables but no lineage ([visitor.rs L646-L653](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/integration/sql/impl/src/visitor.rs#L646-L653)).
  OpenLineage's Spark docs say that the SQL parser collects no transformation types ([spark_column_lineage.md L63](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/website/docs/integrations/spark/spark_column_lineage.md?plain=1#L63)).
- DataHub has a TODO to extract the columns outside the select list ([L1449](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L1449)).
  Its only kind is `is_direct_copy`, true when the output is a bare column, stored beside the projection's SQL text ([L453-L455](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L453-L455), [L1876-L1910](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L1876-L1910)).

Inside a projection, all four tools list condition columns as ordinary upstreams.
The probe `CASE WHEN t1.y > 0 THEN t1.x ELSE 0 END` gives `x` and `y`, and `ROW_NUMBER() OVER (PARTITION BY t1.k ORDER BY t1.y)` gives `k` and `y`.
In the corpus, `SIZE_BAND` in 029 derives from `ORDER_TOTAL` only through a `CASE` condition.

OpenLineage defines the kinds in its column lineage facet ([ColumnLineageDatasetFacet.json](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/spec/facets/ColumnLineageDatasetFacet.json), [docs](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/website/docs/spec/facets/dataset-facets/column_lineage_facet.md?plain=1#L178-L214)).
Each input field carries a list of transformations, and each transformation has a `type`, a `subtype`, a `description` and a `masking` flag.

| Type | Meaning | Subtypes |
| --- | --- | --- |
| `DIRECT` | The output value is derived from the input value. | `IDENTITY` (taken as is), `TRANSFORMATION` (computed from one input row), `AGGREGATION` (computed from several rows) |
| `INDIRECT` | The input affects the output value but the output is not derived from it. | `JOIN`, `GROUP_BY`, `FILTER` (`WHERE`), `SORT` (`ORDER BY`), `WINDOW`, `CONDITIONAL` (`IF`, `CASE WHEN`, `COALESCE`) |

- `masking` is true when the transformation hides the input, and the docs give `hash` and `count` as examples.
- Facet 1-2-0 has a `dataset` list for inputs that affect the whole output dataset, such as filters, sorts, groups, joins and windows.
  The docs call the older form, which copies each such input into every output column, very inefficient.
- The Spark integration combines kinds along a path: an `INDIRECT` step sets the result, two `DIRECT` steps take the first of `AGGREGATION`, `TRANSFORMATION`, `IDENTITY`, and any masking step makes the result masking ([spark_column_lineage.md L80-L86](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/website/docs/integrations/spark/spark_column_lineage.md?plain=1#L80-L86)).
- The newer Lineage facet 1-0-0 uses the same transformation object and supersedes the column lineage facet when both are present ([LineageFacet.json](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/spec/facets/LineageFacet.json), [lineage.md L60-L61](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/website/docs/spec/facets/dataset-facets/lineage.md?plain=1#L60-L61)).

The corpus has 332 column reads, not counting pseudocolumns and the columns a writing query assigns.

| Clause | Column reads |
| --- | --- |
| Select list, at any depth | 170 |
| `WHERE` | 71 |
| `JOIN ... ON` | 54 |
| `GROUP BY` | 15 |
| `ORDER BY` | 10 |
| `MERGE ... ON` | 4 |
| `CONNECT BY` and `START WITH` | 3 |
| `HAVING` | 2 |
| `UPDATE SET` and `MERGE` values | 3 |

The 159 reads in `WHERE`, `JOIN`, `GROUP BY`, `ORDER BY`, `MERGE ... ON`, `CONNECT BY`, `START WITH` and `HAVING` produce no dependency in any of the four tools.
The 170 in select lists include the select lists of `WHERE` subqueries, which the tools do not read for lineage either.

## Aggregates over whole rows

| Tool | `SELECT t1.x, COUNT(*) FROM t1 JOIN t3 ... GROUP BY t1.x` | Source |
| --- | --- | --- |
| sqlglot | `_COL_1` with no upstream. In the corpus, 038a, 038b and 039 get no upstream the same way. | `COUNT(*)` holds no `exp.Column`, so [L367-L368](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/lineage.py#L367-L368) finds nothing. |
| sqllineage | `t2.b ← t1.*` and `t2.b ← t3.*` | The `*` inside the function becomes a `*` column of every table in scope ([models.py L245-L248](https://github.com/reata/sqllineage/blob/v1.5.9/sqllineage/core/models.py#L245-L248)). |
| openlineage-sql | No entry | |
| DataHub | `count(*)` with no upstream | A code comment says a `count(*)` column gets no column lineage ([L1858-L1859](https://github.com/datahub-project/datahub/blob/017b478108a9cc04195ac3412380d1ed97cda54f/metadata-ingestion/src/datahub/sql_parsing/sqlglot_lineage.py#L1858-L1859)). |

The OpenLineage column lineage facet requires `namespace`, `name` and `field` on every input field ([ColumnLineageDatasetFacet.json L98](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/spec/facets/ColumnLineageDatasetFacet.json#L98)), so it has no form for "every row of this table".
The Lineage facet 1-0-0 requires only `namespace`, `name` and `type` on a dataset input ([LineageFacet.json L147-L177](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/spec/facets/LineageFacet.json#L147-L177)).
Its schema therefore allows an output column whose input is a table with no field, which is a table-to-column dependency.
The docs show no such example.

## sqlglot's `lineage()` on the synthetic corpus

### Schema modes

- **empty**: `schema={}`.
- **query**: the columns this query alone attributes to each table it names: a qualified reference, an unqualified reference in a scope with one source, a `JOIN ... USING` column, and a writing query's assigned columns.
  An unqualified column in a scope with several sources stays out, as ADR-0001 requires.
- **corpus**: for each table this query names, every column that any query attributes to it by the rules of the **query** mode.
- **answer_key**: the true schema, with views, the `EMP` synonym and the `@archive` link added.

### Reports

30 of the 40 reports resolve every output column in every mode, 110 columns in all.
The other 10:

| Report | empty | query | corpus | answer_key | Cause |
| --- | --- | --- | --- | --- | --- |
| 009 | 1 resolved, 2 wrong | same | same | same | `LEVEL` becomes `PRODUCT_CATEGORIES.LEVEL` |
| 010 | 2 resolved, 2 wrong | same | same | same | The recursive CTE's self-reference becomes table `CATEGORY_TREE` |
| 014 | Raises `Cannot resolve 'PRODUCT_ID' due to missing source schemas` | 3 resolved | 3 resolved | 3 resolved | Unqualified column in a `NOT IN` subquery |
| 016 | 4 placeholder | 4 placeholder | 3 resolved, 1 placeholder | 4 resolved | Unqualified columns over two tables |
| 021 | 4 resolved, 1 none | same | same | same | The literal `'CURRENT' AS source` |
| 032 | 1 placeholder, 1 none | same | same | same | `sales.payments_seq.NEXTVAL` reads as column `NEXTVAL` of table `PAYMENTS_SEQ`; `SYSDATE` |
| 038a | 1 none | same | same | same | `COUNT(*)` |
| 038b | 1 none | same | same | same | `COUNT(*)` |
| 039 | 3 resolved, 1 none | same | same | same | `COUNT(*)` in a derived table |
| 041 | Raises `Cannot resolve 'EMAIL' due to missing source schemas` | 2 resolved, 1 wrong | same | same | Unqualified column in an `IN` subquery; `c.ROWID` becomes a column |

| Mode | Resolved | Placeholder | Wrong | None | Reports that raise |
| --- | --- | --- | --- | --- | --- |
| empty | 120 | 5 | 4 | 5 | 2 (6 columns) |
| query | 125 | 5 | 5 | 5 | 0 |
| corpus | 128 | 2 | 5 | 5 | 0 |
| answer_key | 129 | 1 | 5 | 5 | 0 |

- `JOIN ... USING` in 042 gives `ORDER_ID ← ORDERS.ORDER_ID, ORDER_LINES.ORDER_ID`, one upstream from each table.
- The `@archive` link in 021 stays in the table name, `SALES."ORDERS@ARCHIVE"`, and the `UNION ALL` maps both branches by position.
- The **corpus** mode resolves 016's `ORDER_ID`, `ORDER_DATE` and `CUSTOMER_NAME` because other queries qualify them.
  `CREDIT_LIMIT` appears only in 016, so it stays a placeholder.

### What the `schema` argument needs

- Column names only.
  A copy of the answer key with every type set to `UNKNOWN` gives the same result for all 45 queries.
- The answer-key tables a report needs, found by removing tables one at a time while the result stays the same, are `SALES.ORDER_LINES` for 014, `SALES.CUSTOMERS` for 041, and `SALES.ORDERS` and `SALES.CUSTOMERS` for 016.
  The other 37 reports give the same result with an empty schema.
- Every column the query qualifies with a listed table.
  A schema that lists a table but not one of its referenced columns raises `Unknown column` ([qualify_columns.py L910-L915](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/optimizer/qualify_columns.py#L910-L915)), unless the call passes `allow_partial_qualification=True`, as DataHub does.
- `JOIN ... USING` columns in both tables, or the call raises `Cannot automatically join` ([L305](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/optimizer/qualify_columns.py#L305)).
  042 raised this until the **query** mode added `USING` columns to both sides.
- Only the tables this query names.
  A first run put the unprefixed `ORDERS` and `SALES.ORDERS` in one schema, and 003 and 040 raised `SchemaError: Ambiguous mapping for ORDERS: SALES, _NO_OWNER_`.
  sqlglot resolves an unprefixed table name against every owner in the schema, so one schema cannot hold an unprefixed name beside a qualified namesake.

### Writing queries

The script rewrites each writing query as one `SELECT` per written column set, with each projection named after the written column, in 55 code lines (`dml_selects`).
`INSERT` maps its column list onto the `SELECT` or `VALUES` row by position, `UPDATE` becomes `SELECT value AS column FROM target`, and each `MERGE` `WHEN` clause becomes its own `SELECT`.
The result is the same in every schema mode:

| Query | Written columns | Resolved | No upstream | Placeholder |
| --- | --- | --- | --- | --- |
| 022 | 9 | 0 | 8: bind variables, `SYSDATE`, `'NEW'` | 1: `sales.orders_seq.NEXTVAL` |
| 023 | 5 | 4, including `UNIT_PRICE ← INV.PRODUCTS.LIST_PRICE` | 1: `:new_order_id` | 0 |
| 024 | 2 | 1: `QTY_ON_HAND ← INV.STOCK_LEVELS.QTY_ON_HAND, INV.SHIPMENT_LINES.QTY_SHIPPED` | 1: `SYSDATE` | 0 |
| 025 | 4 | 2: `PRODUCT_ID ← INV.PRODUCTS.PRODUCT_ID`, `WAREHOUSE_ID ← INV.WAREHOUSES.ID` | 2: `0`, `SYSDATE` | 0 |

026 writes no column.
024 gives the self-dependency `QTY_ON_HAND ← STOCK_LEVELS.QTY_ON_HAND`, which [Lineage inference rules](https://github.com/ozanozbeker/ichnos/issues/35) has to keep or drop.

### Views through `sources`

`lineage()` takes a `sources` mapping of table name to query, and expands each such table before it traces ([lineage.py L130-L139](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/lineage.py#L130-L139)).
With the three view queries from the answer key as `sources`, reports 017, 018 and 019 trace through the views to base tables.
018's `FULL_NAME` traces to `HR.EMPLOYEES.FIRST_NAME` and `LAST_NAME` through the renamed view column.
019's `ORDER_COUNT` traces to no column, because the view computes it with `COUNT(*)`.
A creating query in the corpus could fill `sources` the same way.

## What the sqloxide resolver would need to add

The resolver from [How does sqloxide perform on valid Oracle queries](https://github.com/ozanozbeker/ichnos/issues/18) records base tables, column references attributed to base tables, references to CTEs and derived tables, and equality predicates.
Its code is not committed, so this list compares its documented output with what `lineage()` and the ichnos-side steps above do:

1. Output names and positions for each scope: the alias, the bare column name, or Oracle's name for an unaliased expression, plus a CTE's column list such as `category_tree (category_id, category_name, root_id, depth)` in 010.
2. For each projection, the column references inside it, and the scalar subqueries it holds, each traced through that subquery's projection.
3. A link from each reference to a CTE or derived table to the projection it names, traced until the result is base-table columns.
   The resolver records the reference but not the projection.
4. Set operations by position, with the names from the first branch.
5. `*` expansion from a CTE or derived table, and a table-level dependency for `*` on a base table.
6. The writing forms: the `INSERT` column list, `UPDATE` assignments, `MERGE` `WHEN` clauses, and the column list of `CREATE VIEW`.
   sqlparser-rs gives each its own shape, as rule 9 of that note already lists.
7. A clause tag on each column reference, so that a `WHERE`, `JOIN` or `GROUP BY` column can become an indirect dependency.
8. `COUNT(*)` as a dependency on the scope's tables.

The resolver already makes a CTE name visible inside its own body (its rule 5), so it should not repeat sqlglot's recursive-CTE error in 010.
It already filters `ROWNUM`, `LEVEL` and `NEXTVAL` (its rule 8), which sqlglot reports as columns in 009 and 032.
For scale, sqlglot's `lineage()` and `to_node()` hold 71 and 249 code lines, of which about 55 handle `PIVOT`, on top of the 701 in `scope.py`.
Items 6 and 7 are extra work for sqlglot too: 55 code lines for the rewrite and 26 for the clause tags in `column_lineage_corpus.py`.

## Implications for ichnos

These are inferences from the findings above, not claims from the sources.
They bear on [Lineage inference rules](https://github.com/ozanozbeker/ichnos/issues/35), [Creating queries as declarations](https://github.com/ozanozbeker/ichnos/issues/33) and [One parser or a parser seam for sqlglot and sqloxide](https://github.com/ozanozbeker/ichnos/issues/17).

- With a per-query schema, `lineage()` returns a graph for every report and every rewritten writing query in the corpus.
  ichnos still has to add four things that no tool provides: the writing-query mapping, indirect dependencies from clause tags, a table-to-column dependency for `COUNT(*)`, and a filter for pseudocolumns, sequences and recursive-CTE names among the leaves.
- A schema built from the query alone is the one that ADR-0001 allows.
  It stops the two raises and leaves 016's columns as an ambiguity.
  A corpus-wide schema resolves an ambiguity from other queries, which ADR-0001 rejects; [Creating queries as declarations](https://github.com/ozanozbeker/ichnos/issues/33) decides whether a declared column list may do so.
- Among the sources read, OpenLineage's types and subtypes are the only list of dependency kinds; DataHub has one flag, `is_direct_copy`.
  A kind for a `CASE` condition or a window column needs a clause tag inside the projection too, because every tool lists those columns as ordinary upstreams.
- OpenLineage's Lineage facet can express a table-to-column dependency, and its column lineage facet cannot.
- The writing queries in the corpus assign mostly bind variables and literals: 13 of 20 written columns have no column upstream.
  [Add a pipeline and a lineage answer key to the synthetic corpus](https://github.com/ozanozbeker/ichnos/issues/32) adds the cases that test the mapping.

## Limits

- No lineage answer key exists yet.
  **resolved** means the leaf names a real column of the named table, not that the dependency is the intended one.
- The probes are short single-construct queries.
  openlineage-sql ran with its generic dialect.
- DataHub's probes ran release 1.7.0.19 on sqlglot 30.12.0, while the cited source is `master` on sqlglot 30.22.0.
- sqllineage with a `MetaDataProvider`, and the Spark integration's transformation types, were not run.
