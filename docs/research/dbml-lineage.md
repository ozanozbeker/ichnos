# DBML lineage syntax and dbdiagram rendering

Answers [DBML lineage syntax and dbdiagram rendering](https://github.com/ozanozbeker/ichnos/issues/36).
It builds on the note for [DBML specification and tooling](https://github.com/ozanozbeker/ichnos/issues/20), on the branch [`research/dbml-spec`](https://github.com/ozanozbeker/ichnos/blob/research/dbml-spec/docs/research/dbml-spec.md), and does not repeat its facts about `Ref`, custom properties, names or tooling.
Below, "the earlier note" means that note.

DBML calls one `upstream -> downstream` pair in a `Dep` an edge, and this note uses its word.

## Answers

- **First release.**
  `@dbml/core`, `@dbml/parse` and `@dbml/cli` 10.0.0, published 2026-08-10, are the first stable releases that parse `Dep`.
  9.1.1 rejects it.
  The current release, 11.0.1, accepts each short and inline form on the syntax page.
  It rejects the page's block example, because that block mixes table-level and column-level edges, and every release from 10.0.0 on forbids that.
- **Unique edges.**
  The rule holds across the whole file, not within one block.
  The parser keeps one set of edges for all short, block and inline forms, and a repeat raises `Dep with same endpoints already exists`.
  `a -> b` and `b <- a` are the same edge.
  A reversed pair and the same tables at a different level are distinct edges.
  dbdiagram runs the same parser, so a duplicate is an error there too, but I did not check it in the editor.
- **Custom keys.**
  A short-form `Dep` takes `note`, `color` and any custom key, after the edge or between its name and the colon.
  An inline `dep:` setting takes none: a key beside it belongs to the table or column.
  A block merges the keys of every edge line into one set for the whole block, so a key cannot describe one edge of a block.
  Dep keys read values differently from table custom properties: a negative number or a color is dropped, and a boolean becomes a string.
  Use single-quoted strings and non-negative integers only.
  The docs do not say how dbdiagram shows a `Dep`'s custom keys, and I did not check.
- **Reports.**
  A report must be a `Table`, because a `Dep` endpoint must be a table or a column.
  A table custom property such as `kind: 'report'` works on every dbdiagram plan.
  A `TableGroup` and `headercolor` also parse, but the dbdiagram docs list both as Personal Pro features.
  A table with no `Ref` parses with no error and no warning.
  I did not check how dbdiagram draws it.
- **Large diagrams.**
  The docs describe no automatic layout for lineage.
  They say to put each pipeline stage in a `TableGroup`, and to click a column to show its lineage across every hop.
  A `DiagramView` filters tables, notes, groups and schemas, and has no lineage category.
  The detail levels pages do not mention lineage.
  A release note says that dbdiagram draws `Ref` and `Dep` as different edge styles and can show them together or apart.
- **Self-dependencies and cycles.**
  `t -> t`, `t.a -> t.b` and every cycle that I tried parse with no error and no warning.
  `t.a -> t.a` is an error.
  The docs do not say how dbdiagram draws a self-dependency or a cycle, and I did not check.

## Versions and method

All reads and runs happened on 2026-11-02 with Node 26.12.0 on macOS arm64.
A probe is one DBML text and one call to `new Parser().parse(text, "dbmlv2")`.
Accept means that the parser returns a model and reports no error.
Each tested release has its own install directory, with `@dbml/core` and `@dbml/parse` pinned to the same exact version through npm `overrides`.
The experiment scripts are not committed.

| Source | Version or date | Use |
| --- | --- | --- |
| [DBML data lineage page](https://dbml.dbdiagram.io/syntax/data-lineage) | Live site; source `dbml-homepage/docs/syntax/data-lineage.md`, last changed 2026-08-10 | Syntax reference |
| [dbdiagram data lineage page](https://docs.dbdiagram.io/data-lineage/) | Read 2026-11-02 | Rendering and use cases |
| [dbdiagram release note on data lineage](https://docs.dbdiagram.io/release-notes/2026-08-data-lineage) | 2026-08-21 | Rendering and plan limits |
| dbdiagram pages on [diagram views](https://docs.dbdiagram.io/diagram-views/), [detail levels](https://docs.dbdiagram.io/diagram-detail-levels/), [table groups](https://docs.dbdiagram.io/table-groups/), [header color](https://docs.dbdiagram.io/table-header-color/) and [custom properties](https://docs.dbdiagram.io/custom-properties/) | Read 2026-11-02 | Views, levels and plan limits |
| [`holistics/dbml`](https://github.com/holistics/dbml) | Tag `v11.0.1`, commit `87c0f4e`; the cited files match `master` at `0418f4b` | Parser source, tests and `CHANGELOG.md` |
| `@dbml/core` and `@dbml/parse` | 9.1.1, 10.0.0, 10.1.1, 10.2.0, 10.3.1, 11.0.0, 11.0.1 | 91 probes on each release, 36 more on 11.0.1, and `compiler.parse.warnings` for the self-dependency and cycle cases |
| `@dbml/cli` | 9.1.1, 10.0.0, 11.0.1, run with `npx -p @dbml/cli@<version> dbml2sql` | CLI behaviour |

I did not open the dbdiagram editor.
Every statement about how dbdiagram draws lineage comes from its docs, and the [gaps](#not-verified-in-the-dbdiagram-editor) list what they leave out.

## Release history

| Release | npm date | `Dep` |
| --- | --- | --- |
| 9.1.1 | 2026-07-31 | Rejected. `Dep: a -> b` raises `A Custom element can only appear in a Project`. |
| 10.0.0 | 2026-08-10 | First stable release that parses it, from the pull request [Data dependency](https://github.com/holistics/dbml/pull/933). |
| 10.2.0 | 2026-09-23 | A custom key with a block value, such as `owner { 'a' }`, became an error. 10.0.0 and 10.1.1 accepted it and dropped the key. |
| 11.0.0 | 2026-10-26 | A second `note` in one setting list became an error. 10.x kept the first. |
| 11.0.1 | 2026-11-02 | Only an error message changed. `CHANGELOG.md` dates this release 2026-10-26, but npm published it on 2026-11-02. |

The other 88 probes gave the same result on all six releases from 10.0.0 to 11.0.1.

The first commit for `Dep` ("ft(wip): support dep syntax", 2026-06-10) is in the prerelease tags from `v9.0.0-alpha.0` (2026-06-16) on.
npm published those under the `alpha` tag, and I did not test them.

`@dbml/cli` shares the version number, and 10.0.0 is its first release that parses `Dep`.
Its dependencies use caret ranges, such as `"@dbml/core": "^10.0.0"`, so a fresh install of `@dbml/cli@10.0.0` today runs the newest 10.x parser.
`dbml2sql` from 10.0.0 and 11.0.1 accepts a file of `Dep` lines and writes no SQL for them.
On a duplicate edge it prints `dup.dbml(11,3): Dep with same endpoints already exists`, writes `dbml-error.log` and exits with code 0, as it does for every parse error.

## The forms on the syntax page

Every result is from 11.0.1, and 10.0.0 gave the same.

| Form | Example from the page | Result |
| --- | --- | --- |
| Short, table level | `Dep: raw_orders -> stg_orders` | Accepted |
| Short, `<-` arrow | `Dep: stg_orders <- raw_orders` | Accepted. The model stores it as `raw_orders -> stg_orders`. |
| Short, column level | `Dep: raw_orders.amount -> stg_orders.revenue` | Accepted |
| Short, table to column | `Dep: stg_orders -> fct_orders.revenue` | Accepted |
| Short, column to table | `Dep: raw_events.payload -> stg_events` | Accepted |
| Inline on a table and a column | `Table fct_orders [dep: <- stg_orders]` and `revenue decimal [dep: -> report_revenue.total]` | Accepted |
| The short-form snippet as one file | All of the above | Rejected. Its first two lines are one edge, so the second raises `Dep with same endpoints already exists`. |
| Block | `Dep order_staging [color: #79AD51] { raw_orders -> stg_orders ... raw_orders.amount -> stg_orders.revenue ... }` | Rejected with `All edges in a Dep block must be at the same level (all table-level or all column-level)` |
| Block, table-level edges only | The same block without the column edge | Accepted, with its note, color and three custom keys |

The page states one block rule: every edge targets the same downstream table.
The parser enforces a second rule that the page does not state: every edge in a block is at the same level ([source](https://github.com/holistics/dbml/blob/v11.0.1/packages/dbml-parse/src/core/global_modules/program/utils/dep.ts#L42-L53)).
An edge is table-level only when neither end names a column.
So `t -> u.c` and `t.a -> u.c` can share a block, and `t.a -> u` and `t -> u` cannot.
The rule came in the commit "disallow mixed table and column level in deps" on 2026-07-20, three weeks before the page took its current text.

Other official samples:

- The four complete examples on the [dbdiagram lineage page](https://docs.dbdiagram.io/data-lineage/) parse in 10.0.0 and 11.0.1.
  They use only short forms, inline forms and blocks at one level.
- The lineage sample in the DBML playground (`dbml-playground/src/services/sample-content.ts`) is rejected for the same reason as the short-form snippet.
  Its line 33, `Dep: fct_orders <- stg_orders`, repeats an edge that a block above it declares.
- The test file `packages/dbml-core/__tests__/examples/normalized_model/dep_pipeline.in.dbml` parses, with 31 `Dep` elements.

### Endpoints

- An endpoint is a table or one column: `t`, `t.c`, `owner.t` or `owner.t.c`, quoted or not.
  Quoted Oracle names such as `"HR"."EMP$HIST"."EMPLOYEE_ID"` work, and a table alias resolves to its table.
- A composite endpoint is an error.
  `Dep: t.(a, b) -> u.(x, y)` raises `Table 'a' does not exist in Schema 'public'`, an error that does not name the real cause.
  A dependency that reads two columns needs two edges.
- A missing table or column is an error.
  A `TableGroup` is not an endpoint.
- A `Dep` may come before its tables, and must be top-level.
  Inside a `Project` it raises `A Dep must appear top-level`.
- A `Ref` and a `Dep` may join the same two columns, and neither raises.
- An inline `dep:` on a table takes a table: `<- t` or `<- owner.t`.
  `[dep: <- t.a]` on a table reads `t` as the owner and raises `Schema 't' does not exist in Schema 'public'`.
- An inline `dep:` on a column takes a column: `<- t.a` or `<- owner.t.a`.
  A bare name such as `[dep: <- a]` fails, in the parser when `a` is not a column of the same table, and in `@dbml/core` with `Can't find table "" referenced in Dep edge` when it is.
  So an inline `dep:` cannot write a table-to-column or column-to-table edge.
- A `Dep` in one file may name tables that the file imports with `use` from another file, according to the upstream test `packages/dbml-parse/__tests__/examples/interpreter/multifile/dep.test.ts`.
  I did not check how dbdiagram handles a project of several files.

## Duplicate edges

The parser keeps one set of edges for the whole file ([source](https://github.com/holistics/dbml/blob/v11.0.1/packages/dbml-parse/src/core/global_modules/program/interpret.ts#L170)).
The key is the upstream owner, table and columns plus the downstream owner, table and columns.
A second edge with the same key raises `Dep with same endpoints already exists` (`CompileErrorCode.SAME_ENDPOINT`, 5002).

| Case | Result |
| --- | --- |
| The same short form twice | Error |
| `a -> b` and `b <- a` | Error |
| The same edge twice in one block | Error |
| The same edge in two blocks | Error |
| A short form and a block | Error |
| An inline `dep:` and a short form | Error |
| The same edge with different settings | Error |
| The same column edge twice | Error |
| `a -> b` and `b -> a` | Accepted |
| `a -> b`, `a.x -> b.y`, `a -> b.y` and `a.x -> b` together | Accepted. They are four levels of one table pair. |
| Two blocks with one downstream table | Accepted |
| Two blocks with one name | Accepted. A `Dep` name is not unique. |

The page's rule "Each directed edge must be unique" therefore holds across the file.
The docs do not say what dbdiagram does with a duplicate.
The note for [DBML specification and tooling](https://github.com/ozanozbeker/ichnos/issues/20) found that dbdiagram runs the official parser and that an error leaves the canvas on the last valid diagram.
So a duplicate edge most likely stops the diagram from updating until it is removed.
I did not check this in the editor.

## Settings and custom keys

| Form | Where settings go | What the `Dep` keeps |
| --- | --- | --- |
| Short | `Dep name [k: v]: a -> b`, `Dep name: a -> b [k: v]`, or both lists at once. The name is optional. | `name`, `note`, `color`, custom keys |
| Block | The header `Dep name [k: v] { }`, `k: v` lines in the body, and a `[k: v]` list after any edge line | `name`, `note`, `color`, custom keys, all for the whole block |
| Inline | None | Only the edge. `[dep: <- t [k: v]]` raises ``'dep' must be `-> target` or `<- source` ``, and `[dep: <- t, k: v]` gives `k` to the table or column. |

`note` takes a quoted string, and 11.0.0 and later allow it once per setting list.
`color` takes a hex color.
`Note { 'text' }` works as a body line in a block.

A block has one set of custom keys.
The parser reads the header list, then the list after each edge line in order, then the body lines, and a later key overwrites an earlier one ([source](https://github.com/holistics/dbml/blob/v11.0.1/packages/dbml-parse/src/core/global_modules/dep/interpret.ts#L108-L208)).
So `a -> b [owner: 'x']` and `c -> b [owner: 'y']` in one block give the block `owner: 'y'`, and the first edge loses its key.
Evidence for one edge needs a short-form `Dep` of its own.

Dep keys go through their own reader, not the one for table custom properties, and it accepts different values:

| Written | Stored in the `Dep` | A table custom property in 11.0.x |
| --- | --- | --- |
| `'text'`, `"text"` or `'''text'''` | The string. A multi-line string keeps its indentation, unlike `note`. | The string |
| `3` or `1.5` | A number | A number |
| `-1` | Nothing. The key is dropped with no error. | `-1` |
| `#112233` | Nothing, except for `color` | A color |
| `true` or `false` | The string `'true'` or `'false'` | A boolean |
| A bare word, such as `table` | The string `'table'` | An error |
| `a.b` | An error | An error |
| A key with no value | Nothing. The key is dropped with no error. | An error |
| A key written twice | No error. The first wins within a list, and the last wins across lines. | An error |
| `QueryFile` | Stored as `queryfile` | Stored as `queryfile` |
| `query-file` | An error, `Expect an identifier` | An error |

The [DBML page](https://dbml.dbdiagram.io/syntax/data-lineage) says custom keys "are preserved in the output", and the [dbdiagram page](https://docs.dbdiagram.io/data-lineage/) says they "are kept with the dependency".
Neither says where dbdiagram shows them.
The [custom properties page](https://docs.dbdiagram.io/custom-properties/) lists tables, columns, table groups and sticky notes, and not `Dep`, so its property filter most likely does not list Dep keys.
I did not check either point in the editor.

`ModelExporter.export(db, "dbml")` writes every `Dep` as a block without its name, and writes keys in lower case.

A `Dep` name is optional.
It is an identifier or a quoted string, and a quoted name may hold a path and a colon, such as `"reports/sales_summary.sql"` or `"q1.sql:12"`.

## Self-dependencies and cycles

| Case | Result |
| --- | --- |
| `Dep: t -> t` | Accepted |
| `Dep: t.a -> t.b` | Accepted |
| `Dep: t.a -> t` and `Dep: t -> t.b` | Accepted |
| `t.a -> t.b` and `t.b -> t.a` in one block | Accepted |
| `Table v [dep: <- v]` | Accepted |
| `Dep: t.a -> t.a` | `A column cannot depend on itself` ([source](https://github.com/holistics/dbml/blob/v11.0.1/packages/dbml-parse/src/core/global_modules/dep/bind.ts#L76-L94)) |
| `a int [dep: <- v.a]` in table `v` | `@dbml/parse` accepts it, and `@dbml/core` then raises `Self-loop Dep edge not allowed: "public"."v" columns cannot depend on itself`, with no error code |
| A cycle of two or three tables, or of two columns | Accepted |

`@dbml/parse` 11.0.1 reports no warning for any of these, or for a table that only `Dep` lines touch.

An `UPDATE` such as `SET a = a + 1` gives `t.a -> t.a`, which DBML cannot hold.
[Lineage inference rules](https://github.com/ozanozbeker/ichnos/issues/35) decides whether ichnos keeps such a dependency.
If it does, the writer must put it somewhere other than a `Dep`, such as a custom key on the column.

The docs do not say how dbdiagram draws a self-dependency or a cycle.

## Marking a report

[Report names and columns](https://github.com/ozanozbeker/ichnos/issues/34) records that a report is a query that reads tables and writes none.
In DBML it has to be a `Table`, because a `Dep` endpoint must be a table or a column.
Each mark below parses in 11.0.1.

| Mark | DBML | On dbdiagram |
| --- | --- | --- |
| Table custom property | `Table rpt [kind: 'report', query_file: 'reports/sales.sql']` | Every plan. The earlier note found that the property filter lists table-level keys. |
| Table group | `TableGroup reports [color: #E67E22] { rpt_sales rpt_hr }` | Personal Pro, per the [table groups page](https://docs.dbdiagram.io/table-groups/). A table joins one group at most, so a report in `reports` cannot join a layer group. |
| Header color | `Table rpt [headercolor: #E67E22]` | Personal Pro. The earlier note found that the Free editor accepts it and leaves the header unchanged. |
| Note | `Table rpt [note: 'Report: reports/sales.sql']` | Every plan. Notes render as Markdown. |
| A separate owner | `Table "REPORT"."sales_summary"` | A `DiagramView` can select it with `Schemas { REPORT }`. Report names and columns decides which owner a report takes. |

A report table needs at least one column, because an empty table raises `A Table must have at least one column`.
A placeholder such as `"*" unknown` works when the select list is unknown.

A table with no `Ref` parses with no error and no warning in 11.0.1.
The earlier note found that every warning comes from a `Ref` cardinality check.
The docs do not mention such a table, and I did not check how dbdiagram draws it.

This text parses in 11.0.1 with no error and no warning.
The keys `kind`, `query_file` and `evidence_count` are placeholders.

```text
Table t {
  a int
}

Table u {
  x int
}

Table "REPORT"."sales_summary" [kind: 'report', query_file: 'reports/sales_summary.sql'] {
  "TOTAL" unknown
  "COUNT(*)" unknown
}

Dep "reports/sales_summary.sql" [query_file: 'reports/sales_summary.sql', evidence_count: 1] {
  t -> "REPORT"."sales_summary"
  u -> "REPORT"."sales_summary"
}

Dep: t.a -> "REPORT"."sales_summary"."TOTAL" [query_file: 'reports/sales_summary.sql']
Dep: u -> "REPORT"."sales_summary"."COUNT(*)" [query_file: 'reports/sales_summary.sql']
```

## Large diagrams, views and detail levels

The docs say:

- Data lineage "is available on all plans, with no limit on project size" ([release note](https://docs.dbdiagram.io/release-notes/2026-08-data-lineage)).
- dbdiagram draws `Ref` and `Dep` as different edge styles, "so you can show them together or separately" (same release note).
  No page says where that control is or whether a view saves it.
- Clicking a column shows its lineage across every hop ([lineage page](https://docs.dbdiagram.io/data-lineage/) and the release note).
- To lay a pipeline out by layer, put each stage in a table group (lineage page).
  Table groups are a Personal Pro feature.
- `color` on a `Dep` sets the color of its lineage lines.

The docs say nothing about automatic layout for lineage, or about how dbdiagram places hundreds of tables.
dbdiagram saves table positions with the diagram, and the [dbdiagram CLI](https://docs.dbdiagram.io/cli/) keeps them in a `.dbdiagram` file beside the DBML.

A `DiagramView` selects `Tables`, `Notes`, `TableGroups` and `Schemas`.
Any other block, such as `Deps { * }`, raises `Unknown block type "Deps" in DiagramView. Allowed: Tables, Notes, TableGroups, Schemas` ([source](https://github.com/holistics/dbml/blob/v11.0.1/packages/dbml-parse/src/core/local_modules/diagramView/validate.ts#L172-L191)).
So a view in DBML can show a subset of tables, but it cannot show lineage apart from the ERD.
Named views need a paid plan, and Free has the default view only ([diagram views page](https://docs.dbdiagram.io/diagram-views/)).

The detail levels are Table Names, Keys Only and All Fields, on Personal Pro ([detail levels page](https://docs.dbdiagram.io/diagram-detail-levels/)).
The page does not mention lineage, so it does not say how a column-level `Dep` is drawn when its column is hidden.

`@dbml/core` 11.0.1 parses 600 tables with 2396 `Dep` elements (110 KB) in 180 ms.
The earlier note found that the anonymous editor accepts 400 tables.
Neither number says how the canvas looks at that size.

## What this means for the writer

These rules follow from the measurements, for [DBML output with evidence](https://github.com/ozanozbeker/ichnos/issues/12) to adopt or reject:

- Test against `@dbml/core` 11.0.1. `Dep` text that follows these rules parses the same in every release from 10.0.0 on.
- Remove duplicate edges across the whole file before writing, keyed on both endpoints with their owners and columns, and merge their evidence.
- Write every edge with `->`. Never write the same edge with both arrows.
- Do not mix table-level and column-level edges in one block.
- Write a short-form `Dep` for each edge that carries its own evidence. A block's keys describe the block.
- Write custom key values as single-quoted strings or non-negative integers, with lower-case snake_case keys, each once.
- Do not use inline `dep:`. It takes no keys, and its column form raises on a bare column name.
- Drop `t.a -> t.a`, or record it outside `Dep`.
- Mark a report with a table custom property, which works on every plan.

## Not verified in the dbdiagram editor

I did not open the editor, so these are unchecked:

- What the editor shows for a duplicate edge.
- How it draws a self-dependency, a cycle, a table-to-column edge and a block's `color`.
- Where it shows a `Dep`'s name, note and custom keys, and whether the property filter lists Dep keys.
- Where the control that shows `Ref` and `Dep` apart is, and whether a view saves it.
- How lineage looks at a detail level that hides columns, and with hundreds of tables.
- How it draws a report table that has no `Ref`.
- Whether it handles a lineage file that imports the ERD's tables with `use`.
