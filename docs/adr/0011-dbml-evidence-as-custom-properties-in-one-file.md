# DBML output writes evidence as custom properties, in one file with the lineage

ichnos writes one DBML file that holds the inferred schema, the reports and the lineage.
It writes the text directly ([issue 20](https://github.com/ozanozbeker/ichnos/issues/20)), and every file must parse with no error and no diagnostic in the `@dbml/core` that `tests/dbml/package-lock.json` pins ([ADR 0015](0015-tests-score-the-answer-key-through-deviation-lists-and-parse-dbml-with-dbml-core.md)).
A prototype on the branch [`prototype/dbml-output`](https://github.com/ozanozbeker/ichnos/tree/prototype/dbml-output/prototypes/dbml_output) wrote the synthetic corpus three ways: as custom properties, as notes and as comments.
The measurements below come from that prototype and from the dbdiagram editor on 2026-11-03.

## Evidence

Every evidence count is a custom property.
Its key is the evidence kind in lowercase, and its value is a non-negative integer.
A count of 0 is not written.

- A table takes `read`, `write` and `declared`.
- A column takes `declared`, one key per reference position (`select`, `where`, `join`, `group_by`, `order_by`, `aggregate`, `insert` and `set`), one key per type (`text`, `number`, `datetime` and `interval`), and `nullable`.

A flag or a list is a single-quoted string property: `keys`, `observed`, `ambiguity`, `contradicted` and `self_dependency`.
`observed` joins up to 20 values with a comma and a space, and a value that holds a comma, or starts or ends with a space, takes its SQL literal form.
A column with more than 20 observed values takes `observed_count` instead ([ADR 0003](0003-literals-give-types-and-observed-values-never-an-enum.md)).
DBML raises on a key written twice, so two ambiguities on one element join with a semicolon and a space in one `ambiguity`.

dbdiagram's hover card lists a table's or a column's custom properties, one per line.
Its property filter lists table keys only ([issue 20](https://github.com/ozanozbeker/ichnos/issues/20)).
It shows no index note, no `null` setting and no `Dep` key.

## Keys

ichnos never writes `pk`, because it never claims a primary key ([ADR 0006](0006-keys-from-name-matches-and-four-query-shapes.md)).
Each key is an `indexes` entry with `unique`.
The table property `keys` gives each key's basis and counts, because dbdiagram shows no index note:

```text
Table INV.WAREHOUSES [read: 3, keys: 'ID: name match ID; WAREHOUSE_CODE: name match <S>_CODE'] {
Table INV.STOCK_LEVELS [read: 3, write: 2, keys: '(PRODUCT_ID, WAREHOUSE_ID): merge 1'] {
```

## Columns

A column's type is `text`, `number`, `datetime` or `interval` ([ADR 0007](0007-types-from-fixed-type-expressions-and-nullable-only.md)).
DBML requires a type, so a column with no type evidence takes `unknown`.
A column with two types takes them quoted and joined by `|` in that fixed order, such as `"text|number"`, with each type's count beside it.

A nullable claim writes DBML's `null` setting and the `nullable` count.
A column with no claim writes neither, and no column writes `not null`.
DBML reads both as nullable, so the `nullable` count is the only visible mark in dbdiagram.

A declared table lists its declared columns in declared order, then its undeclared columns by name.
Every other table lists its columns by name, so the output stays the same across runs.
A table with no known column, such as one that only `COUNT(*)` reads, takes the placeholder column `"*" unknown`, because DBML raises on an empty table.

## Declarations

A declared table takes `kind` (`'base table'`, `'view'` or `'materialized view'`) and `declared` ([ADR 0008](0008-declarations-settle-ambiguities-until-contradicted.md)).
It takes `complete: true` while its column list is complete.
A declared column takes `declared`, and an undeclared column takes `undeclared: true`.
A contradicted declaration loses `complete` and takes `contradicted`, which names the contradiction.
Two declarations that differ write both kinds in `kind`, such as `'base table|view'`, and an `ambiguity`.

## Relationships

A relationship with a known direction is `>?` from the referring side to the key side.
`>?` to a `unique` index gives no diagnostic, and a referring column needs `?` because ichnos never claims `not null`.
A relationship with no direction is `?<>?`, with its sides in name order.
It gives no diagnostic, while `<>` gives 4 and `-` gives 6 on the same columns.
A composite relationship is `t.(a, b) >? u.(x, y)`.

A `Ref` takes no custom property, so its evidence goes in its quoted name, such as `Ref "join 6"`.
A shared reference adds its key, such as `Ref "join 1, shared reference to INV.PRODUCTS.PRODUCT_ID"`.
dbdiagram labels a `Ref` line with its name while a column at either end is hovered.

## Ambiguities

An ambiguity is an `ambiguity` property on every candidate table, which lists each candidate with its count ([ADR 0001](0001-evidence-counts-and-no-attribution-on-ambiguity.md)).
It names its query as a report's name does ([ADR 0009](0009-reports-take-their-file-name-and-output-columns-take-oracles-name.md)).
A table-level key reaches dbdiagram's property filter, and a column that exists on no candidate still has a place.
A dependency ambiguity goes on its downstream column or output column.
A table with no owner takes an `ambiguity` that names its qualified namesakes.

## Names

A name is quoted only when it holds a character other than a letter, a digit or `_`, or starts with a digit.
`NOTE`, `REF`, `INDEXES`, `TABLE` and `CHECKS` parse unquoted as column names.
The escape table from [issue 20](https://github.com/ozanozbeker/ichnos/issues/20) escapes every quoted name and string.

An owner is a DBML schema.
A table with no owner is written bare, so DBML puts it in its default schema.
A report is a table in the schema `report`, with `kind: 'report'` and its output columns in position order, each with its type.
Only a quoted lowercase Oracle owner can be named `report`, and ichnos raises an error that names it if the corpus holds one.

## Lineage

The lineage follows the schema in the same file.
dbdiagram's "Link type" switch shows the `Ref` lines, the `Dep` lines or both, so one file serves both views.
The file's order is the `Project` block, the tables, the `Ref` lines, the reports, the self-dependencies and the `Dep` lines.

Each dependency is one short-form `Dep` with `->` ([issue 36](https://github.com/ozanozbeker/ichnos/issues/36)).
A block shares one set of keys across its edges, and an inline `dep:` takes no keys.
Each transformation subtype is a key with its count, such as `[identity: 2, filter: 1]` ([ADR 0010](0010-lineage-from-clause-positions-with-openlineage-subtypes.md)).

For each pair of a table and a table or report that a dependency joins, the output writes the rollup as its own `Dep`, with `queries` set to its count.
A dependency that ichnos stores at table level, from an unexpanded `*` or a `COUNT(*)` in a clause ([ADR 0010](0010-lineage-from-clause-positions-with-openlineage-subtypes.md)), shares that edge, so its subtype counts go beside `queries`.
`Dep` lines group by their downstream end, tables before reports, with the table-level line first.

DBML raises on `t.a -> t.a`.
So each self-dependency is a `Metadata Column` block in the lineage, whose `self_dependency` lists its subtypes and counts:

```text
Metadata Column MART.CUSTOMER_SEGMENTS.SEGMENT {
  self_dependency: 'TRANSFORMATION 1'
}
```

dbdiagram shows it on the column's hover card.
`t.b -> t.a`, `t.a -> t` and `t -> t` are valid `Dep` lines.

The `Project` block sets `database_type: 'Oracle'` and a note that explains `unknown`, `|`, `null`, `?<>?` and the schema `report`.

## Considered options

- One `note` per element.
  Rejected because a program has to parse the string, and dbdiagram shows it as one line.
- `//` comments.
  Rejected because the parser drops them, so dbdiagram and every DBML tool lose the evidence.
- One total count per column.
  Rejected because ADR 0001 reports counts by kind, and a `join` count shows a relationship that the ERD may lack.
- Lineage in its own file that imports the schema with `use`.
  It parses in `@dbml/core` 11.0.1, but the dbdiagram editor takes one file, and its switch already separates the views.
- Column-level dependencies only.
  Rejected because each reader would compute the table graph again.
- `pk` on one key.
  Rejected because it claims a primary key.
- Key evidence in an index note, or one property per key.
  Rejected because dbdiagram never shows an index note, and numbered keys split one claim across properties.
- `<>` or `-` for a relationship with no direction.
  Rejected because each claims a cardinality and raises diagnostics.
- Relationship evidence on the referring column.
  Rejected because a column in two relationships needs two keys, and a composite relationship has no single column.
- `unknown` plus an `ambiguity` for a column with two types.
  Rejected because `"text|number"` shows both types in the diagram.
- A `nullable` count with no `null` setting.
  Rejected because DBML tools read the setting.
- One sticky note that lists every ambiguity.
  Rejected because dbdiagram shows sticky notes only on paid plans.
- Every name quoted.
  Rejected because it costs tokens and reads worse.
- A placeholder schema for a table with no owner.
  Rejected because DBML's default schema already marks it.
- A self-dependency written inline on its column.
  Rejected because it puts a lineage fact in the schema section.
