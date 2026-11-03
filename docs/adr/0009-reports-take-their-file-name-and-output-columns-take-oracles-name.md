# A report takes its file's name, and an output column takes the name Oracle gives it

No query names a report, because a report is never a table.
So ichnos names a report after the file that holds it.
An output column takes the name that Oracle gives it, so the name matches what the report's reader sees in their own tool.
Every report name and every output column name in a report is unique, so each output format can refer to it by name.

## Report names

A report's name is its file's path relative to the corpus folder, without the extension, with `/` between folders.
The name keeps the file's case.
The file name alone is not enough, because two folders can each hold `x.sql`.

A file that holds more than one query adds `#N` to the name of each report in it.
N is the query's position among all queries in the file, counted from 1, as the answer key's `statement` column counts it.
So 038 gives `038_daily_reports#1` and `038_daily_reports#2`.
A file that holds a creating query and then a report names the report `#2`.
A file that holds one query adds no suffix.

ichnos raises an error that names both files when two reports get the same name.
`x.sql` and `x.txt` both give `x`, and a one-query `a#1.sql` gives the name of the first query in a multi-query `a.sql`.

A report takes no owner, because it is not a database object.
The inferred schema keeps reports apart from tables, so a report's name never compares with a table's name.
A DBML `Dep` endpoint must be a `Table`, so [DBML output with evidence](https://github.com/ozanozbeker/ichnos/issues/12) decides how a report's DBML name stays clear of table names.

## Queries that are not reports

A query that reads no table is not a report.
`DUAL` is not a table ([How Oracle conventions show up in queries](https://github.com/ozanozbeker/ichnos/issues/22)), so 032 is not a report.
Neither is a `SELECT` with no `FROM`, which Oracle 23ai accepts.
ichnos reads such a query and records nothing from it, and it is not an unparsed query.
A query that reads a table anywhere is a report, even through a scalar subquery in a query over `DUAL`.

## Output column names

An unaliased bare or qualified column takes the column's name alone, in dictionary form.
An unquoted name is uppercase, and a quoted name keeps its case.
So `a.id` gives `ID`, and 028's `p."ExternalRef"` gives `ExternalRef`.

ichnos builds the name of an unaliased expression from the query's source text, as Oracle does:

- It drops comments and all whitespace, including whitespace inside a literal.
- It uppercases what remains, including literals and quoted identifiers.
- It keeps a table alias as written, and it never truncates the name.

So `count( * )` gives `COUNT(*)`, and `o.qty * o.price` gives `O.QTY*O.PRICE`.

No Oracle document states the rule, but three sources show it:

- The [`DUMP` reference](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/DUMP.html) prints `DUMP('abc', 1016)` under the heading `DUMP('ABC',1016)`.
- The [`TRANSLATE` reference](https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/TRANSLATE.html) drops the spaces inside a literal from its heading.
- [node-oracledb's column metadata test](https://github.com/oracle/node-oracledb/blob/main/test/columnMetadata.js) expects `count(*)` to give `COUNT(*)`.

No source covers comments, a quoted identifier inside an expression, an alias inside an expression, or a name past Oracle's 30-byte or 128-byte identifier limit.
The rules above for those four cases are ichnos's choice, and a live Oracle can check them.
The corpus is valid production SQL, so Oracle ran every long name in it.

ichnos reads the text from the query's tokens, because sqlglot 30.26.0 cannot supply it.
Its `output_name` is empty for an unaliased expression, and its generated SQL rewrites `TRUNC(SYSDATE)` as `TRUNC(SYSDATE, 'DD')`.

Oracle allows two columns with the same name in a top-level `SELECT`.
In a report, the first output column keeps the name, and each later one takes a space and `(2)`, `(3)` and so on, skipping any name the report already holds.
Names compare in dictionary form, so `id` and `"ID"` are the same name.
So `SELECT a.id, b.id` gives `ID` and `ID (2)`, and `SELECT a AS "ID (2)", b AS id, c AS id` gives `ID (2)`, `ID` and `ID (3)`.
An unquoted Oracle name cannot hold a space or parentheses, so the suffix never matches an unquoted alias such as `ID_2`.

`CREATE VIEW` and `CREATE TABLE ... AS SELECT` reject an unaliased expression with ORA-00998 and a repeated name with ORA-00957.
So a declared column never needs these rules.

## Considered options

- The file stem alone as the report name.
  Rejected because two folders can each hold `x.sql`.
- A suffix on every report, which keeps a name stable when its file gains a query.
  Rejected because most files hold one query.
- N counts reports only.
  Rejected because a count of all queries matches what a reader sees in the file and the answer key's `statement`.
- An automatic fix when two reports get the same name.
  Rejected because the reader could not predict the name, and renaming a file is cheap.
- sqlglot's generated SQL as the name of an unaliased expression.
  Rejected because it differs from the source text, so the reader would not find the name in their tool.
- A position name such as `EXPR_3`.
  Rejected because it matches nothing the reader sees.
- The table alias as the qualifier of a repeated name, as in `A.ID` and `B.ID`.
  Rejected because an alias means nothing outside its query, and `SELECT id, id` has none.
