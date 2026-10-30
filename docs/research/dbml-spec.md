# DBML specification and tooling

Answers [issue 20](https://github.com/ozanozbeker/ichnos/issues/20).

## Recommendation

Write the DBML text directly and add no DBML library to the runtime dependencies.
The subset that ichnos emits needs one escape table and a short list of structural rules, both given below.
A writer built on that table produced 2000 of 2000 realistic cases that the official parser read back unchanged.
PyDBML 1.2.1 changed the note text in 791 of the same 2000 cases, and neither Python library parses the current syntax.

Target the grammar of `@dbml/core` 11.0.0, the `dbmlv2` parser.
dbdiagram.io runs it.
On every probe that I ran in both places, the two agreed on accept and reject.

Attach evidence as custom properties.
A custom property keeps its string exactly and is available on all plans.
dbdiagram.io lists a column property in the column's hover card, but its property filter lists table-level keys only.
A `Ref` takes no note and no custom property, so put relationship evidence on the foreign key column.

Test emitted DBML with the official parser from Node, not with a Python library.
Both Python libraries accept text that the official parser rejects, and reject text that it accepts.

## Versions and method

All results come from experiments run on 2026-10-30 with Node 26.12.0 and Python 3.13.12 on macOS arm64.
A probe is one DBML text and one parse.
The experiment scripts are not committed.
In this note, accept means that a parser returns a model and reports no error.
Reject means that it reports at least one error.
A warning is not an error.

| Source | Version or date | Use |
| --- | --- | --- |
| [DBML docs](https://dbml.dbdiagram.io/docs) | Live site; source in `holistics/dbml` at tag `v11.0.0` | Syntax reference |
| `@dbml/core` and `@dbml/parse` | 11.0.0, released 2026-10-26 | Official parser, exporter and CLI. Probes call `new Parser().parse(text, "dbmlv2")`. |
| `@dbml/core` | 10.3.1, released 2026-10-09 | Bounds the version that dbdiagram.io runs |
| dbdiagram.io editor | Live on 2026-10-30, anonymous, Free plan | Probes pasted into the code editor of a new diagram. I read the error and warning lists. I did not sign in or save. |
| dbdiagram.io [release notes](https://docs.dbdiagram.io/release-notes/) and [pricing](https://dbdiagram.io/pricing) | Read on 2026-10-30 | Feature dates and plan limits |
| PyDBML | 1.2.1, released 2025-10-24 | Python parser and builder |
| lark-dbml | 0.7.0, released 2026-01-09 | Python parser and writer |

Source links in this note use the tag `v11.0.0`, which is commit `6e05001`.
The default branch was 46 commits ahead of it when I read it.
Those commits add index sort order and enum aliases to the docs, and the live site does not show them yet.

## What DBML allows

The docs have five pages: [core syntax](https://dbml.dbdiagram.io/docs), [enrichment and visualization](https://dbml.dbdiagram.io/syntax/enrichment-visualization), [data lineage](https://dbml.dbdiagram.io/syntax/data-lineage), [module system](https://dbml.dbdiagram.io/syntax/module-system) and [language basics](https://dbml.dbdiagram.io/syntax/language-basics).
ichnos emits tables, columns, composite keys, relationships and notes, so it needs `Project`, `Table`, columns, `indexes` and `Ref`.
The table lists each element with the limits that I found.

| Element | Settings | Limits that the parser enforces |
| --- | --- | --- |
| `Project` | `database_type: 'x'`, `Note: 'x'`, custom keys with string values | One per file. No setting list. The model keeps `name`, `databaseType` and `note`, and does not keep custom keys. |
| `Table` | `headercolor: #rgb`, `note`, custom properties, `as alias` | At least one column. One name per schema. A second `Note:` body is an error. |
| Column | `pk` or `primary key`, `null`, `not null`, `unique`, `increment`, `default: v`, ``check: `expr` ``, `note`, `ref: op table.column`, custom properties | A type is required. Repeating `pk`, `unique`, `default` or `note` is an error. `null` with `not null` is an error. |
| `indexes` entry | `pk`, `unique`, `type: btree` or `hash`, `name`, `note` | No custom properties. A missing column is an error. |
| `Ref` | `delete`, `update`, `color`, `inactive` | No `note`, no custom property, no `Metadata Ref`. The inline form takes no settings and no name. |
| `Enum` | A `note` on each value | No setting list on the enum. No custom property on a value. |
| `TableGroup` | `note`, `color`, custom properties | A table joins one group at most. |
| Sticky `Note name { }` | `color`, custom properties | None found. |
| `Metadata` | Custom properties for a `Table`, `Column`, `TableGroup` or `Note` | `Metadata Ref` and `Metadata Index` are errors. |
| `Dep`, `Records`, `TablePartial`, `DiagramView`, `use` | See the docs | ichnos does not need them. dbdiagram.io parses all five. |

A custom property is `key: value` in a setting list.
The key is an identifier.
The value is a string, number, boolean or color literal.
Version 10.3.1 accepts only strings and colors, and 11.0.0 added numbers and booleans.
The docs still list only strings and colors.
A key with no value, a bare-word value and a repeated key in any letter case are errors.

### Names, strings and types

- An unquoted name holds letters (any Unicode letter or mark), digits and `_`.
  `$`, `#`, `-` and spaces are errors, so Oracle names with `$` or `#` need quotes.
  A `.` separates a schema from a name.
  The official helper `addDoubleQuoteIfNeeded` quotes any name outside that set and any name that starts with a digit ([source](https://github.com/holistics/dbml/blob/v11.0.0/packages/dbml-parse/src/compiler/queries/utils.ts#L53-L58)).
- A `"quoted name"` stays on one line and may hold any other character.
  The lexer reads a backslash plus a character as an escape, so write `\"` for a quote and `\\` for a backslash.
- Names are case-sensitive.
  `Ref: posts.user_id > Users.id` is an error when the table is `users`.
- A `Ref` endpoint without a schema resolves to `public`.
  Every endpoint of a table in another schema needs its schema.
- A single-quoted string stays on one line.
  It reads `\\`, `\'`, `\"`, `\n`, `\t` and `\uHHHH`.
  An unknown escape such as `\d` drops the backslash.
  SQL-style doubling (`'it''s'`) is an error ([lexer](https://github.com/holistics/dbml/blob/v11.0.0/packages/dbml-parse/src/core/lexer/lexer.ts#L534-L598)).
- A triple-quoted string spans lines and reads the same escapes.
  Write `\'\'\'` to include three quotes.
- `note` text goes through `normalizeNote`: it removes leading blank lines and the indentation that all lines share, even in a single-quoted string ([source](https://github.com/holistics/dbml/blob/v11.0.0/packages/dbml-parse/src/core/utils/interpret.ts#L37-L44)).
  Custom property strings keep every character, so `'  a\n  b'` reads back unchanged.
- A bare type is a name, optionally with a schema, and at most one parenthesized list: `number(10,2)`, `varchar2(20)`, `float(126)`.
  A space (`varchar2(100 char)`, `timestamp(6) with time zone`, `double precision`) or a `*` (`number(*,0)`) is an error unless the whole type is in double quotes.
  Quoting the whole type always works.
- A column without a type is an error.
  `unknown` and `"?"` are accepted types, and a bare `?` is not.
- `;` and a byte order mark are errors.
  CRLF line endings, tabs and `//` and `/* */` comments are accepted, and the parser does not keep comments.

### Relationships

- The operators are `<`, `>`, `-` and `<>`.
  A `?` on either side marks that side optional, which gives 16 operators in all ([source](https://github.com/holistics/dbml/blob/v11.0.0/packages/dbml-parse/src/core/types/relation.ts#L30)).
  The old parser (`parser.parse(text, "dbml")`, deprecated) rejects the `?` operators.
- For `<` and `>`, the foreign key is on the many side.
  For `-`, the right-hand column is the foreign key.
  For `<>`, the SQL export writes a junction table, such as `a_b`.
  I checked each case with `ModelExporter.export(db, "postgres")`.
- A `Ref` has a short form (`Ref name: a.x > b.y [settings]`), a long form (`Ref name { ... }`) and an inline form (`x int [ref: > b.y]`).
  The inline form takes no name and no settings.
- `Ref` order does not matter, and a `Ref` may come before its tables.
  Both endpoints must exist, or the parser reports an error.
- Two refs with the same endpoint pair are an error, in either direction and across the inline and short forms.
  `a.x > b.y` with `b.y < a.x` fails ([source](https://github.com/holistics/dbml/blob/v11.0.0/packages/dbml-parse/src/core/global_modules/program/bind.ts#L73-L74)).
- Several refs may share a name, and two refs may join one pair of tables on different columns.

## Composite keys, self-references and many-to-many

| Case | Syntax | Result |
| --- | --- | --- |
| Composite primary key | `indexes { (a, b) [pk] }` | Accepted. dbdiagram.io draws a key on both columns and an index row. The SQL export writes `PRIMARY KEY (a, b)`. |
| Composite primary key, flags | `a int [pk]` and `b int [pk]` | Accepted, and the SQL export reads them as one composite key. Mixing this form with a `pk` index exports two primary keys. |
| Composite foreign key | `Ref: t.(a, b) >? u.(x, y)` | Accepted, with a single line between the two index rows. Unequal counts raise `Unequal fields in ref endpoints`. The inline form raises `'ref' must be a valid unary relationship`. |
| Self-reference | `Ref: emp.mgr >? emp.id` | Accepted in the short, inline, composite and schema-qualified forms. The same column on both sides raises `Two endpoints are the same`. |
| Many-to-many, direct | `Ref: a.id <> b.id` | Accepted. The SQL export adds a junction table. dbdiagram.io warns when both columns are unique (4 warnings for two primary keys). |
| Many-to-many, junction | Two `>` refs from a table with a composite `pk` index | Accepted, and dbdiagram.io shows no warning, with or without `not null`. The docs describe it as the alternative to `<>`. |

## What dbdiagram.io accepts and rejects

- It runs the official grammar.
  More than 70 probes agreed with `@dbml/core` 11.0.0 on accept and reject.
  Where the input matched, the error text and the line and column matched too.
  Examples: an empty table, `$` in a name, `varchar2(100 char)`, `number(*,0)`, a missing type, `Metadata Ref`, a repeated custom key and an unknown ref setting.
- It runs version 11.0.0 or later.
  It accepts number and boolean custom property values, which 10.3.1 rejects.
  The release notes date [custom properties](https://docs.dbdiagram.io/release-notes/2026-09-custom-properties) to 2026-09-23 and [optional relationships](https://docs.dbdiagram.io/release-notes/2026-08-optional-relationships) to 2026-08-03.
- An error does not update the canvas or the table list, which keep the previous valid diagram.
  The editor shows a red badge with the message and the `line:column` of each error.
  A warning does not stop the update.
- Warnings come from cardinality checks, not from syntax.
  The checks are in [`validateCardinality`](https://github.com/holistics/dbml/blob/v11.0.0/packages/dbml-parse/src/core/global_modules/ref/constraint_fixes.ts#L28), and the table below lists what I observed.
  Each problem appears twice, at the `Ref` and at the column, so one problem counts as 2 warnings.
- The Free plan accepts the syntax of paid features.
  `DiagramView` opens an upgrade dialog.
  `headercolor: #3498DB` raised no error and left the header color unchanged.
  The pricing page lists Table Group, Header Color, Detail Levels and Sticky Notes as not included on Free.
- The anonymous editor accepted 400 tables of 3 columns with 399 refs and no error.
  The pricing page limits the Free plan to 10 diagrams and 1 diagram view.

| Columns | Operator | Warnings |
| --- | --- | --- |
| Target is a primary key, foreign key is nullable (the default) | `>` | 2, such as `Column posts.user_id is nullable but operator > requires it to be NOT NULL`. The quick fix is `>?`. |
| Same columns | `>?` or `?>?` | None |
| Target is a primary key, foreign key is `not null` | `>` | None |
| Target is not unique, foreign key is nullable | `?>?` | 2. The quick fix is `?<>?`. |
| Same columns | `?<>?` | None |
| Neither column is unique, both nullable | `<>` | 4 |
| Same columns | `?<>?` | None |
| Both columns are primary keys | `<>` | 4. The quick fix is `<` or `>`. |
| Both columns are primary keys | `-` | None |

A query does not state nullability, so ichnos needs `?` operators or `not null` flags to avoid the first row.
Ticket 12 decides which operators to emit.

## Attaching evidence

| Element | `note` | Custom property | Observed in dbdiagram.io |
| --- | --- | --- | --- |
| Project | `Note:` | Custom string keys are accepted | Not checked |
| Table | Yes | Yes | An icon in the table header. The property filter lists the key. |
| Column | Yes | Yes | An icon on the column. A hover card lists the properties. The property filter does not list the key. |
| Index | Yes | No | Not checked |
| Enum value | Yes | No | Not checked |
| TableGroup | Yes | Yes | Not checked |
| Ref | No | No | Not applicable |

- Use a custom property for evidence that a program reads.
  It keeps leading spaces and newlines, which `note` does not.
  Its value is one string, so a list of sources needs a delimiter.
- Use `note` for text that a person reads.
  The release notes list Markdown support for table and field notes (2021-10, 2022-11 and 2024-04).
  I did not check the rendering.
- Put a key on the table when a reader should filter by it.
  The panel said that it found no custom properties in a diagram that had only a column property.
  Its "Search keys" list showed the table keys `confidence` and `source`, and left out the column keys `evidence` and `note_src`.
  The release notes describe a filter on "tables and fields".
  I did not apply a filter.
- A relationship has three places for evidence.
  The foreign key column takes a custom property, such as `fk_users: 'q1.sql:12'`.
  A `//` comment above the `Ref` stays in the text, and no tool reads it, because the parser does not keep comments.
  A quoted `Ref` name is the only free-text field on a relationship, and it accepts spaces and colons.
  I did not check where dbdiagram.io shows the name.
- Custom property keys are identifiers.
  Two keys that differ only in letter case count as one key.

## Python libraries

PyPI has 20 projects with `dbml` in the name, and two of them (`dbmle` and `pydbml-lang`) are unrelated to DBML.
Two are general parsers and writers.
The rest read DBML for one purpose, such as documentation, diagrams, SQL or models, or generate it from another source.

| Package | Version | Dependencies | Notes |
| --- | --- | --- | --- |
| [PyDBML](https://github.com/Vanderhoof/PyDBML) | 1.2.1, 2025-10-24 | `pyparsing` | MIT. Python 3.8 and later. 143 stars, 13 open issues. The README says that it follows DBML 3.9.5, and `@dbml/core` 3.9.5 shipped on 2024-12-13. The [ecosystem page](https://dbml.dbdiagram.io/ecosystem) lists it. |
| [lark-dbml](https://github.com/daihuynh/lark-dbml) | 0.7.0, 2026-01-09 | `pydantic`; `sqlglot` and `lark` are extras | MIT. Python 3.10 and later. 9 stars. The README claims the April 2025 specification. `import lark_dbml` raises `ModuleNotFoundError` on a plain install: it imports `sqlglot`, an optional extra, and then `yaml`, which the package does not declare. |

Nine of the 20 projects declare PyDBML as a dependency: `al2dbml`, `dbml-builder`, `dbml-sqlite`, `dbml-to-fides`, `dbml-to-sqlmodel`, `dbmlviz`, `foliantcontrib.dbmldoc`, `mkdocs-dbml-plugin` and `snowflake-dbml-generator`.
`django-dbml` 1.2.0 (2026-09-11) and `dbterd` 1.32.0 (2026-10-19) write DBML and declare no DBML library.
`dbml` and `sqlalchemy-dbml` convert SQLAlchemy models and have had no release since 2021.

### Parsing compared with the official parser

PyDBML (56 probes) and lark-dbml (28 probes) differ from `@dbml/core` 11.0.0 in both directions.

| Parser | Rejects what the official parser accepts | Accepts what the official parser rejects |
| --- | --- | --- |
| PyDBML | The `?` operators. `color` and `inactive` on a `Ref`. `Metadata`, `Records`, `Dep`, `TablePartial`, `DiagramView` and `checks`. A one-line table. An unquoted Unicode name. Inline custom properties, unless `allow_properties=True`, and the official table syntax in any mode. | A duplicate column. Reversed duplicate refs. A composite ref with unequal counts. Two `Note:` bodies. Two `Project` blocks. A byte order mark. An unquoted `varchar2(100 char)`. |
| lark-dbml | The `?` operators. `inactive` on a `Ref`. `Metadata`, `Records`, `Dep` and `DiagramView`. | An empty table. A `Ref` to a missing table. Reversed duplicate refs. |

PyDBML writes table custom properties as `owner: 'hr'` inside the table body.
The official parser rejects that form with `A Custom element can only appear in a Project or a Dep`.

### Writing compared with the official parser

I wrote the same cases with each writer, parsed the text with `@dbml/core` 11.0.0, and compared what the parser read with what I meant.
The realistic corpus has 2000 cases with Oracle-style names (`A-Z`, digits, `_`, and `$` or `#` in 15%), 12 Oracle types, and 10 note strings.
The notes include Windows paths, apostrophes, double quotes, a tab and a line break.
The adversarial corpus mixes quotes, backslashes, comment markers, DBML keywords, non-BMP characters and control characters.
I compared each note after `normalizeNote`, because no writer can keep a note's leading indentation.

| Writer | Corpus | Cases | Read back unchanged | Rejected | Changed |
| --- | --- | --- | --- | --- | --- |
| Direct, escape table below | Realistic | 2000 | 2000 | 0 | 0 |
| Direct | Adversarial | 1500 | 1498 | 0 | 2 |
| Direct, with a custom property | Adversarial | 4000 | 3997 | 0 | 3 |
| PyDBML, types quoted by the caller | Realistic | 2000 | 1209 | 0 | 791 |
| PyDBML, types quoted by the caller | Adversarial | 1500 | 87 | 757 | 656 |
| PyDBML, types as given | Realistic | 2000 | 913 | 477 | 610 |

The changed direct cases are notes that consist of one line break, which `normalizeNote` turns into an empty note.
The two Python writers have these defects:

- PyDBML does not escape a backslash.
  `C:\path\to\file.sql` reads back as `C:path`, a tab, `o`, a form feed and `ile.sql`.
- PyDBML indents the continuation lines of a multi-line note, so a note `line1\nline2` reads back with four spaces before `line2`.
- PyDBML writes a type as given, so `TIMESTAMP(6) WITH TIME ZONE` fails unless the caller adds quotes.
- PyDBML does not escape a quote in a name, and it writes an empty table.
- lark-dbml turns the note `it's a \ test` into `it's a ' test`.

The official exporter has related defects.
`ModelExporter.export(db, "dbml")` writes `Table "a"b"` for the name `a"b`, which its own parser rejects.
It also moves inline custom properties into trailing `Metadata` blocks, rewrites each `Ref` with the key side on the left, and omits the `Project` block.
Do not round-trip ichnos output through it.

## Writing the text directly

This escape table is all that the writer needs for names, types and strings:

```python
ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "'": "\\'",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
    "\b": "\\b",
    "\f": "\\f",
    "\v": "\\v",
    "\0": "\\0",
}


def escape(text: str) -> str:
    return "".join(ESCAPES.get(char, char) for char in text)


def quoted(name: str) -> str:
    return f'"{escape(name)}"'


def literal(text: str) -> str:
    return f"'{escape(text)}'"
```

The official `escapeString` has the same table ([source](https://github.com/holistics/dbml/blob/v11.0.0/packages/dbml-parse/src/compiler/queries/utils.ts#L139)).
One table serves both quote styles, because `\'` is valid inside `"..."` and `\"` inside `'...'`.

The writer must also follow these structural rules:

- Quote every name, every type and every index column.
  The official exporter writes index columns unquoted, and `(A$B, C) [pk]` is an error.
- Fold identifiers to one letter case before it matches endpoints, because DBML names are case-sensitive.
  Oracle folds unquoted names to upper case.
- Write the schema on every table and every `Ref` endpoint outside `public`.
- Write a `Ref` only when both tables and all its columns exist in the output.
  Drop a second ref for the same endpoint pair, in either direction.
- Write at least one column per table.
  A table with no known column needs a placeholder column: `"*"` and `"?"` are accepted names, and `unknown` is an accepted type.
- Write at most one `Project`.
  Do not write `;` or a byte order mark.
- Declare a composite primary key with one `indexes` entry.

This output parses with no error and no warning in `@dbml/core` 11.0.0 and in dbdiagram.io.
The property keys `source`, `evidence` and `joins` are placeholders.

```text
Project "inferred" {
  database_type: 'Oracle'
  Note: 'Inferred from queries. No database connection was used.'
}

Table "HR"."DEPARTMENTS" [source: 'q1.sql:4'] {
  "DEPARTMENT_ID" "number(4)" [pk, evidence: 'q1.sql:4']
}

Table "HR"."EMPLOYEES" [source: 'q1.sql:4; q2.sql:9'] {
  "EMPLOYEE_ID" "number(6)" [pk, evidence: 'q2.sql:9']
  "MANAGER_ID" "number(6)" [evidence: 'q2.sql:9', joins: 'HR.EMPLOYEES.EMPLOYEE_ID']
  "DEPARTMENT_ID" "number(4)" [evidence: 'q1.sql:4', joins: 'HR.DEPARTMENTS.DEPARTMENT_ID']
  "SALARY" unknown
}

Ref: "HR"."EMPLOYEES"."MANAGER_ID" >? "HR"."EMPLOYEES"."EMPLOYEE_ID"
Ref: "HR"."EMPLOYEES"."DEPARTMENT_ID" >? "HR"."DEPARTMENTS"."DEPARTMENT_ID"
```

`dbterd` is a Python precedent for this approach.
It writes DBML with string formatting, uses `//` comments for provenance, and declares no DBML library.

## Testing the output

Call the JavaScript API in tests:

```js
const { Parser } = require("@dbml/core");

new Parser().parse(text, "dbmlv2"); // throws on any error
```

- The `dbml2sql` CLI exits with code 0 on a parse error.
  It prints the error and writes `dbml-error.log` in the working directory.
- The official parser needs Node.
  It parses 1000 tables of 20 columns (1.5 MiB) in 0.65 s.
- A Python parser does not replace it.
  PyDBML parses 400 such tables in 1.3 s and lark-dbml in 0.24 s, with the custom properties and `?` operators removed.
  Both give different accept and reject results.
- Pin `@dbml/core` in the test setup and rerun the probes when the pin moves.

## Gaps and risks

- The grammar changes often.
  `@dbml/core` shipped seven major versions after 4.0.0 (2025-10-23), the last on 2026-10-26.
  Optional relationships are 3 months old and custom properties are 5 weeks old.
  11.0.0 was a breaking change that added number and boolean custom property values.
- dbdiagram.io is a hosted app, and I found no version number in it.
  It can change between runs, so rerun the probes before relying on a result.
- Tools that depend on PyDBML read DBML with its grammar.
  I did not test them.
- The probes use short synthetic inputs.
  Real Oracle queries are not available yet.

## Not covered

- dbdocs.io, the dbdiagram CLI and the VS Code extension.
- Saving and sharing a diagram, which needs an account.
- The rendering of notes as Markdown, the use of a property filter, and where dbdiagram.io shows a `Ref` name.
- Paid features beyond whether the syntax is accepted.
- `Records`, `Dep` and `DiagramView` beyond acceptance.
