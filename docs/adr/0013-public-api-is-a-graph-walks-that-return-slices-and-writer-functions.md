# The public API is a graph, walks that return slices, and writer functions

One call builds an immutable `Graph` from a corpus.
Its walks return a `Slice`, and module-level functions write DBML and the summary.
The CLI uses this API alone, so a Python caller gets every result the CLI prints, as data as well as text.
Every module stays private, and `ichnos/__init__.py` re-exports the names below ([issue 16](https://github.com/ozanozbeker/ichnos/issues/16)).

## Building a graph

`infer(files: Mapping[str, str]) -> Graph` takes each file's text under a key that names the file.
A query's name is the key as given, plus `#N` when the text holds several queries ([ADR 0009](0009-reports-take-their-file-name-and-output-columns-take-oracles-name.md)).
`infer` raises `IchnosError` when two queries get the same name, such as a one-query key `a#1` beside a two-query key `a`.

`read(folder) -> Graph` builds each key from the file's path relative to the folder, without the extension, with `/` between folders.
It raises `IchnosError` on two files with one key, such as `x.sql` and `x.txt`, and then calls `infer`.
Which files `read` reads and how it decodes them is a rule of `read`, so the CLI and a library caller read the same files.
The [CLI surface](https://github.com/ozanozbeker/ichnos/issues/15) ticket sets that rule.

The API never receives text without a name.
A caller with one string writes `infer({"q": sql})`.
Parsing and inference are one step, and `_read`'s records stay private.
`Graph` is a frozen dataclass, and nothing adds queries to it later.

## Records

`Graph` holds `tables`, `reports`, `relationships`, `dependencies`, `rollups`, `ambiguities`, `queries` and `unparsed`, each a tuple.
Every record is a frozen dataclass from stdlib `dataclasses`.
Records point at each other as objects, such as `column.table`, `report.query` and `dependency.upstream`.
They compare and hash by name only: a table by its owner and name, a column by its table and name.
Otherwise `Table.columns` and `Column.table` form a cycle that breaks `==`, `hash` and `repr`.

A `Query` is one query of the corpus: its `name`, `file`, `position` and `text`.
`graph.queries` lists every query that ichnos read, by file key and then by position, including one such as 032 that records nothing.
`graph.unparsed` lists `UnparsedQuery(name, file, position, text, error)`, a separate type because no evidence points at one.

Each claim maps each evidence kind to the `Query` records behind it.
A count is the number of distinct texts among them, so two files with the same text give two records and a count of 1 ([ADR 0001](0001-evidence-counts-and-no-attribution-on-ambiguity.md)).
The records mirror the properties of [ADR 0011](0011-dbml-evidence-as-custom-properties-in-one-file.md), grouped by claim:

- `Table` holds `owner`, `name`, `columns`, `keys`, its `read`, `write` and `declared` evidence, `declarations`, `kind`, `complete`, `contradictions` and `ambiguities`.
  `columns` follows ADR 0011's order: declared order, then undeclared columns by name.
- `Declaration(kind, columns, queries)` is one distinct declaration, with `columns` in declared order.
  Two matching creating queries give one `Declaration` with two queries ([ADR 0008](0008-declarations-settle-ambiguities-until-contradicted.md)).
- `Table.kind` is a `TableKind` or `None`.
  It is `None` with no declaration, or when the declarations differ in kind, which an ambiguity records.
- `Contradiction(query, reason, column)` takes `reason` from `"undeclared column"`, `"declaration"` and `"value count"`.
  A table with any contradiction has every declaration contradicted.
- `Column` holds `references` by position, `declared`, `types`, `nullable`, `observed` and `undeclared`.
  `observed` maps every observed value, as its SQL literal text, to its queries.
  The writer caps the list at 20 ([ADR 0003](0003-literals-give-types-and-observed-values-never-an-enum.md)).
- `Key` holds `columns`, `name_match` (the pattern, or `None`) and its evidence by shape ([ADR 0006](0006-keys-from-name-matches-and-four-query-shapes.md)).
- `Relationship` holds two column tuples, `direction`, `shared` and its `join` evidence.
  `direction` is the `Key` that the first side refers to, or `None`, and with `None` the sides go in name order.
  `shared` is the third table's key column for a shared reference ([ADR 0002](0002-relationships-from-bare-equality-direction-from-key.md)).
- `Report` holds `name`, `query` and `output_columns`, and `OutputColumn` holds `name`, `position` and `types`.
- `Dependency` holds `upstream`, `downstream` and `subtypes`, which maps each `Subtype` to its queries.
  `Subtype` takes OpenLineage's uppercase names, as `answer_key/lineage.csv` does ([ADR 0010](0010-lineage-from-clause-positions-with-openlineage-subtypes.md)).
  `direct` and `indirect` say whether it holds any direct or any indirect subtype, and one dependency can hold both.
- `Rollup` holds `upstream`, `downstream`, `queries` and the dependencies it rolls up.
- `Ambiguity` holds `kind`, `query` and `candidates`, each candidate with its own evidence from other queries.
  `kind` is `"column"`, `"owner"`, `"declaration"`, `"type"` or `"dependency"`.
  `query` is `None` for `"declaration"` and `"type"`, which span queries.
  `graph.ambiguities` lists every one, and each table, column and output column that one touches lists it too.

The graph has no filter methods.
A caller filters with a comprehension, such as `[d for d in graph.dependencies if "FILTER" in d.subtypes]`.

## Lookups

`graph.table("sales.orders")` parses the name as Oracle does.
An unquoted part becomes uppercase, a quoted part keeps its case, and `@link` stays part of the name, so `X` and `MART.X` stay different tables.
`table.column(name)`, `graph.report(name)` and `report.output_column(name)` look up the rest, and output column names compare in dictionary form.
A missing name raises `KeyError`.
No single dotted string names every start, because `MART.X` could be a table or a column `X` of an unowned table `MART`, and a report name can hold a `.`.

## Walks

Each walk takes records, never strings, and returns a `Slice` ([ADR 0012](0012-llm-output-as-dbml-slices-under-a-character-budget.md)):

- `graph.neighborhood(tables, depth=1)`.
- `graph.join_path(tables)`.
- `graph.upstream(start, indirect="first_hop")`, where `start` is a `Table`, `Column`, `Report` or `OutputColumn`.
- `graph.downstream(start, indirect="first_hop")`, where `start` is a `Table` or `Column`.

A `Slice` holds what the writer needs and nothing the writer computes.
It holds `kind`, `starts`, `depth`, `indirect`, the `distances` of each table and report from the start, the kept `columns` per table, `relationships`, `dependencies`, `rollups`, the `outside` names of ADR 0012's header, and the `unconnected` tables of a join path.
The cut order lives in the writer, so a `Slice` never changes with the budget.

## Writers

`_dbml` and `_llm` sit above the graph module, so the writers are functions, not `Graph` methods:

- `dbml(graph)` writes the full DBML file.
- `dbml(slice, budget=8000, detail="compact", examples=False)` writes a slice with its header and its cut order.
- `summary(graph, owner=None, keyword=None, budget=8000)` writes the summary.

Keyword search exists only as `summary(keyword=...)`.

## Errors

`IchnosError` is the one public exception.
`infer` and `read` raise it on a name clash, and `dbml` raises it on an Oracle owner named `report`.
Lookups raise `KeyError`, and a missing folder raises Python's own `OSError`.
So the CLI can tell a user error from a bug.

## Public names

- Functions: `infer`, `read`, `dbml` and `summary`.
- Classes: `Graph`, `Slice`, `Query`, `UnparsedQuery`, `Table`, `Column`, `Key`, `Relationship`, `Report`, `OutputColumn`, `Dependency`, `Rollup`, `Declaration`, `Contradiction`, `Ambiguity` and `IchnosError`.
- `Literal` aliases: `TableKind`, `Type`, `Position`, `KeyShape`, `Subtype`, `AmbiguityKind`, `ContradictionReason`, `SliceKind`, `Indirect` (`"first_hop"` or `"all"`) and `Detail` (`"compact"` or `"full"`).

The records are public for annotations and `isinstance`.
Only `infer` and `read` build them.
`Type` keeps the glossary's term, because `typing.Type` is deprecated.

## Considered options

- `Inference` or `Catalog` as the name of the graph.
  Rejected because `Catalog` suggests Oracle's data dictionary, and the ADRs already say "the graph".
- `infer` also takes a bare `str` under a default name.
  Rejected because it gives one input two shapes for the cost of one dict.
- A public `parse` step.
  Rejected because nothing in v1 needs the parsed records apart from the graph.
- Counts only, with no queries behind them.
  Rejected because example queries need the queries behind each `Ref`, and a caller asks which queries support a claim.
- A `Query` record that merges identical text.
  Rejected because the glossary counts two files with the same text as two queries and two reports.
- `graph.dbml()` and other writer methods.
  Rejected because the graph module would import `_dbml` and `_llm`, which sit above it.
- Walks that return text.
  Rejected because a Python caller could not get the lineage as data.
- A walk that returns a smaller `Graph`.
  Rejected because it loses the distances and roles that the cut order needs.
- One dotted string for any start.
  Rejected for the reasons under **Lookups**.
- Records that hold names, looked up through the graph.
  Rejected because every caller would repeat the lookups.
- Filter methods on the graph by subtype or by direct and indirect.
  Rejected because a comprehension over `subtypes` does the same with nothing new to learn.
- `graph.search(keyword)`.
  Rejected for v1, because only the summary uses it, and the TUI can add it.
