# The CLI mirrors the API, decodes each file on its own, and writes UTF-8 on every OS

The `ichnos` CLI has one command per API call, so it prints nothing that a Python caller cannot get ([ADR 0013](0013-public-api-is-a-graph-walks-that-return-slices-and-writer-functions.md)).
`read` decodes each file of the corpus on its own, because one corpus can hold files from several Windows editors.
Every command writes UTF-8 with `\n` line endings, so one command writes the same bytes on Windows, macOS and Linux.

The facts about cyclopts, Python, PowerShell and the editors below come from research on 2026-11-03, with cyclopts 5.3.3 and Python 3.14.7 tested on macOS.

## Commands

The CLI has seven commands:

| Command | API call |
| --- | --- |
| `dbml` | `dbml(graph)` |
| `summary` | `summary(graph, owner=, keyword=, budget=)` |
| `neighborhood` | `dbml(graph.neighborhood(...), ...)` |
| `join-path` | `dbml(graph.join_path(...), ...)` |
| `upstream` | `dbml(graph.upstream(...), ...)` |
| `downstream` | `dbml(graph.downstream(...), ...)` |
| `unparsed` | `graph.unparsed` |

Keyword search is `summary --keyword`, as the API's keyword search is `summary(keyword=...)`.
No command writes lineage DBML alone, because the full file holds every `Dep` and a lineage slice is already DBML ([ADR 0011](0011-dbml-evidence-as-custom-properties-in-one-file.md)).

## Corpus

Every command takes the corpus path as its first positional argument, and the path is required:

```text
ichnos dbml queries -o schema.dbml
ichnos join-path queries SALES.ORDERS SALES.PRODUCTS
```

The path is a folder or one file.
`read` reads a file given as the path whatever its suffix.
The CLI types the path as a plain `Path`, not cyclopts's `ExistingPath`, so a missing path exits 1 with the other user errors, not 2.

## Which files `read` reads

In a folder, `read` reads every file whose suffix is `.sql`, in every subfolder.
It compares the suffix without case on every OS, so `.SQL` counts.
`Path.glob` is case-sensitive on macOS and Linux but not on Windows, so it cannot do this alone.
It skips every file and folder under the corpus folder whose name starts with `.`.
It reads the files in key order.

`--suffix` replaces `.sql`, and it can repeat, as `read(path, suffixes=...)` does.
A folder with no matching file raises `IchnosError`.

## Decoding

`read` decodes each file on its own:

1. A BOM picks the codec: UTF-32 LE or BE, UTF-8, or UTF-16 LE or BE.
   UTF-32 LE is checked before UTF-16 LE, because its BOM starts with UTF-16 LE's.
   The BOM is not part of the text.
2. A file with no BOM decodes as strict UTF-8.
3. A file that fails UTF-8 decodes as strict cp1252.
4. A file that fails cp1252 raises `IchnosError`, which names the file, the byte offset and `--encoding`.

Strict cp1252 rejects only the bytes `0x81`, `0x8D`, `0x8F`, `0x90` and `0x9D`.
`--encoding NAME` replaces cp1252 as the fallback, as `read(path, encoding=...)` does.
It never overrides a BOM or valid UTF-8.
An unknown encoding name raises `IchnosError`.

`read` turns `\r\n` and `\r` into `\n`, as Python's text mode does.
So a query's text, and its example in a slice, hold `\n` only.

Each Windows editor saves a new file in its own default encoding:

- VS Code, Notepad, Notepad++ and DBeaver write UTF-8 with no BOM.
- SQL Server Management Studio writes cp1252, and one user reports UTF-16 LE with a BOM for a scripted procedure.
- PL/SQL Developer writes cp1252, or UTF-8 with a BOM when the text needs it.
- Toad for Oracle writes UTF-8 with no BOM by Quest's knowledge base, and users report cp1252 after updates.
  The work machine will have Toad.
- Oracle SQL Developer follows the JVM default, which is likely cp1252 on Western Windows.
  This is unverified.

So one corpus can mix encodings.
One encoding for every file would garble the files it does not match, and cp1252 decodes almost any byte, so it would not raise on a UTF-8 file.
A fixed cp1252 fallback, not `locale.getencoding()`, makes one corpus give one graph on every OS.

## Starts

`neighborhood` takes one or more tables, and `join-path` two or more, as positional arguments after the corpus.
`graph.table` parses each one.

`upstream` takes exactly one of `--table NAME` and `--report NAME`, plus an optional `--column NAME`.
With `--table`, `--column` names a column through `table.column`.
With `--report`, it names an output column through `report.output_column`.
`downstream` takes `--table NAME` and an optional `--column NAME`, because a report is never an upstream end.

```text
ichnos upstream queries --report 055_key_customers --column CUSTOMER_COUNT
ichnos downstream queries --table SALES.ORDERS --column ORDER_ID
```

The options map one to one onto ADR 0013's lookups.
So no string has to tell the table `MART.X` from a column `X` of a table `MART`.
A report name such as `sub/038_daily_reports#2` needs no quotes in PowerShell or cmd.

A name that matches nothing is a user error.
The message names up to three close matches from `difflib.get_close_matches`:

```text
ichnos: no table SALES.ORDER; did you mean SALES.ORDERS?
```

A report name keeps its file's case, and Windows file names ignore case, so a user can type a report name in the wrong case.

## Options

Each option mirrors an API parameter, with the API's name, values and default.
The slice commands are `neighborhood`, `join-path`, `upstream` and `downstream`.

| Option | Default | Commands |
| --- | --- | --- |
| `--budget N` | `8000` | `summary` and the slice commands |
| `--detail compact\|full` | `compact` | the slice commands |
| `--examples` | off | the slice commands |
| `--indirect first_hop\|all` | `first_hop` | `upstream` and `downstream` |
| `--depth N` | `1` | `neighborhood` |
| `--owner NAME` | none | `summary` |
| `--keyword TEXT` | none | `summary` |
| `--suffix SUFFIX` | `.sql` | every command |
| `--encoding NAME` | `cp1252` | every command |
| `-o`, `--output PATH` | stdout | every command |

`--budget` takes a positive integer, and `--depth` takes a non-negative one.
The lineage walks take no depth, as in ADR 0013.

cyclopts matches a `Literal` choice exactly, so `--indirect first-hop` exits 2 with `Did you mean "first_hop"?`.
An `Enum` would accept both spellings, but ichnos types a set of strings as a `Literal`.

## Output

Every command writes to stdout, or to the file that `-o` names.
Both are UTF-8 with no BOM and `\n` line endings, on every OS.
The CLI calls `reconfigure(encoding="utf-8", newline="\n")` on `sys.stdout` and `sys.stderr`.
Python 3.14 on Windows writes cp1252 to a pipe or a file, and it turns `\n` into `\r\n`.
UTF-8 mode becomes Python's default only in 3.15 ([PEP 686](https://peps.python.org/pep-0686/)).

A command writes with `sys.stdout.write` and returns `None`.
cyclopts prints a returned string through Rich.
Rich deletes `[pk, note: 'x']` as markup, and it wraps lines at 80 columns when stdout is a pipe.

`-o` is the one route on Windows that no shell re-encodes:

- Windows PowerShell 5.1's `>` writes UTF-16 LE with a BOM.
  PowerShell 7.4 and later write ichnos's bytes unchanged.
- Both versions decode ichnos's stdout with `[Console]::OutputEncoding` before a cmdlet reads it.
  That is cp437 on en-US, so `| Set-Clipboard` turns `é` into `├⌐`.
- cmd's `>` writes ichnos's bytes unchanged.

ichnos's own text is ASCII.
So only non-ASCII text from the corpus garbles, such as an observed value or a quoted identifier.
The README gives this recipe for a slice to paste:

```powershell
ichnos upstream queries --report 055_key_customers -o slice.dbml
Get-Content -Raw -Encoding UTF8 slice.dbml | Set-Clipboard
```

## Exit codes

The CLI uses three exit codes:

- `0`: success.
- `1`: a user error.
  ichnos writes one line, `ichnos: <message>`, to stderr, with no traceback.
- `2`: a usage error, such as an unknown option, a bad choice or a missing argument.
  cyclopts sets this code and writes its own message to stderr.

A user error is an `IchnosError`, a `KeyError` from a lookup, or an `OSError` from `read`.
The CLI catches `KeyError` only around its lookup calls, and `OSError` only around `read`.
So a `KeyError` raised inside a walk still shows as a bug.
Any other exception is a bug: it propagates with its traceback, and Python exits with `1`.

## Lines on stderr

Two more lines go to stderr, and neither changes the exit code.

When the core of a slice exceeds the budget, ichnos writes the whole slice and this line:

```text
ichnos: the core of this slice is 11,203 characters, over the 8,000-character budget
```

The header states the size too, but stderr reaches a user who pastes without reading the header.
A cut that brings a slice under the budget writes nothing to stderr, because the header lists it.

When any query is unparsed, every command except `unparsed` writes one line that names the corpus path as given:

```text
ichnos: 3 of 61 queries unparsed; run ichnos unparsed queries to list them
```

`ichnos unparsed queries` prints one line per unparsed query to stdout: its name, a colon, and the first line of its error.
So a slice stays clean to paste, and `-o` saves the list.

## Considered options

- A `-c/--corpus` option that defaults to the current folder.
  Rejected because a missing option would read whatever folder the shell is in.
- Reading every file in the folder.
  Rejected because it reads `README.md`, `desktop.ini` and `Thumbs.db`, and `x.sql` beside `x.txt` would clash by default.
- One dotted string for a lineage start.
  Rejected for the reasons under ADR 0013's **Lookups**.
- A `search` command.
  Rejected because the API's keyword search is a `summary` parameter.
- A command that writes lineage DBML alone.
  Rejected because the full file already holds every `Dep`.
- One encoding for every file, set by `--encoding`.
  Rejected because a corpus can mix UTF-8 and cp1252 files, and cp1252 would garble the UTF-8 ones without raising.
- `locale.getencoding()` as the fallback.
  Rejected because one corpus would give a different graph on each OS.
- Listing a file that does not decode as an unparsed query.
  Rejected because an unparsed query is one that ichnos cannot read whole, and such a file gives no text to split into queries.
- A nonzero exit code when the core exceeds the budget.
  Rejected because the slice is complete and valid, and the code would break `ichnos ... -o slice.dbml && ...`.
- Every unparsed query on stderr on every run.
  Rejected because a real corpus with dozens of them would bury the slice's own message.
- Stdin input, as `-`.
  Rejected for v1, because one query fits in a file, stdin text needs a made-up name, and Windows PowerShell 5.1 pipes text into a native command as ASCII.
  cyclopts's `StdioPath` makes `-` cheap to add later.
- A `--copy` option that writes to the clipboard.
  Rejected for v1, because it needs code for each OS and its own CI coverage, and ichnos's own text is ASCII.
- An `Enum` for `--indirect`, so `first-hop` works.
  Rejected because ichnos types a set of strings as a `Literal`.
- Python's default `\r\n` on Windows.
  Rejected because stdout and `-o` would then write different bytes on each OS.
