# ichnos

ichnos infers a database schema and its lineage from Oracle SQL queries alone.
It never connects to the database.

## Input

**Query**: One SQL statement in the input, of any kind.
DML such as `INSERT` and `MERGE` counts.
_Avoid_: statement

**Corpus**: The set of queries ichnos reads, usually a folder of files.
A file may hold several queries.
_Avoid_: workload, query log

**Literal**: A fixed value written in a query, such as `'A'`, `10000` or `DATE '2024-01-01'`.
A bind variable such as `:customer_id` is not a literal.
_Avoid_: constant

**Creating query**: A query that creates a table from a `SELECT`: `CREATE TABLE ... AS SELECT`, `CREATE VIEW` or `CREATE MATERIALIZED VIEW`.
It declares the table's kind and its full column list.
_Avoid_: DDL, definition

**Declaration**: The table kind and the ordered column list that a creating query states for the table it creates.
_Avoid_: table definition, declared schema

**Report**: A query that reads tables and writes none.
It is never a table, because no other query can read it.
It takes no owner.
A query that reads only `DUAL` reads no table, so it is not a report.
Two files that hold the same text are two reports.
_Avoid_: asset, dashboard, output

**Output column**: One position in a report's select list, under the name Oracle gives it.
It is never a column, because a report is never a table.
_Avoid_: report column, result column

**Unparsed query**: A query that ichnos cannot read whole, or one that is not a `SELECT`, DML or a creating query.
ichnos skips it and lists it.
_Avoid_: invalid query, failed query

## Schemas

**Inferred schema**: The tables, columns and relationships ichnos derives from a corpus.
_Avoid_: model

**Graph**: The inferred schema, the reports, the lineage and the unparsed queries of one corpus.
_Avoid_: schema graph, result

**True schema**: The database's actual schema. ichnos never sees it.
_Avoid_: hidden schema, real schema, ground truth

**Answer key**: A true schema, or the true lineage of a corpus, written down so ichnos's output can be scored against it.

**Owner**: Oracle's namespace for tables, such as `HR` or `SALES`.
Oracle and DBML both also call it a schema, and this glossary does not.
_Avoid_: schema (for the namespace)

**Qualified name**: A table name together with its owner, written `owner.table`.

**Table**: A named relation that a query reads or writes and that exists outside the query.
Base tables, views and materialized views are all tables, and a synonym name counts as a table name.
_Avoid_: relation, entity, object

**Table kind**: Whether a table is a base table, a view or a materialized view.
Only a declaration states it.
_Avoid_: object type, table type

**Local relation**: A CTE or derived table defined inside one query.
It is never a table.
_Avoid_: subquery table, temp table

**Column**: A named attribute of a table that some query references or a creating query declares.
_Avoid_: field, attribute

**Undeclared column**: A column that a query references in a table whose declarations do not list it.
_Avoid_: missing column, extra column

**Pseudocolumn**: Oracle's term for a value such as `ROWNUM`, `ROWID`, `LEVEL`, `ORA_ROWSCN`, `CURRVAL` or `NEXTVAL` that a query reads like a column.
It is never a column of the inferred schema.

**Column reference**: One occurrence of a column name in one query.

**Table reference**: One occurrence of a table in one query, usually named by an alias.
A query that joins a table to itself holds two table references to it.
_Avoid_: table instance

**Key**: An inferred claim that a set of columns identifies at most one row of its table.
A table can have several keys, or none.
ichnos never claims a primary key.
_Avoid_: primary key, unique key, candidate key, identifier

**Relationship**: An inferred claim that columns of one table match columns of another table, or of the same table.
Its direction is a separate claim.
_Avoid_: edge, link, ref

**Direction**: The claim that one side of a relationship refers to a key of the other side.

**Shared reference**: A relationship whose two sides both refer to the same key column of a third table.
ichnos flags it and never drops it.
_Avoid_: sibling join, transitive join

**Foreign key**: A constraint declared in a true schema. ichnos infers relationships, never foreign keys.

## Inference

**Join condition**: A predicate in one query that compares columns of two tables.
It is evidence for a relationship, never a relationship itself.
_Avoid_: join (for the predicate)

**Evidence**: One observation in one query that supports a claim about a table, a column, a key, a relationship or a dependency.
_Avoid_: signal, hint, proof, observation

**Evidence count**: The number of distinct queries that hold evidence for a claim.
Identical query text counts once.
_Avoid_: confidence, score, weight

**Name match**: A column name that follows a key pattern for its table, such as `ID`, or `CUSTOMER_ID` in `CUSTOMERS`.
It supports a key on its own.
It is not evidence, because no query holds it, so it has no evidence count.
_Avoid_: naming evidence, naming hint, naming convention

**Observed value**: A literal that a query compares with a column by equality, or assigns to it.
A column's observed values are never its full set.
_Avoid_: enum, allowed value, domain, sample value

**Type**: An inferred claim that a column holds text, numbers, datetimes or intervals.
ichnos never claims an Oracle data type such as `VARCHAR2(10)`.
_Avoid_: data type, kind (for a type)

**Nullable**: An inferred claim that a column can hold `NULL`.
ichnos never claims that a column is `NOT NULL`.
_Avoid_: optional

**Ambiguity**: A point where the corpus admits more than one reading, such as an unqualified column in a query over two tables. ichnos records every candidate reading and picks none.
_Avoid_: conflict, uncertainty, warning

**Contradicted declaration**: A declaration that a query shows no longer describes its table.
The query holds an undeclared column, declares the table differently, or inserts a different number of values.
_Avoid_: stale declaration, invalid declaration

## Lineage

**Lineage**: The dependencies ichnos infers from a corpus.
_Avoid_: data flow, provenance

**Dependency**: An inferred claim that a table or column is derived from another table or column, or that a column selects which rows or values it holds.
A report and its output columns can be the downstream end, never the upstream end.
A dependency has no direction, because direction is a claim about a relationship.
_Avoid_: edge, dep, flow

**Direct dependency**: A dependency whose downstream value is computed from its upstream end, as from a bare column, an expression or an aggregate.
_Avoid_: value dependency

**Indirect dependency**: A dependency whose upstream column selects which rows or values the downstream end holds, as a column in `WHERE`, `JOIN`, `GROUP BY` or a `CASE` condition does.
_Avoid_: control dependency, filter dependency

**Rollup**: A dependency between two tables, or between a table and a report, that holds wherever another dependency joins them.
Its evidence count is the number of distinct queries that hold one.
_Avoid_: table-level dependency, table lineage

**Transformation subtype**: OpenLineage's name for how a dependency's downstream end uses its upstream end, such as `IDENTITY`, `AGGREGATION` or `FILTER`.
Each subtype is an evidence kind of the dependency.
_Avoid_: type, kind, transformation type

**Self-dependency**: A dependency whose two ends belong to one table.
_Avoid_: loop

**Upstream**: The end of a dependency that the other end is derived from or selected by: a table or a column.
_Avoid_: source, parent

**Downstream**: The end of a dependency that is derived or selected: a table, a report or a column.
_Avoid_: target, child, sink

## Output

**Slice**: A part of the inferred schema and lineage that ichnos selects for one question and writes to paste into an LLM chat.
_Avoid_: context, excerpt, subgraph, view

**Summary**: The list of one line per table and report that ichnos writes so a user can choose what to slice.
_Avoid_: table summary, overview, index, catalog
