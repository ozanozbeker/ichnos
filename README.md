# ichnos

Infer a DBML schema and ERD from SQL queries alone.
No database connection needed.

ichnos reads a folder of Oracle queries and writes the tables, columns, keys, relationships and lineage those queries imply.
Every claim carries its evidence counts, and every ambiguity lists its candidates.

## Run it

`uvx` runs ichnos with no install and no compiler:

```sh
uvx ichnos dbml queries -o schema.dbml
uvx ichnos summary queries --keyword status
uvx ichnos join-path queries SALES.ORDERS INV.PRODUCTS
uvx ichnos upstream queries --report 055_key_customers
```

`uvx "ichnos[c]"` runs the same commands on compiled sqlglot, which is about 3x faster.

## Paste a slice into a chat on Windows

Every command writes UTF-8.
Windows PowerShell re-encodes what it pipes, so write the slice to a file with `-o` and copy the file:

```powershell
ichnos upstream queries --report 055_key_customers -o slice.dbml
Get-Content -Raw -Encoding UTF8 slice.dbml | Set-Clipboard
```
