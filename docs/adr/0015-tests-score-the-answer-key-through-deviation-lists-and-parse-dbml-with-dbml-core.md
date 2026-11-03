# Tests score the answer key through deviation lists and parse DBML with `@dbml/core`

The synthetic corpus cannot show every fact in its answer key.
No query reads `HR.JOB_HISTORY`, and the name patterns of [ADR 0006](0006-keys-from-name-matches-and-four-query-shapes.md) find 12 of 18 keys.
So a test compares ichnos's claims with the answer key exactly, and lists every expected difference, with its reason, in a committed file.
No Python parser agrees with `@dbml/core` ([issue 12](https://github.com/ozanozbeker/ichnos/issues/12)), so the tests run it in Node.

## Reading the answer key

`tests/answer_key.py` reads `answer_key/schema.sql` with sqlglot.
sqlglot 30.26.0 parses its 22 tables, 5 views and 38 `ALTER TABLE` constraints, and it reads the 5 `CREATE PUBLIC SYNONYM` statements and the database link as `Command`.
A regex reads those 6 statements.
A second, hand-written copy of the schema would state the truth twice.
That module is the one file outside `_read` that ruff's TID251 lets import sqlglot.

## Scoring

The scorer resolves every name through the answer key's synonyms.
Each claim then gets one outcome:

- `match`: the claim holds in the answer key.
- `miss`: the answer key holds a fact that the corpus shows and ichnos does not claim.
- `extra`: ichnos claims what the answer key does not hold.
- `ambiguous`: an ambiguity whose candidates include the true answer, with no evidence counted for any candidate.

An ambiguity whose candidates miss the true answer is a `miss` and an `extra`.

A claim holds by these rules.
Recall is checked only where the corpus shows the fact:

| Claim | Holds when | Recall checked against |
| --- | --- | --- |
| Table | the answer key has its owner and name | every table that `lineage.csv` names |
| Column | the answer key's table has it | every column that `lineage.csv` names |
| Kind | it equals the answer key object's kind | every declared table |
| Key | its columns equal a primary key or a unique constraint | every key in the answer key |
| Relationship | its columns equal a foreign key's, with the referring side on the foreign key's side when it has a direction | every foreign key in the answer key |
| Shared reference | both sides have a foreign key to the named key column | the same |
| Type | it equals the mapped type | not checked |
| Nullable | the answer key's column has no `NOT NULL` | not checked |
| Dependency | it equals a `lineage.csv` row | every row |

`CHAR` and `VARCHAR2` map to `text`, `NUMBER` to `number`, and `DATE` and `TIMESTAMP` to `datetime`.
So a missing type or nullable claim costs nothing, and a wrong one fails.

A dependency gives one row per subtype per `Query` record behind it, in `lineage.csv`'s columns.
`file` is the query's file key plus `.sql`, and `statement` is its position.
A table or a report as the downstream end gives an empty `downstream_column`, a table as the upstream end gives an empty `upstream_column`, and a report gives an empty `downstream_table`.
The test compares the rows with `lineage.csv` as sets, because the key holds no duplicate row.

The answer key holds no evidence count, so the scorer reads none.
The golden files pin every count in the corpus output, and the inline tests pin each counting rule.

## Deviation lists

Every outcome other than `match` must appear in one of two files beside the answer key:

- `schema_deviations.csv` holds `claim`, `subject`, `outcome` and `reason`.
  `subject` is the name as the DBML file writes it, such as `SALES.ORDERS.STATUS`, `INV.STOCK_LEVELS(PRODUCT_ID, WAREHOUSE_ID)` or `SALES.ORDERS(CUSTOMER_ID) > SALES.CUSTOMERS(CUSTOMER_ID)`.
- `lineage_deviations.csv` holds `lineage.csv`'s eight columns, plus `outcome` and `reason`, so a row compares column for column.

An outcome that no row lists fails the test.
A row whose outcome no longer occurs also fails, so the lists only shrink.
Each `ambiguous` outcome is listed, so a broken declaration that adds an ambiguity fails.

Each `reason` names the ADR rule or the fixture README trap that produces the deviation, such as "ADR 0001: an unprefixed name stays its own table".
A difference that no rule explains is a bug.
It is fixed, or it goes to a new decision, and it never goes on a list.

## Rule cases

The synthetic corpus does not change.
Each case it lacks is an inline `infer({...})` test that asserts on the records, so the SQL and the expected claim sit side by side:

- Declarations ([ADR 0008](0008-declarations-settle-ambiguities-until-contradicted.md)): an ambiguity that a declaration settles, an undeclared column, two declarations that differ, an `INSERT` with a different value count, a `NATURAL JOIN` over declared tables, a reference that contradicts a declared type, and `USER` read as a column.
- Lineage ([ADR 0010](0010-lineage-from-clause-positions-with-openlineage-subtypes.md)): `COUNT(1)`, `COUNT(*) OVER`, an `INSERT ALL` with `WHEN`, an `INSERT` with no column list into an undeclared table, an unexpanded `*` in a creating query and in a report, and a cycle through two tables.
- Reports ([ADR 0009](0009-reports-take-their-file-name-and-output-columns-take-oracles-name.md)): an unaliased expression, whitespace or a comment inside one, a repeated output column name, and a query over `DUAL` that reads a table through a scalar subquery.
- Evidence counts ([ADR 0001](0001-evidence-counts-and-no-attribution-on-ambiguity.md)): identical text counts once, an ambiguous reference counts for no candidate, and a count is of queries, not of references.

The input cases of [ADR 0014](0014-cli-mirrors-the-api-and-decodes-each-file-on-its-own.md) write their bytes into `tmp_path`: each BOM, a cp1252 file, a file that fails cp1252, a `.SQL` suffix, a hidden file, a subfolder and `\r\n` line endings.
A committed file would not keep its bytes, because the `trailing-whitespace` and `end-of-file-fixer` hooks rewrite it, and git on Windows can convert its line endings.
A file that fails cp1252 makes `read` raise for its whole folder, so no corpus can hold one.

Tests import only the public names of [ADR 0013](0013-public-api-is-a-graph-walks-that-return-slices-and-writer-functions.md).
The one exception is the in-process CLI tests, which import the cyclopts app from `ichnos._cli`.
So a refactor of a private module breaks no test, and a line that no public call reaches is dead code.

## Parsing DBML

`tests/dbml/package.json` and `package-lock.json` pin `@dbml/core` and `@dbml/parse`.
Every DBML text must parse in that `@dbml/core` with no error and no diagnostic ([ADR 0011](0011-dbml-evidence-as-custom-properties-in-one-file.md)).
Dependabot's `npm` entry bumps it weekly, with the same 7-day cooldown as its `uv` entry, and it skips pre-releases.
A bump that passes merges as a `chore:` commit, so ichnos follows the parser that dbdiagram moves to.
CI installs it with `npm ci --ignore-scripts`, so no package install script runs.

A pytest session fixture starts one Node process running `tests/dbml/check.mjs`.
Each test sends it DBML text and receives the parse error, the diagnostics, and the parsed tables, columns and property values as JSON.
One process costs one round trip per text, where a process per text would cost one Node start each.
Every CI job that runs pytest runs `setup-node` with the current LTS major.
Locally, a missing `node` fails the test with a message, so no run skips the DBML checks silently.

A Hypothesis test writes generated quoted names and observed values through `infer` and `dbml`.
The values hold quotes, backslashes, commas, leading spaces, newlines and non-ASCII text.
It asserts that `@dbml/core` reads back the same name and value, which checks the escape table from [issue 20](https://github.com/ozanozbeker/ichnos/issues/20) beyond hand-picked cases.

## Golden files

syrupy stores, as golden files, the full DBML of the synthetic corpus, its summary, and one slice per walk kind.
A small extension writes them as `.dbml` and `.txt` files, so a reviewer opens one in dbdiagram, and every change to the output shows in the pull request diff.
`pytest --snapshot-update` rewrites them, and syrupy reports a golden file that no test uses.
The extension calls `assert_dbml_valid` on every text it compares, so no golden file holds invalid DBML.
`.gitattributes` keeps them at `eol=lf` on Windows.

Two more checks compare with the golden DBML file:

- A subprocess test in the `test` job compares its `-o` file with it.
- The `uvx` job of [issue 16](https://github.com/ozanozbeker/ichnos/issues/16) compares its output with it, using `git diff --no-index --exit-code`.
  The job resolves the newest sqlglot patch with no lock, so it catches a patch that changes the output before a user runs it.

## Budget and cut order

For each slice kind and for the summary, a test steps the budget down from the full text's length.
Each step sets the budget one character under the last text's length, so it forces exactly the next cut.
At each step the test asserts three things:

1. The text fits the budget, or the header states the core's size.
2. The cut names extend the previous step's names, so the cut order of [ADR 0012](0012-llm-output-as-dbml-slices-under-a-character-budget.md) is fixed.
3. A slice parses with no diagnostic, so no cut leaves a `Ref` to a table it dropped.

A slice stops at its core.
The summary has no core, so it stops when only its first line remains, and that line states how many lines it cut and below which count.
One golden file per slice kind pins the exact sequence, at a budget that runs through every cut step.

## CLI

In-process tests call the cyclopts app with `capsys`.
One parametrized test covers each exit code and each of ichnos's stderr lines as exact text, including the budget line, the unparsed line, and a bug that exits 1 with its traceback.
A cyclopts usage error asserts only exit code 2 and a non-empty stderr, because the `lowest` job runs cyclopts's floor, whose wording can differ.

Subprocess tests run `python -m ichnos` in the `test` job, over a corpus that holds `é` in an observed value and in a quoted name.
They assert that stdout and the `-o` file hold the same bytes, in UTF-8 with no BOM and no `\r`.
These tests alone check `reconfigure` on a real Windows pipe.
CI runs on Ubuntu only ([CONTRIBUTING.md](../../CONTRIBUTING.md)), so they check it only when run on a Windows machine.

## The real corpus

`test_real_corpus` runs only when `ICHNOS_CORPUS` names a folder, and its skip reason names the variable.
It builds the graph once and walks these starts:

- `neighborhood` of every table, at depth 1.
- `upstream` of every report.
- `downstream` of every table that some query reads.
- `join_path` over each pair of tables that one report reads, taken from the rollups.

It asserts that nothing raised other than `IchnosError`, that every DBML text parses with no diagnostic, and that every slice fits its budget or states its core size.
Each CLI command then runs once, on the first start, and the test checks its exit code and its stderr lines.
It writes nothing to the repo, because the real queries stay on the user's machine.

## Config for the first implementation pull request

- A ruff per-file ignore of TID251 for `tests/answer_key.py`.
- `syrupy` and `hypothesis` in the `dev` group.
- `.gitattributes` with `eol=lf` for the golden files.
- Dependabot's `npm` entry for `tests/dbml`.
- `setup-node` and `npm ci --ignore-scripts` in every job that runs pytest.

## Considered options

- Precision and recall thresholds.
  Rejected because a regression inside the margin passes.
- A hand-written expected output beside the answer key.
  Rejected because it states the truth twice.
- An ambiguity that passes unlisted when its candidates hold the truth.
  Rejected because a broken declaration would then add ambiguities unseen.
- Recall over every column of the answer key.
  Rejected because the list would hold every column that no query names.
- A second fixture corpus with its own answer key for the missing cases.
  Rejected because each case's SQL and its expected claim would sit in two files.
- Committed byte fixtures for the input cases.
  Rejected because the hooks and git rewrite their bytes.
- Unit tests per private module.
  Rejected because each test would depend on the module layout.
- A pytest marker that runs the DBML tests in one Ubuntu job.
  It saves about 15 seconds per job, but a local run can skip them silently.
- One Node process per DBML text.
  Rejected because each start costs a Node launch and a load of `@dbml/core`.
- `@dbml/core` pinned at 11.0.1 for good.
  Rejected because dbdiagram moves to newer releases.
- A few hand-picked budgets.
  Rejected because they can skip a cut step.
- In-process CLI tests alone.
  Rejected because `capsys` replaces the stream that `reconfigure` changes, so they cannot see Windows's bytes.
- A separate script for the real corpus.
  Rejected because its checks could drift from the tests'.
- A join path over every pair of tables in the real corpus.
  Rejected because it grows with the square of the table count.
