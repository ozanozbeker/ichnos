# A declaration fixes its table's kind and column list, and settles ambiguities until a query contradicts it

A creating query states the kind and the full, ordered column list of the table it creates.
This statement is a declaration.
The corpus holds the creating query of every table that its queries build.
Unlike a column reference, a declaration shows which columns its table lacked when it was created.
So ichnos uses declarations to settle ambiguities, the one exception to the rule in [ADR 0001](0001-evidence-counts-and-no-attribution-on-ambiguity.md).
It stops using a declaration once a query contradicts it.

## Creating queries

A creating query is a query that sqlglot parses as `exp.Create` with a `SELECT`:

- `CREATE TABLE ... AS SELECT`, with or without a column list, including `GLOBAL TEMPORARY` and `IF NOT EXISTS`.
- `CREATE [OR REPLACE] [FORCE] VIEW`, with or without a column list.
- `CREATE MATERIALIZED VIEW ... AS SELECT`.

`IF NOT EXISTS` does nothing when the table exists, so its column list can describe an older table.
It counts anyway, because a script that uses it usually re-runs the statement that created the table.
Any other DDL, including a `CREATE TABLE` with column types, is not a creating query ([ADR 0004](0004-sqlglot-is-the-only-parser.md)).

## What a declaration states

The column names come from the creating query's column list when it has one, and from its select list otherwise.
Oracle raises ORA-00998 for an expression with no alias in a creating query, so every column has a name.
A `*` or `t.*` over a declared table expands to that table's declared columns, in order, because Oracle expands a top-level `*` when it creates a view.
So 052 declares the four columns that 049 declares for `MART.CUSTOMER_SEGMENTS`.
A `*` over a table with no declaration stays unexpanded, and the creating query declares only the columns it names.
The `*` still gives a table-to-table dependency ([ADR 0010](0010-lineage-from-clause-positions-with-openlineage-subtypes.md)).

`declared` is an evidence kind for a column, counted in distinct creating queries.
ichnos marks a declared table's column list as complete, unless a `*` in its creating query stayed unexpanded.
A declaration applies only to the table name exactly as the creating query writes it.
So a declaration of `MART.X` says nothing about `X` or `MART.X@link`, and a declaration of `X` says nothing about `MART.X`.
It also settles nothing in the ambiguity that pairs an unprefixed name with its qualified namesakes ([issue 9](https://github.com/ozanozbeker/ichnos/issues/9)).

A declaration states one table kind: `base table` for `CREATE TABLE ... AS SELECT`, `view`, or `materialized view`.
ichnos reads a table kind from nothing else, so a table with no declaration has none.
Tables, views and private synonyms share one namespace per owner, so a declared name is not also a synonym.
So for the declared name, a declared kind settles 4 of the 10 cases in [How Oracle conventions show up in queries](https://github.com/ozanozbeker/ichnos/issues/22): a bare name, a qualified name that could be a private synonym, a local name that hides a database link, and a materialized view.

A declared column whose expression has a fixed type takes that type ([ADR 0007](0007-types-from-fixed-type-expressions-and-nullable-only.md)).

## Ambiguities a declaration settles

For an unqualified column with several candidate tables:

- ichnos removes each declared table that lacks the column.
- ichnos assigns the column to a declared table that declares it, and removes the other candidates in its scope.
  Oracle raises ORA-00918 when an unqualified name matches columns of two tables in one scope, so a valid query shows that only one has it.
- Oracle resolves a name in a correlated subquery's own scope first.
  So ichnos assigns the column to an inner declared table that declares it, and to an outer candidate only when it has removed every inner candidate.
- With one candidate left, the reference resolves and adds evidence like any other reference.
  With several left, the ambiguity keeps them.
  With none left, the ambiguity keeps all its original candidates.

A column traced through a `*` that a declaration expands is no ambiguity.
A `NATURAL JOIN` between two declared tables reads as `USING` over the declared names they share ([ADR 0002](0002-relationships-from-bare-equality-direction-from-key.md)).

In the synthetic corpus, 016 would resolve its five unqualified columns if either table had a declaration.
Neither has one, and no corpus ambiguity involves a declared table.

## An `INSERT` with no column list

An `INSERT`, each `INTO` of an `INSERT ALL`, and a `MERGE ... INSERT` with no column list map their n-th value to the n-th declared column.
Oracle raises ORA-00947 or ORA-00913 when the counts differ, so the mapping applies only when they match.
A mapped value counts as if a column list named its column, for `generated` key evidence ([ADR 0006](0006-keys-from-name-matches-and-four-query-shapes.md)), type evidence, observed values ([ADR 0003](0003-literals-give-types-and-observed-values-never-an-enum.md)) and nullable evidence.
With no declaration, the values map to no column and give no column evidence.
Each value still gives a column-to-table dependency ([ADR 0010](0010-lineage-from-clause-positions-with-openlineage-subtypes.md)).
In the corpus, 046's nine values map to the nine columns that 045 declares.

## Contradicted declarations

A query contradicts a declaration in one of three ways:

- It references a column that the declaration lacks, an undeclared column.
  Oracle raises ORA-00904 for a column that does not exist, so the column existed when the query ran.
- It creates the same table with a different kind, different names or a different order.
- It is an `INSERT` with no column list whose value count differs from the declared column count.

Only a reference that resolves without a declaration counts: a qualified column, the only candidate in its scope, or a column that a column list or a `SET` names.
So the settlement rules never take their own results as input.
A reference whose candidates are all declared without the column contradicts all of them, because one table changed and the query does not show which.

A contradicted declaration keeps its `declared` evidence, its table kind and its declared types.
ichnos no longer reads its column list as complete or ordered: it removes no candidate, settles no ambiguity, expands no `*`, maps no value and loses the complete mark.
An undeclared column stays in the inferred schema with its reference evidence.
Two creating queries that differ each keep their declared columns with their own counts, and ichnos flags an ambiguity over the column list, and over the table kind when the kinds differ.
Two that match in kind, names and order agree, and each column counts 2.

ichnos drops an unqualified `USER`, `UID`, `SESSIONTIMEZONE`, `DBTIMEZONE`, `ORA_INVOKING_USER` or `ORA_INVOKING_USERID`, which sqlglot 30.26.0 reads as a column ([ADR 0004](0004-sqlglot-is-the-only-parser.md)).
Each would otherwise be an undeclared column that contradicts a declaration.
054's `ORDER BY net_amount` names its own select-list alias, and `qualify` resolves it so, which a test can check.

## Considered options

- A declaration as evidence that never settles an ambiguity.
  Rejected because a declaration shows which columns its table lacked, which no reference can.
- Removing declared tables that lack the column, without the ORA-00918 argument.
  Rejected because 016, with only `SALES.ORDERS` declared, would keep three ambiguities that a valid query rules out.
- A flag per column with no count.
  Rejected because a count shows which of two differing declarations lists a column.
- No expansion of `*` through a declaration.
  Rejected because `MART.V_KEY_CUSTOMERS` would lose `SEGMENT`, which no query reads through the view.
- Dropping a reference to an undeclared column, because a declaration ranks above reference evidence.
  Rejected because it hides a column that a valid query proves.
- The last of two differing creating queries in corpus order wins.
  Rejected because file order does not show which statement ran last.
- A contradicted declaration still assigns the columns it declares, because an added column leaves them in place.
  Rejected because the corpus cannot show whether a column was also dropped.
- A table kind from `PARTITION`, `SAMPLE`, `VERSIONS`, a select of `ROWID`, or a DML target.
  Rejected because each rules out some kinds only, and an updatable view can be the target of DML.
