# PROTOTYPE: DBML output with evidence

Throwaway. It answers [DBML output with evidence](https://github.com/ozanozbeker/ichnos/issues/12) and is never merged.

`build.py` writes the same slice of the synthetic corpus in three variants, which differ only in where evidence counts and ambiguity flags go:

- `out/a_settings/`: integer and string custom properties, such as `[select: 14, join: 9]`.
- `out/b_notes/`: one `note` per element, such as `[note: 'select 14, join 9']`.
- `out/c_comments/`: `//` comments, which no parser keeps.

Each variant has `schema.dbml` (the ERD), `lineage.dbml` (reports and `Dep`, which imports the ERD with `use`) and `combined.dbml` (both in one file, to paste into dbdiagram).
The schema counts are hand-entered and illustrative.
The lineage comes from `answer_key/lineage.csv`, with 016's unqualified columns turned into ambiguities.
Tables in the `DEMO` owner and the report `demo/unaliased_columns#2` are invented, for cases the corpus lacks.

```bash
uv run --no-project python prototypes/dbml_output/build.py
```

`check.mjs` parses a file with `@dbml/core` 11.0.1 and prints every diagnostic.
Every output file parses with no error and no diagnostic.

## What dbdiagram showed

I pasted a 60-line extract of variant A, with two variant B notes, into the anonymous dbdiagram editor on 2026-11-03.

- A table's hover card lists its indexes and its custom properties as a bullet list.
- A column's hover card lists its custom properties, or its note.
- The hover card shows no index note, so key evidence in an index note is invisible. The variants put it in a table property or the table note.
- The hover card shows no `null` setting.
- Hovering a column labels its `Ref` lines with the `Ref` name, such as `join 6`.
- A `Dep` line has no hover card. Clicking a table highlights its lineage.
- A "Link type" switch shows `ERD`, `Dependencies` or `ERD + Deps`, so one file holds both views.
- `?<>?`, `"text|number"`, a report table with no `Ref`, a quoted name such as `"COUNT(*)"`, and a table-level self-dependency all render.

## Other measurements

- A `>?` whose target is a `unique` index gives no diagnostic. `>?` to a column with no key gives `should be unique or primary key`.
- `?<>?` gives no diagnostic. `<>` gives 4 and `-` gives 6 on the same columns.
- `NOTE`, `REF`, `INDEXES`, `TABLE` and `CHECKS` parse as column names without quotes.
- `Metadata Column t.a { k: 'v' }` in one file sets a property on a column that another file defines and `use` imports.
