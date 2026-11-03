# Infer lineage from clause positions, with OpenLineage's subtypes

ichnos records a dependency for every column that a value is computed from, and for every column that selects which rows or values a query writes or returns.
No prior tool records the second kind, but 159 of the synthetic corpus's 332 column reads are in clauses that select rows ([issue 31](https://github.com/ozanozbeker/ichnos/issues/31)).
Each dependency carries a transformation subtype from OpenLineage's column lineage facet, the only published list of kinds, so a test scores it row for row against `answer_key/lineage.csv`.

## Direct and indirect dependencies

The position of a column reference sets its subtype, by the rules in the corpus README:

- A direct dependency is `IDENTITY` for a bare column, `TRANSFORMATION` for an expression, `NVL` or a `CASE` result, and `AGGREGATION` for an aggregate's argument.
- An indirect dependency is `JOIN`, `FILTER`, `GROUP_BY`, `SORT`, `WINDOW` or `CONDITIONAL`.

A column in a clause of the query, such as `WHERE`, `ON`, `GROUP BY` or `MERGE ... ON`, gives a column-to-table dependency on the written table, or a column-to-report one.
A clause inside an output expression, such as a `CASE` condition, an `OVER` clause or a scalar subquery's `WHERE`, gives a column-to-column dependency on that output column.
A `WHEN` condition of an `INSERT ALL` is `FILTER` for its `INTO` target.

A path through a local relation takes the subtype of its outermost indirect step.
With no indirect step, it takes the first of `AGGREGATION`, `TRANSFORMATION` and `IDENTITY` on the path, as OpenLineage's Spark integration does.
So every column of an `EXISTS` subquery is `FILTER`.
Every `MINUS` branch after the first is `FILTER`, because it removes rows and computes no value.

`COUNT(*)`, `COUNT(1)` and `COUNT` of a literal read whole rows.
Each gives a table-to-column `AGGREGATION` dependency from every table in its `FROM`, traced through local relations, so 039's `ORDER_COUNT` depends on `SALES.ORDERS`.
In a clause, it gives a table-to-table or table-to-report dependency with the clause's subtype instead.
So 040's and 041's `HAVING COUNT(*) > 1` give table-to-report `FILTER` dependencies.
An aggregate over a column, `COUNT(DISTINCT col)` included, gives a column-to-column `AGGREGATION` dependency.
`COUNT(*) OVER (...)` is `AGGREGATION` from whole rows, and its window columns give `WINDOW` dependencies.

## Ends

A table, a column, a report and an output column are the only ends.
A bind variable, a literal, `SYSDATE`, a sequence's `NEXTVAL` or `CURRVAL`, a pseudocolumn and `DUAL` give no dependency, so 022 has none.
A `DELETE` gives none, because it computes no value.
A local relation is never an end, and ichnos traces through it to the tables it reads.

[ADR 0009](0009-reports-take-their-file-name-and-output-columns-take-oracles-name.md) names each report and output column.
A report's `*` that stays unexpanded gives no output column.

An end names a table exactly as ichnos infers it.
So a path continues from a written table to a query that reads it only where both write the same name, and an unprefixed `X` stays apart from `MART.X` ([issue 9](https://github.com/ozanozbeker/ichnos/issues/9)).

## Values that map to no column

A declaration maps an `INSERT` with no column list and expands a `*` ([ADR 0008](0008-declarations-settle-ambiguities-until-contradicted.md)).
With no declaration, or a contradicted one:

- An unmapped value gives a column-to-table dependency from each column it reads to the written table, or a column-to-report one, with the value's own direct subtype.
- A `*` that stays unexpanded gives a table-to-table `IDENTITY` dependency, or a table-to-report one.

ichnos never maps a value by its select-list name, as sqlglot and sqllineage do.
046's select list names `QUANTITY` where the table has `UNITS`, and names nothing for two values.

A set operation maps its branches by position.
A value at or after an unexpanded `*` in a select list has no known position.
The first branch names the output columns, so a position it leaves unknown is unknown in every branch.

## Self-dependencies and cycles

ichnos keeps every self-dependency.
024 derives `QTY_ON_HAND` from itself, 051 derives `SEGMENT` from itself, and the `WHERE` of an `UPDATE` and the `ON` of a `MERGE` give indirect dependencies on their own target.
ichnos flags no cycle, because a cycle is a fact of the corpus, not an ambiguity.
DBML raises on `t.a -> t.a` ([issue 36](https://github.com/ozanozbeker/ichnos/issues/36)), so the output writes it as a column property ([ADR 0011](0011-dbml-evidence-as-custom-properties-in-one-file.md)).

## Evidence

A dependency is its pair of ends.
Each transformation subtype is an evidence kind, counted in distinct queries ([ADR 0001](0001-evidence-counts-and-no-attribution-on-ambiguity.md)).
039 gives `SALES.ORDERS.SALES_REP_ID` to its report as both `GROUP_BY` and `JOIN`, so one dependency holds two kinds, each with count 1.
An ambiguous upstream column gives a dependency ambiguity, which lists each candidate column with its count from other queries and adds evidence to none.

ichnos stores each dependency at the finest level its query shows.
A rollup joins two tables, or a table and a report, wherever another dependency joins them, and its count is the number of distinct queries that hold one.
The API and the output compute it ([ADR 0013](0013-public-api-is-a-graph-walks-that-return-slices-and-writer-functions.md)).
ichnos stores a dependency between two tables, or a table and a report, only for an unexpanded `*` and for a `COUNT(*)` in a clause.

A dependency is evidence for no relationship and no type.
[ADR 0002](0002-relationships-from-bare-equality-direction-from-key.md) counts only bare `=` for a relationship.
A type does not pass along a dependency, even an `IDENTITY` dependency in a creating query, where Oracle copies the data type.
The upstream column's type comes from other queries, and one wrong type would pass to every column downstream ([ADR 0007](0007-types-from-fixed-type-expressions-and-nullable-only.md)).

## Tracing

ichnos traces lineage itself over sqlglot's `optimizer.scope`, and never calls `sqlglot.lineage`.
`lineage()` collects columns inside the projection only ([lineage.py L367-L368](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/lineage.py#L367-L368)), lists a `CASE` condition as an ordinary upstream, and gives `COUNT(*)` no upstream.
It raises on 022, returns an inner `SELECT` for 023 to 026, and guesses the whole inner `SELECT` when its single-source rule misses ([L249](https://github.com/tobymao/sqlglot/blob/v30.26.0/sqlglot/lineage.py#L249)).
sqlglot 30.26.0's `traverse_scope` gives no scope for the statement level of an `UPDATE` or `MERGE` (run on 2026-11-03).
024's `SET` and `WHERE` columns, 048's `ON` and `WHEN` columns and every column of 051 are in no scope, so ichnos walks that level itself with either engine.

The private parser module ([ADR 0004](0004-sqlglot-is-the-only-parser.md)) returns a trace per query, with no declaration applied.
The trace holds:

- each output position with its name;
- each column reference with its clause and the output position it feeds;
- each `COUNT(*)` with its tables;
- each `*` that the query alone cannot expand;
- each `INSERT` value with no column list.

The lineage layer above the module expands `*` and maps values through declarations, applies the rules for values that map to no column, and combines the subtypes along each path.

## Considered options

- Direct dependencies only, as every prior tool records.
  Rejected because it drops 159 of 332 column reads, and 029's `STATUS_LABEL` and `SIZE_BAND` would have no dependency.
- No dependency for `COUNT(*)`, as sqlglot and DataHub give.
  Rejected because the count is computed from the table's rows.
- A table-to-table dependency for an unmapped value.
  Rejected because it drops the upstream column that the query names.
- Mapping a value by its select-list name.
  Rejected because it maps 046 wrong.
- Dropping a self-dependency, because DBML cannot write `t.a -> t.a`.
  Rejected because an output format should not remove a dependency from the lineage.
- Storing table-to-table dependencies apart from column-level ones.
  Rejected because they repeat what the column-level dependencies show, and the two counts could differ.
- A type passed along an `IDENTITY` dependency.
  Rejected for the reason above.
- `sqlglot.lineage`.
  Rejected for the reasons above.
