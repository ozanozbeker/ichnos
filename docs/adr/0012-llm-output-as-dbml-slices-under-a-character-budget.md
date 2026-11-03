# LLM output is DBML slices and a summary, under a character budget

ichnos writes two outputs to paste into an LLM chat: a summary with one line per table and report, and slices.
A slice is DBML in ADR 0011's dialect, written by the same code as the DBML file over a selected part of the graph ([ADR 0011](0011-dbml-evidence-as-custom-properties-in-one-file.md)).
So a test parses a slice with `@dbml/core` 11.0.1 as it parses the full file, and dbdiagram draws a slice.
DBML costs the fewest tokens of the formats that carry refs ([issue 21](https://github.com/ozanozbeker/ichnos/issues/21)).
No study tests DBML, so this choice rests on cost and on one writer, not on measured accuracy.

The measurements below come from the DBML prototype on [`prototype/dbml-output`](https://github.com/ozanozbeker/ichnos/tree/prototype/dbml-output/prototypes/dbml_output) on 2026-11-03: 26 tables, 103 columns, 13 `Ref` lines and 97 `Dep` lines.

## Budget

Every slice and every summary has a budget of 8,000 characters by default, and a call can set another.
8,000 characters is the only prompt size that Microsoft documents for Copilot Chat ([issue 21](https://github.com/ozanozbeker/ichnos/issues/21)).
A paste test in the target tenant may raise the default, and it changes no other rule.

Over the budget, ichnos cuts in the order under **Cut order** and lists every cut name in the header.
It never splits a slice and never fails on size, because Copilot may truncate a long paste without a message.

## Detail

A slice writes ADR 0011's properties at compact detail by default.
Compact detail drops the eight position counts and the four type counts.
A column with two types keeps its type counts, because they are the evidence for that ambiguity.
Every other property stays, so a slice shows `unknown`, `"text|number"`, `null` with `nullable`, `kind`, `complete`, `declared`, `undeclared` and `contradicted` as the DBML file does.
A slice can ask for full detail.

| Level | Characters | Per column |
| --- | --- | --- |
| Full, as ADR 0011 | 10,441 | 101 |
| Compact | 8,410 | 82 |
| Compact without `read`, `write`, `declared` and `nullable` | 7,679 | 75 |
| Names, types and refs only | 5,603 | 54 |

Each figure includes the `Project` note.

## Header

Every slice opens with `Project ichnos`.
Its note holds these lines, in this order:

1. What was asked: the slice kind, its start, its depth, and "N of M tables".
2. "Inferred from N queries, with no database connection."
3. A legend line for each mark that appears in the slice, such as `unknown`, `"text|number"`, `null`, `>?`, `?<>?`, `complete`, `undeclared` and the schema `report`. A slice that holds a table with no `kind` adds the line that says such a table may list only some of its columns.
4. Every name the budget cut, and the core's size when the core exceeds the budget.
5. The outside names that **Neighborhood** and **Join path** list.

ADR 0011's fixed legend costs about 560 characters, 7% of the budget, so a slice writes only the lines it needs.

## Order

A slice keeps ADR 0011's block order: `Project`, tables, `Ref` lines, reports, self-dependencies, `Dep` lines.
Tables are ordered by distance from the start, then by name, so the start comes first and the order matches the cut order.
A schema slice writes no self-dependency.
A lineage slice writes the `Metadata Column` block of each chain column that depends on itself.

## Neighborhood

A neighborhood slice takes one or more center tables and follows relationships only, never dependencies.
Its depth defaults to 1.
Every table in it keeps all its columns, and it holds every `Ref` between two of its tables.

DBML raises on a `Ref` to a table that is not in the file.
So the header names the tables outside the slice that join a table in it, and the centers' upstream and downstream tables.

## Join path

A join path slice takes two or more tables and holds the union of all shortest paths between every pair.
A path's length is its number of relationships.
Every relationship is one step, whatever its direction, including `?<>?` and a shared reference.
Evidence counts do not weight a step, because a count is not a score ([ADR 0001](0001-evidence-counts-and-no-attribution-on-ambiguity.md)).
Every table on a path keeps all its columns.
If no path joins two of the tables, the slice still holds them, and the header names the tables that no relationship connects.

SchemaGraphSQL's union of shortest join paths raised BIRD accuracy for Gemini 2.5 Flash from 51.50 to 62.91, and its high-recall variant beat its high-precision variant by 2 to 7 points ([issue 21](https://github.com/ozanozbeker/ichnos/issues/21)).

## Lineage

An upstream slice starts at a column, an output column, a report or a table.
A report starts at all its output columns, and a table at all its columns.
The slice follows the chain to its upstream ends, the tables that no query in the corpus writes.
Each table block holds only the columns on the chain, and a report block holds all its output columns.
It writes the column-level `Dep` lines, plus the dependencies that ichnos stores at table level, such as from an unexpanded `*` ([ADR 0010](0010-lineage-from-clause-positions-with-openlineage-subtypes.md)).
It writes no rollup.

A downstream slice of a column follows the same rules in the other direction.
A downstream slice of a table writes only the rollup `Dep` lines, over all hops, to every downstream table and report.
Each block lists the columns and output columns that depend on the start table, without their column-level `Dep` lines.

Indirect dependencies appear on the first hop only: from the queries that write the start, or, downstream, from the queries that read it.
The 39 `Dep` lines with only indirect subtypes hold 3,031 of the prototype's 7,702 `Dep` characters, and each hop adds the filters and joins of the query that writes it.
A slice can ask for every indirect dependency.

## Example queries

A slice names its evidence by counts only, as the DBML file does.
Copilot cannot open the query files, so a query's name gives it nothing.
A slice can ask for example queries, which count against the budget:

- A schema slice picks, one at a time, the query that holds evidence for the most `Ref` lines in the slice that no picked query covers, until every `Ref` is covered. A tie goes to the shorter text, then to the name.
- A lineage slice picks the queries that write each hop, nearest hop first.

Each example is the query's text as the corpus holds it, comments included.
It follows a `// <query name>` line, with every line prefixed `// `.
SQL text can hold `*/`, which ends a `/* */` comment early, and a `//` line needs no escaping.
DBML drops comments, so the slice still parses.

## Cut order

Within each step, ichnos cuts the farthest table first, then the one with the fewest `read` plus `write`, then by name in reverse.

- Neighborhood:
  1. Drop the example queries, the last one picked first.
  2. Trim each table that is not a center to its key columns and the columns on the slice's `Ref` lines.
  3. Drop each table that is not a center, with its `Ref` lines.
- Join path:
  1. Drop the example queries.
  2. Trim each table between the ends to its key columns and the columns on the path.
- Lineage:
  1. Drop the example queries.
  2. Drop the first hop's indirect dependencies.

What remains is the core: the centers, the paths or the chain.
If the core exceeds the budget, ichnos writes it whole, and the header states its size.
ichnos never cuts below compact detail, because the counts are the evidence.

## Summary

The summary is plain text, because DBML raises on a table with no columns.
It holds one line per table and report, in name order, after one line that states its filters, the number of queries, and what the budget cut.

A table's line holds its name, its kind if declared, its column count with `complete`, its `read` and `write` counts, and the tables it joins:

```text
SALES.ORDERS: base table, 11 columns, complete, read 24, write 1; joins SALES.CUSTOMERS, SALES.ORDER_LINES
```

A report's line holds its output column count and the tables it reads:

```text
report."055_key_customers": report, 3 columns; from MART.V_KEY_CUSTOMERS
```

On the prototype, a line costs 61 characters, so 8,000 characters hold about 130 lines.
Adding each table's upstream and downstream tables would raise that to 96, and a lineage slice answers that question.

The summary takes an owner filter and a keyword filter.
The keyword filter keeps each table whose name, column names or observed values contain the keyword, ignoring case.
Each kept line adds `matches` and the matching columns, such as `matches STATUS ('A')`.
A report matches on its name and its output column names.
Over the budget, the summary cuts the lines with the lowest `read` plus `write` first, and its first line says how many it cut and below which count.

## Explore commands

The neighborhood and join path explore commands print these slices, and keyword search prints the filtered summary.
No second format exists for a human, because a human reads DBML and dbdiagram draws a slice.

## Considered options

- Compact lines, such as `table(col TYPE, ...)` plus `a.b -> c.d`.
  They cost 17% fewer tokens, but need a second writer and a second way to write evidence.
- One-line DDL.
  It costs 2% more tokens and has no place for a count but a comment.
- Full detail by default.
  It holds about 79 columns per 8,000 characters against 98 at compact detail.
- A slice of one table as the per-table summary.
  Rejected because nothing then lists a large corpus, and the LangChain agent and LlamaIndex list the tables before they fetch any detail.
- Warn and write the whole slice, split it into numbered parts, or fail.
  Rejected because Copilot may truncate a long paste without a message, and a split slice loses the `Ref` lines between parts.
- The names of the queries behind each claim.
  Rejected because Copilot cannot open them and each list is long.
- Example queries in a `/* */` comment.
  Rejected because SQL text can hold `*/`.
- Every indirect dependency on every hop by default.
  Rejected because they make 40% of the `Dep` text.
- Direct dependencies only.
  Rejected because the first hop's filters state which rows the start holds.
- Path steps weighted by evidence count.
  Rejected because a count is not a score.
- A fixed legend.
  Rejected because it costs 7% of the budget.
- A separate human format for the explore commands.
  Rejected because it would define a neighborhood and a join path twice.
