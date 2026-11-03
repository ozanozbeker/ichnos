# sqlglot is the only parser, and a query is read whole or skipped

ichnos parses with sqlglot's Oracle dialect alone.
It has no parser seam, no fallback parser and no option to pick one.
sqloxide 0.61.1 parses 5.1x faster than pure-Python sqlglot 30.26.0, but sqlglot still parses and resolves a query in about 0.7 ms, so 10,000 queries take about 7 seconds.
On the synthetic mix, 178 of sqlglot's 179 failures are positional binds (`:1`), so a sqloxide fallback would add almost no coverage once that bug is fixed.
sqlglot also ships `optimizer.scope` and `lineage`, and sqloxide returns a raw tree that ichnos would have to resolve itself.

The package depends on pure-Python `sqlglot`, not `sqlglot[c]`.
The compiled build is 3x faster, but its wheel is 28.6 to 33.9 MB and its Linux wheels need glibc 2.28.
Where no wheel fits, it builds from source with a C compiler, which a locked-down machine usually lacks.
A user who wants the speed runs `uvx "ichnos[c]"`, whose extra installs `sqlglot[c]` ([ADR 0005](0005-runtime-dependencies-stop-at-the-newest-tested-release.md)).

ichnos never subclasses a sqlglot class.
With `sqlglotc` installed, a parse through a subclass of the Oracle dialect raises `TypeError: interpreted classes cannot inherit from compiled` (sqlglot 30.26.0, run on 2026-11-02).
A library user whose environment holds `sqlglotc` would hit that error.
A bug in sqlglot's own output goes upstream as a pull request, and ichnos waits for the release.
If implementation needs a fix before the release, a pre-pass rewrites the query text using sqlglot's tokenizer.
A rule that belongs to ichnos, such as dropping pseudocolumns, reads the tree after the parse.
sqlglot 30.26.0 reads `USER`, `UID`, `SESSIONTIMEZONE`, `DBTIMEZONE`, `ORA_INVOKING_USER` and `ORA_INVOKING_USERID` as columns, so that rule drops an unqualified one too.
These bugs in sqlglot 30.26.0 need an upstream fix:

- A positional bind such as `:1` raises.
- `CREATE MATERIALIZED VIEW` with a `BUILD`, `REFRESH` or `ON PREBUILT TABLE` clause, an `EDITIONABLE` or `EDITIONING` view, and `CREATE PRIVATE TEMPORARY TABLE` return an opaque `exp.Command`.
- `FOR UPDATE OF a.x` reads `x` as a table.
- `optimizer.scope` lists the self-reference of a recursive CTE as a base table, because Oracle writes no `RECURSIVE`.

One private module holds every use of sqlglot, and no other module imports it.
It splits each file into queries at `;` tokens and at lines that hold only `/`, parses each query strictly, and returns records that ichnos owns.
It reads one query at a time.
It resolves aliases, CTEs and derived tables within the query, and records an unqualified column in a scope with several sources as an ambiguity with its candidates.
Evidence counts and declarations from creating queries combine queries, so they live above the module.
The schema that `lineage()` needs comes from the query and from declarations ([ADR 0008](0008-declarations-settle-ambiguities-until-contradicted.md)), never from references in other queries, as ADR-0001 requires.
[Lineage inference rules](https://github.com/ozanozbeker/ichnos/issues/35) chooses between `lineage()` and ichnos's own tracing over `optimizer.scope`.

A query is read whole or not at all.
A parse that raises, a `Command` result, or a later step that raises makes the query an unparsed query, and the run continues.
So does a query that is not a `SELECT`, DML or a creating query, such as `ALTER TABLE` or `DROP`.
ichnos lists each unparsed query with its file, position and error.
It never uses the partial tree from `error_level=IGNORE`, because that tree can drop or invent columns with no sign.
SQL*Plus syntax other than `/`, such as `SET`, `PROMPT` or `&var`, is outside v1, and a query that holds it is unparsed.

The measurements come from [How does sqloxide perform on valid Oracle queries](https://github.com/ozanozbeker/ichnos/issues/18) and [Prior art for column lineage from SQL](https://github.com/ozanozbeker/ichnos/issues/31).

## Considered options

- sqloxide alone.
  Rejected because it has no scope or lineage helpers, and it raises on `ORDER SIBLINGS BY`, `KEEP (DENSE_RANK ...)` and `DBMS_LOB.SUBSTR`.
  Its recursion limit of 50 has no setting, and a chain of about 25,000 `OR` terms ends the process with SIGSEGV, which no `except` catches.
- Both parsers behind a seam, with the user picking one.
  Rejected because two resolvers must agree, and on 529 third-party queries they already differ on 40.
  Two adapters also double the test surface.
- sqlglot first, with sqloxide for the queries it rejects.
  Rejected because the two together read 99.7% of the synthetic mix against 96.4% for sqlglot, and the upstream fix for `:1` closes nearly all of that gap.
- A dependency on `sqlglot[c]`.
  Rejected for its size, its glibc floor and its C compiler fallback.
- A subclass of the Oracle dialect to fix `:1`.
  Rejected because it raises under `sqlglotc`.
- Keep a query's schema evidence when a step after the parse raises.
  Rejected because the evidence would be incomplete with no sign.
