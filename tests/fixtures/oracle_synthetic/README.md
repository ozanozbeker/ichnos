# Synthetic Oracle corpus

This fixture is an invented Oracle schema and 44 query files over it.
Design work and tests use it until real queries are available.

`queries/` is the input: one or more statements per file, as ichnos would read a folder of production queries.
`answer_key/schema.sql` is the real schema as Oracle DDL, with every primary key, foreign key, view, synonym and database link.
ichnos must never read the answer key as input, because a test scores inferred output against it.

## The schema

The schema has 18 tables, 3 views and 2 sequences in four schemas.
`REF` holds lookup tables with character keys, `HR` holds employees and departments, `SALES` holds customers and orders, and `INV` holds products, stock and shipments.
The queries run as `APP_RO`, a user that owns no objects, so an unprefixed name resolves through a public synonym.

## Coverage

Each construct the corpus covers appears in these files:

| Construct | Files |
| --- | --- |
| ANSI joins | 002, 004, 010, 027, 034, 035, 043 |
| Comma joins with the condition in `WHERE` | 003, 037 |
| `(+)` outer joins | 005 (right side), 006 (self-join), 007 (left side, two columns), 044 (two columns) |
| Table and column aliases | Most files; 006 and 034 alias one table twice; 028 quotes its column aliases |
| CTEs | 010 (recursive), 011 (two CTEs) |
| Subqueries | 012, 025, 030, 039 (inline view); 013, 026 (`EXISTS`); 014 (`NOT IN`); 015, 024 (scalar); 041 (`IN`) |
| Unqualified columns | 001, 009, 014 (one table); 016, 042 (two tables); 021, 038, 039 |
| Schema prefixes | Most files; 003, 020, 040 have none; 028 quotes them; 037 is all uppercase |
| Views | 017, 018 (renamed columns); 019 (materialized view) |
| DML | 022 (`INSERT`), 023 (`INSERT ... SELECT`), 024 (`UPDATE`), 025 (`MERGE`), 026 (`DELETE`) |
| Other Oracle syntax | 009 (`CONNECT BY`), 012 (`ROWNUM`), 021 (database link), 022 and 032 (sequences), 029 (`DECODE`, `NVL`), 031 (`FETCH FIRST`), 033 (hint), 040 (`LISTAGG`), 041 (`ROWID`) |

## Traps

Some files lead a naive reading away from the answer key:

- 036 joins `HR.EMPLOYEES` to `SALES.CUSTOMERS` on `EMAIL`, and 044 joins `SALES.PAYMENTS` to `SALES.ORDERS` on `CURRENCY_CODE`.
  Neither join is a foreign key.
- 024 joins `SALES.ORDER_LINES` to `INV.STOCK_LEVELS` on `PRODUCT_ID`.
  Both columns reference `INV.PRODUCTS`, and neither references the other.
- `INV.WAREHOUSES` has the key `ID`, not `WAREHOUSE_ID` (008, 025, 043).
- `SALES.ORDERS` references `SALES.CUSTOMER_ADDRESSES` twice, through `SHIP_TO_ADDRESS_ID` and `BILL_TO_ADDRESS_ID` (034).
- `HR.DEPARTMENTS.LOCATION_COUNTRY` references `REF.COUNTRIES.COUNTRY_CODE` (035).
- `EMP` is a synonym for `HR.EMPLOYEES` (020), and `CUSTOMERS`, `ORDERS`, `ORDER_LINES` and `PRODUCTS` are synonyms with the table's own name (003, 040).
- `HR.EMP_DIRECTORY` renames every column it exposes (018).
- `sales.payments_seq.NEXTVAL` has the shape of `schema.table.column` (032).
- No query reads `HR.JOB_HISTORY`, and no query joins on some declared foreign keys, such as `SALES.CUSTOMER_ADDRESSES.CUSTOMER_ID`.
