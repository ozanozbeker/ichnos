# Infer keys from name matches and four query shapes, and claim no primary key

A corpus holds no key constraint, and direction comes only from keys ([ADR 0002](0002-relationships-from-bare-equality-direction-from-key.md)).
ichnos infers a key from two bases: a column's name and the shape of a query.
A table's keys are the union of both bases, and neither basis overrides the other.
A table often has a surrogate key and a business key, such as `ID` and `WAREHOUSE_CODE` in `INV.WAREHOUSES`, and both are keys.
A key whose columns contain another key's columns stays its own claim, and ichnos never claims a primary key.

## Name matches

A name match supports a key on its own.
It is not evidence and has no evidence count, because no query holds it.
For a table `T`, with its owner and database link dropped, a column is a name match when its name is:

- `ID`.
- `<S>_ID` or `<S>_CODE`, where `S` is `T` or a singular of `T`.
- `<S>_ID` or `<S>_CODE`, where `S` is the last word of a multi-word `T`, or a singular of it.
  This pattern does not apply when another table's name, or a singular of it, equals the last word or a singular of it.
  So `USER_ROLES (ROLE_ID)` claims no key when a table `ROLES` or `ROLE` exists, because `ROLE_ID` there is a foreign key.

A singular drops a final `S`, drops a final `ES`, or turns a final `IES` into `Y`.
ichnos tries every singular, so `WAREHOUSES` gives `WAREHOUSE` and `ADDRESSES` gives `ADDRESS`.
Names compare without regard to case, after Oracle folds unquoted names.

Against every column of the synthetic answer key, these patterns give the true key of 12 of the 18 tables and no false key.
They miss `PROMOTIONS (PROMO_ID)`, every composite key, and the unique keys `EMAIL`, `SKU` and `PROMO_CODE`.

## Key evidence

Four query shapes give key evidence.
Each is its own kind, counted in distinct queries ([ADR 0001](0001-evidence-counts-and-no-attribution-on-ambiguity.md)):

- `generated`: an `INSERT`, a `MERGE ... INSERT` or an `UPDATE ... SET` assigns `NEXTVAL` or `SYS_GUID()` to a column that a column list or the `SET` names, or that a declaration maps by position ([ADR 0008](0008-declarations-settle-ambiguities-until-contradicted.md)).
  In the corpus, 022 gives `ORDERS (ORDER_ID)`.
  `CURRVAL` gives nothing, because it copies a parent's key into a foreign key.
- `merge`: the target columns that the `ON` clause of a `MERGE` compares with `=`.
  Oracle does not require them to be unique, but an upsert matches on a key.
  In the corpus, 025 gives `STOCK_LEVELS (PRODUCT_ID, WAREHOUSE_ID)`.
- `single_row`: the columns that a single-row subquery's `WHERE` compares with `=`.
  A single-row subquery sits where Oracle expects one value: a select list, a comparison operator, a `SET` or a function argument.
  It reads one table, not a local relation, and has no aggregate, `GROUP BY`, `DISTINCT`, `ROWNUM` or `FETCH FIRST`.
  Oracle raises ORA-01427 when such a subquery returns two rows, so a valid production query shows that it returns one.
  In the corpus, 024 gives `SHIPMENTS (SHIPMENT_ID)`.
  `IN`, `EXISTS`, `ANY` and `ALL` take many rows, so they give nothing.
- `grouped`: the output columns of a creating query that project its `GROUP BY` expressions.
  Under `SELECT DISTINCT` or a top-level `UNION`, `INTERSECT` or `MINUS`, every output column forms the key, because Oracle removes duplicate rows.
  `ROLLUP`, `CUBE`, `GROUPING SETS` and `UNION ALL` give nothing, because their rows can repeat.

`merge` and `single_row` count only when every conjunct of the clause is a bare `=` between a column of the table and a bind variable, an outer column or a source column.
A literal, a range, `IS NULL`, a function or an `OR` can make a column set unique in part of the table only.
For example, `PRODUCT_ID` is unique among the current rows of a history table under `current_flag = 'Y'`, but not in the whole table.
So a literal still gives no key evidence ([ADR 0003](0003-literals-give-types-and-observed-values-never-an-enum.md)).
Under ADR 0001, an ambiguous column gives key evidence to no candidate.

`CONNECT BY PRIOR` gives no key evidence.
`PRIOR` sits on the key in `CONNECT BY PRIOR category_id = parent_category_id`, which reads a tree from the root down.
It sits on the foreign key in `CONNECT BY PRIOR manager_id = employee_id`, which reads a tree from a leaf up.

ichnos records no evidence that a column set is not a key.

## Direction

The side of a relationship whose columns equal one of its table's keys is the referenced side.
With no such side, or two, the direction stays unknown, as ADR 0002 says.
In the synthetic corpus, every foreign key that a query joins on gets a direction except two.
`SHIPMENT_LINES` to `ORDER_LINES` has a composite key, and `ORDER_PROMOTIONS` to `PROMOTIONS` has the abbreviated key `PROMO_ID`.

## Considered options

- Naming counts as evidence, with a count of the queries that reference the column.
  Rejected because a reference says nothing about uniqueness, so the count would measure use.
- No naming.
  Rejected because only `ORDERS`, `SHIPMENTS` and `STOCK_LEVELS` get a key from query shapes in the corpus, so most relationships would lose direction.
- Key evidence on a table overrides its name matches.
  Rejected because a `MERGE` on `WAREHOUSE_CODE` would hide `ID` and the direction it gives 008 and 043.
- `_NO` and `_KEY` patterns.
  Rejected because the last-word pattern would make `LINE_NO` a key of `ORDER_LINES`, when it is half of `(ORDER_ID, LINE_NO)`.
- Abbreviations by prefix, such as `PROMO_ID` for `PROMOTIONS`.
  Rejected because a prefix rule would make `PRODUCTION_RUNS (PROD_ID)` a key, when it is a foreign key to `PRODUCTS`.
- A bind variable under `=` in a `WHERE`.
  Rejected because 021 and 033 filter `ORDERS` by `CUSTOMER_ID`, a foreign key.
- The column that the most tables join to is the key.
  Rejected because 024's `PRODUCT_ID` ties three ways.
- Evidence against a key from `GROUP BY`, `PARTITION BY` or `HAVING COUNT(*) > 1`.
  Rejected because it could only veto a key, no corpus case needs a veto, and a veto would need a rule for when it meets a name match.
