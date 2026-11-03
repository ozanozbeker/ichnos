# Synthetic Oracle corpus

This fixture is an invented Oracle schema and 58 query files over it.
Design work and tests use it until real queries are available.

`queries/` is the input: one or more statements per file, as ichnos would read a folder of production queries.
`answer_key/schema.sql` is the true schema as Oracle DDL, with every primary key, foreign key, view, synonym and database link.
`answer_key/lineage.csv` is the true lineage of every query, one dependency per row.
ichnos must never read the answer key as input, because a test scores inferred output against it.

## The schema

The schema has 22 tables, 3 views, 2 materialized views and 2 sequences in five owners.
`REF` holds lookup tables with character keys, `HR` holds employees and departments, `SALES` holds customers and orders, and `INV` holds products, stock and shipments.
`MART` holds a reporting pipeline over the other four.
The queries run as `APP_RO`, a user that owns no objects, so an unprefixed name resolves through a public synonym.
The pipeline files 045 to 053 run as `MART` and qualify every name.

## The pipeline

Each pipeline table has its creating query in the corpus:

- 045 creates `MART.ORDER_LINE_FACTS` from orders, order lines and products, and 046 appends the day's lines.
- 047 creates `MART.CUSTOMER_DAILY_SALES` from the line facts, and 048 merges the day's totals into it.
- 049 creates `MART.CUSTOMER_SEGMENTS` and 050 creates `MART.LAPSED_CUSTOMERS` from the daily totals.
  051 updates the segments.
- 052 creates the view `MART.V_KEY_CUSTOMERS` over the segments, and 053 creates the materialized view `MART.MV_CATEGORY_MONTHLY` over the line facts.
- 054 to 058 are reports over the pipeline.

The longest path runs five hops, from `SALES.ORDERS` to the reports 055 and 056.
The three views outside `MART` have no creating query in the corpus, so the corpus still covers a view that ichnos never sees created.

## Coverage

Each construct the corpus covers appears in these files:

| Construct | Files |
| --- | --- |
| ANSI joins | 002, 004, 010, 027, 034, 035, 043 |
| Comma joins with the condition in `WHERE` | 003, 037 |
| `(+)` outer joins | 005 (right side), 006 (self-join), 007 (left side, two columns), 044 (two columns) |
| Table and column aliases | Most files; 006 and 034 alias one table twice; 028 quotes its column aliases |
| CTEs | 010 (recursive), 011 (two CTEs), 049 (in a creating query) |
| Subqueries | 012, 025, 030, 039, 048 (inline view); 013, 026 (`EXISTS`); 014 (`NOT IN`); 015, 024 (scalar); 041 (`IN`) |
| `SELECT *` | 012 (over an inline view), 052 (over a table) |
| Set operations | 010, 021 (`UNION ALL`); 050 (`MINUS`) |
| `COUNT(*)` | 038, 039, 040, 041, 047, 048, 054 |
| `CASE` and `DECODE` | 029, 049, 051 |
| Unqualified columns | 001, 009, 014 (one table); 016, 042 (two tables); 021, 038, 039 |
| Schema prefixes | Most files; 003, 020, 040 have none; 028 quotes them; 037 is all uppercase |
| Views | 017, 018 (renamed columns) and 019 (materialized view) read a view with no creating query; 055, 056 and 058 read a view that 052 or 053 creates |
| Creating queries | 045, 047, 049, 050 (`CREATE TABLE ... AS SELECT`); 052 (`CREATE VIEW`); 053 (`CREATE MATERIALIZED VIEW`) |
| DML | 022 (`INSERT`), 023 (`INSERT ... SELECT`), 024 (`UPDATE`), 025 (`MERGE`), 026 (`DELETE`), 046 (`INSERT ... SELECT` with no column list), 048 (`MERGE` with both branches), 051 (`UPDATE` from its own table) |
| Several reports in one file | 038, 057 |
| Reports with the same text | 055, 056 |
| Other Oracle syntax | 009 (`CONNECT BY`), 012 (`ROWNUM`), 021 (database link), 022 and 032 (sequences), 029 (`DECODE`, `NVL`), 031 (`FETCH FIRST`), 033 (hint), 040 (`LISTAGG`), 041 (`ROWID`) |

## Traps

Some files lead a naive reading away from the answer key:

- 036 joins `HR.EMPLOYEES` to `SALES.CUSTOMERS` on `EMAIL`, and 044 joins `SALES.PAYMENTS` to `SALES.ORDERS` on `CURRENCY_CODE`.
  Neither join is a foreign key.
- 024 joins `SALES.ORDER_LINES` to `INV.STOCK_LEVELS` on `PRODUCT_ID`.
  Both columns reference `INV.PRODUCTS`, and neither references the other.
- `INV.WAREHOUSES` has the key `ID`, not `WAREHOUSE_ID` (008, 025, 043).
- `SALES.ORDERS` references `SALES.CUSTOMER_ADDRESSES` twice, through `SHIP_TO_ADDRESS_ID` and `BILL_TO_ADDRESS_ID` (034).
- `HR.DEPARTMENTS.LOCATION_COUNTRY` references `REF.COUNTRIES.COUNTRY_CODE` (035).
- `EMP` is a synonym for `HR.EMPLOYEES` (020), and `CUSTOMERS`, `ORDERS`, `ORDER_LINES` and `PRODUCTS` are synonyms with the table's own name (003, 040).
- `HR.EMP_DIRECTORY` renames every column it exposes (018).
- `sales.payments_seq.NEXTVAL` has the shape of `schema.table.column` (032).
- No query reads `HR.JOB_HISTORY`, and no query joins on some declared foreign keys, such as `SALES.CUSTOMER_ADDRESSES.CUSTOMER_ID`.
- 046's `INSERT` has no column list, and its select list does not use the table's column names, so only the column order that 045 declares maps its values.
- 048's `USING` subquery names its columns `LINES_TODAY`, `UNITS_TODAY` and `AMOUNT_TODAY`, and the `MERGE` writes them to `LINE_COUNT`, `UNITS` and `NET_AMOUNT`.
- 048 compares `MART.CUSTOMER_DAILY_SALES` with `MART.ORDER_LINE_FACTS` on three columns.
  No foreign key links them.
- 029's `STATUS_LABEL` and `SIZE_BAND` and 049's `SEGMENT` take only literals, so their only upstreams are `CONDITIONAL`.
- 050's second `MINUS` branch never reaches the output.
- 051 derives `SEGMENT` from itself, which a DBML `Dep` cannot express.
- 052 selects `*`, so only 049 declares the view's columns.
- 055 and 056 hold the same text, so they are two reports, and their evidence counts once.

## The lineage answer key

`answer_key/lineage.csv` holds one row per dependency per query, in these columns:

| Column | Value |
| --- | --- |
| `file` | The query file. |
| `statement` | The query's position in its file, from 1. |
| `downstream_table` | The table the query writes. It is empty for a report, which `file` and `statement` name. |
| `downstream_column` | The written column or report output column. It is empty when the dependency decides which rows the query writes or returns, rather than one column's value. |
| `upstream_table` | The table the query reads. |
| `upstream_column` | The column the query reads. It is empty when the query reads whole rows, as `COUNT(*)` does. |
| `type`, `subtype` | The transformation type and subtype of OpenLineage's [column lineage facet](https://github.com/OpenLineage/OpenLineage/blob/bcc7b97111f05f3ddcf0332f9d054dbbd75a3f90/website/docs/spec/facets/dataset-facets/column_lineage_facet.md). |

The key records every dependency kind, so a test can score any subset that the lineage rules adopt.
OpenLineage's facet is the only published list of kinds that [Prior art for column lineage from SQL](https://github.com/ozanozbeker/ichnos/issues/31) found.
A table-level dependency is a pair of `upstream_table` and downstream end in any row.

These rules fix each row:

- A name takes Oracle's dictionary form, so it needs no CSV quoting.
  An unquoted name is uppercase, a quoted name keeps its case, and every table carries its owner.
  A synonym resolves to its table, and a database link stays in the name, as in `SALES.ORDERS@ARCHIVE`.
- Only a table or a column is an upstream end.
  A literal, a bind variable, `SYSDATE`, a sequence, a pseudocolumn and `DUAL` give no row, so 022 and 032 have none.
  A `DELETE` derives no value, so 026 has none.
- The position of a column reference sets its subtype:
  - `IDENTITY` when the output is the bare column, `TRANSFORMATION` when the column feeds the output through an expression, `NVL` or a `CASE` result, and `AGGREGATION` when it feeds an aggregate.
  - `JOIN` in an `ON` clause, a `USING` list, a `MERGE` `ON` clause, `CONNECT BY`, or a `WHERE` conjunct that equates bare columns of two table references.
  - `FILTER` in any other `WHERE` or `HAVING` conjunct, in `START WITH`, and in every `MINUS` branch after the first.
  - `GROUP_BY` in `GROUP BY`, `SORT` in `ORDER BY`, `ORDER SIBLINGS BY` and `WITHIN GROUP`, `WINDOW` in `OVER`, and `CONDITIONAL` in a `CASE` condition or the first argument of `DECODE`.
- `COUNT(*)` reads whole rows of every table in its `FROM` clause.
- A select list position gives a row for its output column, and so does every clause inside that output expression, such as a scalar subquery's `WHERE`.
  A `SET` value and a `VALUES` entry count as select list positions.
  Every other position gives a row with an empty `downstream_column`.
- A reference to a CTE, an inline view or a subquery continues to the tables that it reads.
  Along that path, the outermost `INDIRECT` step sets the subtype.
  With no `INDIRECT` step, the first of `AGGREGATION`, `TRANSFORMATION` and `IDENTITY` on the path sets it.
  So every column of an `EXISTS` subquery is `FILTER`, while a correlated equality in a scalar subquery in the select list is `JOIN`.
- A set operation maps its branches by position.
- The key holds only the dependencies of corpus queries, so the three views outside `MART` have no rows of their own.
