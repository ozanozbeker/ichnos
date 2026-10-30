# How Oracle conventions show up in queries

Answers [issue 22](https://github.com/ozanozbeker/ichnos/issues/22).

## Answer

A plain query names a table reference and does not state its kind.
A name in `FROM` can be a table, a view, a materialized view, or a synonym for any of them, on the local database or across a database link.
Only the data dictionary, or the `CREATE` statement of the object, states which.
A file of `SELECT` and DML statements has neither.
Ten cases leave the kind of a name open, and the section on cases lists them.

The other constructs add little to the schema.
`DUAL`, `ROWNUM` and `ROWID` are not columns of a user table.
A quoted identifier sets the case of a name.
Oracle's naming rules prescribe no prefix or suffix for user objects, and Oracle reserves several patterns for its own objects.

The table gives the form of each construct, and it says what a query contains and what it omits.

| Construct | Form in a query | The query contains | The query omits |
| --- | --- | --- | --- |
| Schema prefix | `hr.employees` | The schema that holds the name | The object kind, and the owner of the data when the name is a synonym |
| No prefix | `employees` | The name only | The schema: Oracle resolves the name in the current schema, then in public synonyms |
| Synonym | `emp`, written like a table | Nothing that marks a synonym | The target, its owner and its database link |
| View | `emp_v`, written like a table | The output column names of the view | The base tables, joins, filters and column renames |
| Database link | `employees@hq` | The link name | The remote schema, the remote object kind, the connect string and the remote user |
| `DUAL` | `FROM dual` | A reference to the one-row table `SYS.DUAL` | Any user table |
| `ROWNUM` | `WHERE ROWNUM <= 10` | A row counter | Any column, key or table |
| `ROWID` | `SELECT ROWID, last_name` | A row address | Any key or unique column |
| Quoted identifier | `"Order Total"` | The exact spelling of a name | Nothing; quoting changes which object the name denotes |
| Naming pattern | `V$SESSION`, `DBA_TABLES` | An Oracle-supplied object | Any meaning for a user prefix such as `V_` or `_SYN` |

## Sources and limits

All pages come from the Oracle AI Database 26ai documentation, read on 2026-10-30.
Version notes cite the 19c, 18c and 12.1 pages by name.
No Oracle database was available, so nothing in this note was run.
A fetch tool returned passages of each page, so the quotes and paraphrases follow those passages.
Check a quote against the linked page before reuse.
The tool read the SELECT page in full, and it read the Managing Tables page only in the sections on private temporary tables and the recycle bin.

## Name resolution and schema prefixes

These rules map a name in a query to an object.

- A database user owns a schema with the user's name, and the schema contains the user's schema objects ([Concepts: schemas]).
- A reference has the form `[schema.]object[.part][@dblink]`.
  Only schema objects take a `schema.` qualifier.
  A public synonym can take the qualifier `"PUBLIC"`, and the quotation marks are required ([schema object syntax]).
- Without a qualifier, Oracle first searches the tables, views and private synonyms of your own schema.
  A private synonym refers to its target, which can be in another schema, on another database, or be another synonym.
  If Oracle finds nothing, it searches the public synonyms.
  A match of the wrong type for the statement raises an error ([schema object syntax]).
- `ALTER SESSION SET CURRENT_SCHEMA` changes the schema that later unqualified names resolve in.
  It changes no privilege ([ALTER SESSION]).
- Oracle uses a public synonym only when the name has no schema qualifier and no database link ([CREATE SYNONYM]).
- Each schema has one namespace for tables, views, private synonyms, sequences, stand-alone procedures and functions, packages, user-defined types and user-defined operators.
  A table and a sequence in one schema cannot share a name, and the same follows for the other pairs in that list.
  Public synonyms have one database-wide namespace.
  Materialized views have their own namespace, but a schema cannot contain a table and a materialized view with one name ([naming rules]).
- A schema qualifier can name a schema that contains a private synonym.
  Other users use that synonym only by naming the schema and by holding privileges on the target ([CREATE SYNONYM]).
- After a table reference gets an alias, every other reference to it in the query must use the alias ([SELECT]).
  A reference to an object type attribute must start with a table alias, as in `c.cust_address.postal_code` ([schema object syntax]).

## Synonyms

A statement references a synonym the same way it references the target.

- Oracle defines a synonym as an alias for a table or view, sequence, PL/SQL program unit, user-defined object type, or another synonym.
  A synonym needs no storage beyond its dictionary entry ([Concepts: views and synonyms]).
  A synonym can also target a materialized view ([CREATE SYNONYM]).
- Oracle lists three purposes.
  A synonym masks the name and owner of an object.
  It gives location transparency for remote objects.
  It lets the target move or change its name while only the synonym changes ([Admin: views and synonyms]).
- A public synonym belongs to the user group `PUBLIC`, and every user can reference it, subject to privileges on the target ([Admin: views and synonyms], [CREATE SYNONYM]).
- The target does not have to exist, and the creator needs no privilege on it ([CREATE SYNONYM]).
  ORA-00942 covers a synonym that points to a missing table or view ([ORA-00942]).
- A synonym can point to a remote object, as in `CREATE PUBLIC SYNONYM emp_table FOR hr.employees@remote.us.example.com` ([CREATE SYNONYM]).
  The synonym stores the expanded link name, and it does not change when the global name of the remote database changes ([Admin: distributed databases]).
- A chain of synonyms that loops raises ORA-01775 ([ORA-01775]).
- The CREATE SYNONYM page lists the statements that accept a synonym.
  The DML statements are `SELECT`, `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `FLASHBACK TABLE`, `EXPLAIN PLAN`, `LOCK TABLE` and `CALL`.
  The DDL statements are `AUDIT`, `NOAUDIT`, `GRANT`, `REVOKE` and `COMMENT`.
  The page does not say that the list is complete.
- ORA-00942 names two rejections: a synonym used where the statement does not allow one, and a view used where the statement needs a table ([ORA-00942]).

## Views and materialized views

A view stores a query and no data.

- Oracle lists four uses for views.
  A view restricts the rows or columns that users see.
  It hides joins and calculations.
  It renames columns.
  It isolates applications from changes to base tables ([Concepts: views and synonyms]).
- Oracle stores the view text in the dictionary, and it expands a top-level `*` into a column list when it creates the view ([Admin: views and synonyms]).
- A materialized view stores a query result, and users query it directly with `SELECT`.
  Query rewrite transforms a request on the master tables into an equivalent request on a materialized view, with no change to the SQL text ([Concepts: views and synonyms], [CREATE MATERIALIZED VIEW]).
- Creating a materialized view creates one internal table and at least one index, and it may create a view.
  Oracle names them by adding a prefix or suffix to the name of the materialized view.
  `ON PREBUILT TABLE` registers an existing table under the name of the materialized view ([CREATE MATERIALIZED VIEW]).
- An editioning view selects some columns of one table and can alias them.
  The preparation procedure renames the table and gives the view the old table name, so existing SQL reads the view ([Development Guide: editions]).
- An object view is a virtual object table ([Concepts: views and synonyms]).
  The column `ALL_VIEWS.DUALITY_VIEW` marks a JSON-relational duality view ([ALL_VIEWS]).

## Database links

A database link adds a remote location to a name and adds no remote metadata.

- A reference follows the object name with `@dblink` ([schema object syntax]).
  A sequence pseudocolumn takes the link last, as in `schema.sequence.CURRVAL@dblink` ([sequence pseudocolumns]).
- In the SELECT page example, a column of a remote table takes the bare table name as its qualifier.
  The query joins `employees@remote` to `departments` with `employees.department_id = departments.department_id` ([SELECT]).
- The remote object can be a table, a view or a materialized view, and the remote database need not be an Oracle database ([SELECT]).
  The remote database resolves the name by the rules above, so the remote name can be a synonym ([schema object syntax]).
- A link name has up to 128 bytes and can contain periods and `@`.
  Oracle reads `ralph.linktosales` as one link name in your schema, not as link `linktosales` in schema `ralph`.
  A link name takes no schema qualifier ([naming rules], [CREATE DATABASE LINK]).
- Oracle adds the local domain to a link name that has none.
  Link names are case insensitive, and Oracle ignores quotation marks around them.
  So `@hq` and `@hq.example.com` can name one link ([schema object syntax], [CREATE DATABASE LINK]).
- With `GLOBAL_NAMES=TRUE`, the link name must equal the global name of the remote database.
  With `FALSE`, a link can have any name, so a link name does not identify the remote database ([Admin: distributed databases]).
- A link connects as a fixed user, as the connected user, or as the current user ([CREATE DATABASE LINK]).
  A synonym that has a link and no schema refers to the schema that the link specifies ([CREATE SYNONYM]).
  A query that omits the schema names neither the remote user nor the remote schema.
- Oracle states that the local database has no remote describe capability.
  It runs `SELECT *` on a remote object to determine its structure ([Admin: distributed databases]).
- A database link cannot define or enforce referential integrity ([Admin: distributed databases]).

## Quoted identifiers and case

Quoting sets the case and the allowed characters of a name.

- Oracle interprets a nonquoted identifier as uppercase.
  A quoted identifier is case sensitive.
  `employees`, `EMPLOYEES` and `"EMPLOYEES"` name one object.
  `"Employees"` and `"employees"` name two others ([naming rules]).
- Oracle uppercases by the rules of the database character set, as the SQL function `UPPER` does.
  It ignores `NLS_SORT` and does not use `NLS_UPPER` ([naming rules]).
- A nonquoted identifier starts with a letter and contains letters, digits, `_`, `$` and `#`.
  A quoted identifier can start with any character and can contain spaces and punctuation.
  Neither kind can contain a double quotation mark or a null character ([naming rules]).
- A quoted identifier can be a reserved word, although Oracle does not recommend it ([reserved words]).
- Names of databases, global databases, database links, disk groups and PDBs are always case insensitive and stored in uppercase.
  Oracle ignores quotation marks around them ([naming rules]).
- A name has 1 to 128 bytes when `COMPATIBLE` is 12.2 or higher.
  Below 12.2 the limit is 30 bytes, except 128 bytes for link names.
  The 19c page states the same rule ([naming rules], [naming rules 19c]).
- Quoted names appear beyond table and column names.
  A column alias can be quoted, as in `"Catalog Type"` ([schema object syntax]).
  A query reads a dropped table by its recycle bin name, as in `"BIN$yrMKlZaVMhfgNAgAIMenRA==$0"` ([Admin: tables]).

## DUAL, ROWNUM and ROWID

These three names are not columns of a user table.

`DUAL`:

- `DUAL` is a table that Oracle creates with the data dictionary.
  It belongs to the schema of `SYS`, and every user can access it by the name `DUAL`.
  It has one column, `DUMMY VARCHAR2(1)`, and one row with the value `X` ([DUAL]).
- A select from `DUAL` computes a constant expression once ([DUAL]).
- Release 23 makes `FROM DUAL` optional, so `SELECT 1 + 1` has no table reference.
  The 19c page has no such note ([DUAL], [DUAL 19c]).
- `DUAL` is not on the reserved word list ([reserved words]).

`ROWNUM`:

- A pseudocolumn behaves like a column but is not stored in the table.
  A query can select it, and no statement can insert, update or delete it ([Pseudocolumns]).
- `ROWNUM` numbers the rows that Oracle selects from a table or a set of joined rows, starting at 1 ([ROWNUM]).
- In one query block, `ORDER BY` reorders the rows after `ROWNUM` is assigned.
  A top-N query orders in a subquery and tests `ROWNUM` outside it.
  A test for `ROWNUM` greater than a positive integer is always false ([ROWNUM]).
- The page recommends `ROW_NUMBER` and the `row_limiting_clause` instead ([ROWNUM]).
  The clause is new in 12.1 ([12.1 changes]).
- `ROWNUM` is a reserved word and has no special note.
  By the general rule, a quoted `"ROWNUM"` can name a column.
  The pages show no example ([reserved words]).

`ROWID`:

- `ROWID` returns the address of a row.
  The value contains the data object number, the data block, the position in the block and the data file ([ROWID]).
- The data type is `ROWID` or `UROWID`.
  `UROWID` holds the logical address of a row in an index-organized table ([ROWID], [data types]).
- A rowid usually identifies one row.
  Rows of different tables in one cluster can share a rowid ([ROWID]).
- Oracle says not to use `ROWID` as a primary key.
  A rowid can change on import, and Oracle can reuse the rowid of a deleted row ([ROWID]).
- Selecting `ROWID` fails on a view built with `DISTINCT`, `GROUP BY` or expressions (ORA-01446) and on a join view without a key-preserved table (ORA-01445) ([ORA-01446], [ORA-01445]).
- The uppercase word `ROWID` cannot name a column, quoted or not.
  `"rowid"` can ([reserved words], [naming rules]).

Related names:

- The Pseudocolumns chapter lists hierarchical query pseudocolumns, sequence pseudocolumns, version query pseudocolumns, `COLUMN_VALUE`, `OBJECT_ID`, `OBJECT_VALUE`, `ORA_ROWSCN`, `ROWID`, `ROWNUM` and `XMLDATA` ([Pseudocolumns]).
- `sequence.NEXTVAL` and `sequence.CURRVAL` have the shape of `alias.column`, but the qualifier is a sequence, not a table ([sequence pseudocolumns]).
  A sequence shares the namespace of tables ([naming rules]).
- `ROWID`, `ROWNUM`, `LEVEL`, `SYSDATE`, `UID` and `USER` are reserved words, so a nonquoted use of one of them is not a user column ([reserved words]).

## Naming patterns

Oracle's naming rules prescribe no prefix or suffix for user objects, and Oracle reserves several patterns for its own.

- The guidelines recommend descriptive names, consistent rules, and one name for one attribute in every table, as `department_id` in `employees` and `departments` ([naming rules]).
- The naming rules page assigns no meaning to a prefix or suffix such as `V_`, `_VW` or `_SYN`.
  A query cannot verify such a habit.
- The Development Guide recommends a new name for a table that gets an editioning view.
  The name should relate to the original name and reflect the change history, as `Data_1` does for `Data` ([Development Guide: editions]).

The table lists the patterns that the Oracle pages document.

| Pattern | Meaning | Source |
| --- | --- | --- |
| `DBA_`, `ALL_`, `USER_` | Dictionary views for the whole database, for the objects the user can access, and for the objects the user owns | [Concepts: data dictionary] |
| `CDB_` | The `DBA_` view across the containers of a CDB | [Concepts: data dictionary] |
| `V$`, `GV$` | Public synonyms for `V_$` views that `SYS` owns; `GV$` adds the column `INST_ID` | [dynamic performance views], [Concepts: data dictionary] |
| `SYS_` | Names that Oracle generates for implicit objects and subobjects | [naming rules] |
| `ORA_` | Some Oracle-supplied objects | [naming rules] |
| `ORA$PTT_` | Default prefix of private temporary tables; a custom prefix must start with `ORA$` | [PRIVATE_TEMP_TABLE_PREFIX] |
| `BIN$unique_id$version` | Recycle bin name of a dropped table | [Admin: tables] |
| `SNAP$_` | Container name prefix for materialized views created before Oracle8i | [ALL_MVIEWS] |

The dictionary flags these names.
`ALL_OBJECTS.GENERATED` marks a system-generated name.
`ORACLE_MAINTAINED` marks the objects and users that Oracle scripts create ([ALL_OBJECTS], [ALL_USERS]).

## Data dictionary views

Each construct maps to dictionary views.
`ALL_` views list the objects that the current user can access, and they obey the enabled roles.
`DBA_` views list the whole database, and `USER_` views list the objects that the user owns ([Concepts: data dictionary]).

| Subject | View | Columns that matter |
| --- | --- | --- |
| Schemas | [ALL_USERS] | `USERNAME`, `ORACLE_MAINTAINED` |
| Any object kind | [ALL_OBJECTS] | `OWNER`, `OBJECT_NAME`, `OBJECT_TYPE`, `GENERATED`, `ORACLE_MAINTAINED`, `EDITION_NAME`, `DATA_OBJECT_ID` |
| Tables, clusters, views, synonyms and sequences | [ALL_CATALOG] | `OWNER`, `TABLE_NAME`, `TABLE_TYPE` |
| Tables | [ALL_TABLES] lists relational tables; [ALL_ALL_TABLES] adds object tables | `TEMPORARY`, `IOT_TYPE`, `PARTITIONED`, `EXTERNAL`, `NESTED` |
| Columns of tables, views and clusters | [ALL_TAB_COLUMNS] | `COLUMN_NAME`, `DATA_TYPE`, `NULLABLE`; `ALL_TAB_COLS` adds hidden columns |
| Views | [ALL_VIEWS] | `TEXT`, `TEXT_VC`, `READ_ONLY`, `DUALITY_VIEW` |
| Updatable columns of join views | `ALL_UPDATABLE_COLUMNS` | `OWNER`, `TABLE_NAME`, `COLUMN_NAME`, `UPDATABLE` ([Admin: views and synonyms]) |
| Editioning views | [ALL_EDITIONING_VIEWS] | `VIEW_NAME`, `TABLE_NAME` |
| Materialized views | [ALL_MVIEWS] | `CONTAINER_NAME`, `QUERY`, `MASTER_LINK` |
| Synonyms | [ALL_SYNONYMS] | `SYNONYM_NAME`, `TABLE_OWNER`, `TABLE_NAME`, `DB_LINK` |
| Database links | [ALL_DB_LINKS] | `DB_LINK`, `USERNAME`, `HOST` |
| Dependencies | [ALL_DEPENDENCIES] | `REFERENCED_OWNER`, `REFERENCED_NAME`, `REFERENCED_LINK_NAME` |
| Private temporary tables | [USER_PRIVATE_TEMP_TABLES] | The current session only |
| Dropped tables | `USER_RECYCLEBIN`, `DBA_RECYCLEBIN` | `OBJECT_NAME`, `ORIGINAL_NAME` ([Admin: tables]) |
| Reserved words | [V$RESERVED_WORDS] | `KEYWORD`, `RESERVED`, `RES_TYPE`, `RES_ATTR`, `RES_SEMI` |
| Dictionary view names | `DICTIONARY` | `TABLE_NAME` ([Concepts: data dictionary]) |
| `DUAL`, `ROWNUM`, `ROWID` | None | No dictionary view describes them |

Two points about these views:

- `ALL_VIEWS.EDITIONING_VIEW` is "reserved for future use" on its Reference page.
  The Development Guide says a row of `*_VIEWS` that matches a row of `*_EDITIONING_VIEWS` has `EDITIONING_VIEW = 'Y'`.
  Use `ALL_EDITIONING_VIEWS` to find editioning views ([ALL_VIEWS], [Development Guide: editions]).
- The description of `ALL_DEPENDENCIES` names procedures, packages, functions, package bodies, triggers and views created without database links.
  It does not name synonyms ([ALL_DEPENDENCIES]).

## Cases where a query alone cannot tell a table from a view or a synonym

In each case the query does not state the kind of the name.

1. A bare name.
   A name in `FROM`, or the target of `INSERT`, `UPDATE`, `DELETE` or `MERGE`, can be a table, a view, a materialized view or a synonym.
   The view can be an object view or a JSON-relational duality view.
   The SELECT syntax groups table, view and materialized view.
   The Concepts guide says views serve in most places where tables serve.
   The Administrator's Guide says a DML statement references a synonym the same way as its target ([SELECT], [Concepts: views and synonyms], [Admin: views and synonyms], [ALL_VIEWS]).
2. A schema-qualified name.
   `hr.emp` can be a private synonym in `hr` whose target is in another schema ([CREATE SYNONYM]).
3. An unqualified name.
   Oracle searches your own schema, then public synonyms, so one text can denote different objects in different sessions.
   In the CREATE SYNONYM example, `SELECT COUNT(*) FROM customers` reads `sh.customers` for user `sh`, who owns a `customers` table.
   It reads `oe.customers`, through a public synonym, for user `hr`, who owns none ([schema object syntax], [CREATE SYNONYM]).
4. A chain of synonyms.
   A synonym can refer to another synonym before the chain reaches a table or view ([schema object syntax]).
5. A local name for a remote object.
   A synonym can hide a database link, so `emp` can be `scott.emp@sales.us.example.com` ([Admin: distributed databases], [CREATE SYNONYM]).
6. A remote name.
   `t@link` can be a table, a view or a materialized view on the remote database.
   The remote database applies the same resolution rules, so it can also be a remote synonym ([SELECT], [schema object syntax]).
7. A dictionary or dynamic performance view name.
   Oracle creates public synonyms for many dictionary views, so a dictionary view name in a query can be a synonym.
   A `V$` name is a public synonym for a `V_$` view over the dynamic performance tables ([Concepts: data dictionary], [dynamic performance views]).
8. A materialized view.
   Users query it as they query a table, and query rewrite can substitute it for the master tables with no change to the text ([CREATE MATERIALIZED VIEW], [Concepts: views and synonyms]).
9. An editioning view.
   After the editions procedure, the name that SQL uses for a table belongs to an editioning view, and the table has a new name ([Development Guide: editions]).
10. A query name.
    A name in `FROM` can be a query name from a `WITH` clause.
    Oracle states that the query name is visible to the main query and to later subqueries.
    The pages state no precedence over a schema object with the same name ([SELECT]).

Some table references name no stored object at all.
The SELECT page lists these forms ([SELECT]):

- A subquery, also called an inline view.
- `TABLE(collection_expression)`, which treats a collection value as a table.
- A `VALUES` table value constructor.
- A table function, including a polymorphic table function.
- A table macro, which `CREATE FUNCTION ... SQL_MACRO` defines from 19.6 and `CREATE MACRO` defines from 23.26.4.
- The `GRAPH_TABLE` operator from 23ai.
- An inline external table.

## Cases where the syntax states the kind

A few constructs limit the kind of object they apply to.

- `PARTITION (p)`, `SUBPARTITION (p)` and `PARTITION FOR (...)` apply to a partitioned base table.
  The SQL Language Reference excludes synonyms, views and other objects.
  The Development Guide adds one exception: an editioning view on a partitioned table ([schema object syntax], [Development Guide: editions]).
- The `VERSIONS` clause of a flashback query does not apply to views, temporary tables, external tables or clustered tables ([SELECT]).
- The `SAMPLE` clause applies to a base table, the container table of a materialized view, or a key-preserving view ([SELECT]).
- `ONLY (name)` applies to a view in a view hierarchy ([SELECT]).
- A query that selects `ROWID` without error does not read a view built with `DISTINCT`, `GROUP BY` or expressions, and it does not read a join view without a key-preserved table ([ORA-01446], [ORA-01445]).
- A `CREATE TABLE`, `CREATE VIEW`, `CREATE SYNONYM` or `CREATE MATERIALIZED VIEW` statement names the kind.
  For a view or a synonym it also names the target.

## Version differences

The table lists the changes that matter when parsing queries.

| Change | Release | Source |
| --- | --- | --- |
| `row_limiting_clause` (`FETCH FIRST`) | 12.1 | [12.1 changes] |
| Identifier limit rises from 30 to 128 bytes | 12.2, set by `COMPATIBLE` | [naming rules 19c], [naming rules] |
| Private temporary tables and the `ORA$PTT_` prefix | 18c | [PRIVATE_TEMP_TABLE_PREFIX 18c] |
| Table macros with `CREATE FUNCTION ... SQL_MACRO` | 19.6 | [SELECT] |
| `FROM` clause optional | 23 | [DUAL] |
| `GRAPH_TABLE` in `FROM` | 23ai | [SELECT] |
| `CREATE MACRO` | 23.26.4 | [SELECT] |

## Gaps

The pages reviewed do not state these points:

- Whether a `WITH` query name takes precedence over a table or view with the same name.
- How every user accesses `SYS.DUAL`, and whether a user can create a `DUAL` of their own.
- Which reading wins for an ambiguous three-part name: `schema.table.column` or `alias.column.attribute`.
- The set of `OBJECT_TYPE` values.
  The `ALL_OBJECTS` page names `TABLE` and `INDEX` as examples.
- Where the internal table of a materialized view appears in `ALL_TABLES` and `ALL_OBJECTS`.
- Whether the dictionary stores a quoted name in its exact spelling.
  The case rule implies uppercase for nonquoted names.
- Which statements accept only a base table.
  ORA-00942 names the situation without a list.
- Whether the statement list on the CREATE SYNONYM page is complete.

## Not covered

- Name resolution inside PL/SQL units.
- JSON dot notation and other attribute paths beyond the table alias rule.
- Whether a call to a function without arguments can omit the parentheses, and how that call reads against a column name.
- Optimizer hints, which can name aliases and indexes.
- Non-Oracle targets of database links.

## Implications for ichnos

These points are inferences from the sources above, not Oracle statements.

- Record each table reference as written: optional schema, name, and optional link.
  Keep the kind unknown unless an input `CREATE` statement states it.
- Fold nonquoted names to uppercase and keep quoted names exact.
  Fold only ASCII letters, because Oracle uppercases by the database character set.
- Merge `t` with `s.t`, or `t` with `t@link`, only on explicit configuration.
  Queries do not show the current schema or the link target.
- Skip `DUAL`, a `SELECT` without `FROM`, the pseudocolumns and the reserved bare names.
  Treat `x.NEXTVAL` and `x.CURRVAL` as sequence references, not as a table alias.
- Mark a join across a database link as a cross-database relationship, not a foreign key, because Oracle cannot define referential integrity over a link.
- Do not infer a key from `ROWID`.
- Mark names with the patterns `DBA_`, `ALL_`, `USER_`, `CDB_`, `V$`, `GV$`, `SYS_`, `ORA_`, `ORA$PTT_` and `BIN$` as Oracle-owned, because the tool cannot read `ORACLE_MAINTAINED`.

[12.1 changes]: https://docs.oracle.com/database/121/SQLRF/release_changes.htm
[Admin: distributed databases]: https://docs.oracle.com/en/database/oracle/oracle-database/26/admin/distributed-database-concepts.html
[Admin: tables]: https://docs.oracle.com/en/database/oracle/oracle-database/26/admin/managing-tables.html
[Admin: views and synonyms]: https://docs.oracle.com/en/database/oracle/oracle-database/26/admin/managing-views-sequences-and-synonyms.html
[ALL_ALL_TABLES]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_ALL_TABLES.html
[ALL_CATALOG]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_CATALOG.html
[ALL_DB_LINKS]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_DB_LINKS.html
[ALL_DEPENDENCIES]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_DEPENDENCIES.html
[ALL_EDITIONING_VIEWS]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_EDITIONING_VIEWS.html
[ALL_MVIEWS]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_MVIEWS.html
[ALL_OBJECTS]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_OBJECTS.html
[ALL_SYNONYMS]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_SYNONYMS.html
[ALL_TAB_COLUMNS]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_TAB_COLUMNS.html
[ALL_TABLES]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_TABLES.html
[ALL_USERS]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_USERS.html
[ALL_VIEWS]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/ALL_VIEWS.html
[ALTER SESSION]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/ALTER-SESSION.html
[Concepts: data dictionary]: https://docs.oracle.com/en/database/oracle/oracle-database/26/cncpt/data-dictionary-and-dynamic-performance-views.html
[Concepts: schemas]: https://docs.oracle.com/en/database/oracle/oracle-database/26/cncpt/introduction-to-oracle-database.html
[Concepts: views and synonyms]: https://docs.oracle.com/en/database/oracle/oracle-database/26/cncpt/partitions-views-and-other-schema-objects.html
[CREATE DATABASE LINK]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/CREATE-DATABASE-LINK.html
[CREATE MATERIALIZED VIEW]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/CREATE-MATERIALIZED-VIEW.html
[CREATE SYNONYM]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/CREATE-SYNONYM.html
[data types]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/Data-Types.html
[Development Guide: editions]: https://docs.oracle.com/en/database/oracle/oracle-database/26/adfns/editions.html
[DUAL]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/Selecting-from-the-DUAL-Table.html
[DUAL 19c]: https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Selecting-from-the-DUAL-Table.html
[dynamic performance views]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/about-dynamic-performance-views.html
[naming rules]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/Database-Object-Names-and-Qualifiers.html
[naming rules 19c]: https://docs.oracle.com/en/database/oracle/oracle-database/19/sqlrf/Database-Object-Names-and-Qualifiers.html
[ORA-00942]: https://docs.oracle.com/en/error-help/db/ora-00942/
[ORA-01445]: https://docs.oracle.com/en/error-help/db/ora-01445/
[ORA-01446]: https://docs.oracle.com/en/error-help/db/ora-01446/
[ORA-01775]: https://docs.oracle.com/en/error-help/db/ora-01775/
[PRIVATE_TEMP_TABLE_PREFIX]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/PRIVATE_TEMP_TABLE_PREFIX.html
[PRIVATE_TEMP_TABLE_PREFIX 18c]: https://docs.oracle.com/en/database/oracle/oracle-database/18/refrn/PRIVATE_TEMP_TABLE_PREFIX.html
[Pseudocolumns]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/Pseudocolumns.html
[reserved words]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/Oracle-SQL-Reserved-Words.html
[ROWID]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/ROWID-Pseudocolumn.html
[ROWNUM]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/ROWNUM-Pseudocolumn.html
[schema object syntax]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/Syntax-for-Schema-Objects-and-Parts-in-SQL-Statements.html
[SELECT]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/SELECT.html
[sequence pseudocolumns]: https://docs.oracle.com/en/database/oracle/oracle-database/26/sqlrf/Sequence-Pseudocolumns.html
[USER_PRIVATE_TEMP_TABLES]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/USER_PRIVATE_TEMP_TABLES.html
[V$RESERVED_WORDS]: https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/V-RESERVED_WORDS.html
