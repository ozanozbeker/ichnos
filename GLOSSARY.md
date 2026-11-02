# ichnos

ichnos infers a database schema from Oracle SQL queries alone.
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

## Schemas

**Inferred schema**: The tables, columns and relationships ichnos derives from a corpus.
_Avoid_: schema graph, model

**True schema**: The database's actual schema. ichnos never sees it.
_Avoid_: hidden schema, real schema, ground truth

**Answer key**: A true schema written down so an inferred schema can be scored against it.

**Owner**: Oracle's namespace for tables, such as `HR` or `SALES`.
Oracle and DBML both also call it a schema, and this glossary does not.
_Avoid_: schema (for the namespace)

**Qualified name**: A table name together with its owner, written `owner.table`.

**Table**: A named relation that a query reads or writes and that exists outside the query.
Base tables, views and materialized views are all tables, and a synonym name counts as a table name.
_Avoid_: relation, entity, object

**Local relation**: A CTE or derived table defined inside one query.
It is never a table.
_Avoid_: subquery table, temp table

**Column**: A named attribute of a table that some query references.
_Avoid_: field, attribute

**Pseudocolumn**: Oracle's term for a value such as `ROWNUM`, `ROWID`, `LEVEL`, `CURRVAL` or `NEXTVAL` that a query reads like a column.
It is never a column of the inferred schema.

**Column reference**: One occurrence of a column name in one query.

**Table reference**: One occurrence of a table in one query, usually named by an alias.
A query that joins a table to itself holds two table references to it.
_Avoid_: table instance

**Relationship**: An inferred claim that columns of one table match columns of another table, or of the same table.
Its direction is a separate claim.
_Avoid_: edge, link, ref

**Direction**: The claim that one side of a relationship refers to the key of the other side.

**Shared reference**: A relationship whose two sides both refer to the same key column of a third table.
ichnos flags it and never drops it.
_Avoid_: sibling join, transitive join

**Foreign key**: A constraint declared in a true schema. ichnos infers relationships, never foreign keys.

## Inference

**Join condition**: A predicate in one query that compares columns of two tables.
It is evidence for a relationship, never a relationship itself.
_Avoid_: join (for the predicate)

**Evidence**: One observation in one query that supports a claim about a table, a column or a relationship.
_Avoid_: signal, hint, proof, observation

**Evidence count**: The number of distinct queries that hold evidence for a claim.
Identical query text counts once.
_Avoid_: confidence, score, weight

**Observed value**: A literal that a query compares with a column by equality, or assigns to it.
A column's observed values are never its full set.
_Avoid_: enum, allowed value, domain, sample value

**Ambiguity**: A point where the corpus admits more than one reading, such as an unqualified column in a query over two tables. ichnos records every candidate reading and picks none.
_Avoid_: conflict, uncertainty, warning
