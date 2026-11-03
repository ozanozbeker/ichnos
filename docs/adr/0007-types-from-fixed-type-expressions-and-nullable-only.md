# Types come from fixed-type expressions in one query, and ichnos claims nullable but never `NOT NULL`

[ADR 0003](0003-literals-give-types-and-observed-values-never-an-enum.md) gives a bare column the type of a literal that a query compares with it or assigns to it.
This ADR widens the literal to any fixed-type expression and adds typed parameters.
Every rule reads one query, and a type never passes from one column to another.

## Types

A type is text, number, datetime or interval.
The output writes it in lowercase with no length or precision: `text`, `number`, `datetime` or `interval`.
ichnos writes no Oracle data type, because `VARCHAR2` or `DATE` claims a subtype that no query tells apart from `CHAR` or `TIMESTAMP`.
In the answer key, `PAYMENTS.PAID_AT` is a `TIMESTAMP` and `ORDERS.ORDER_DATE` is a `DATE`, and both get `datetime`.
LOB, `RAW` and `BOOLEAN` get no type of their own.
A column with no type evidence has no type.

## Type evidence

A fixed-type expression has a type that ichnos can name without knowing any column's type.
It is a literal, `SYSDATE`, `SYSTIMESTAMP`, a sequence's `NEXTVAL`, a function with a fixed result type such as `ADD_MONTHS`, `COUNT` or `UPPER`, or arithmetic over these.

Two shapes give a bare column type evidence:

- A same-type position: the column sits beside a fixed-type expression where Oracle converts operands to one type.
  The positions are comparisons, assignments, the arguments of `NVL`, `COALESCE`, `NULLIF`, `GREATEST` and `LEAST`, the result branches of `CASE` and `DECODE`, and one column position across the branches of a set operation.
  In the corpus, 015's `order_date >= ADD_MONTHS(SYSDATE, -1)` gives datetime, 022's `NEXTVAL` assigned to `ORDER_ID` gives number, and 029's `NVL(o.sales_rep_id, -1)` gives number.
- A typed parameter: the column is the argument of a parameter that takes one type.
  `*`, `/`, unary minus, `SUM`, `AVG`, `ABS`, `MOD`, `FLOOR` and `CEIL` give number.
  The first argument of `UPPER`, `LOWER`, `TRIM`, `SUBSTR`, `INSTR`, `LENGTH`, `REPLACE`, `LPAD` and `RPAD` gives text.
  `ADD_MONTHS`, `MONTHS_BETWEEN`, `LAST_DAY` and `EXTRACT` give datetime.
  `TRUNC` and `ROUND` give datetime with a text format such as `'MM'`, number with a number, and nothing with one argument, because both take dates and numbers.
  In the corpus, 011's `ol.quantity * ol.unit_price` gives number and 036's `LOWER(c.email)` gives text.

These positions give nothing:

- `+` and `-`, because datetime arithmetic uses them.
- `||`, because code concatenates numbers and dates routinely, as 009 does.
- The arguments of `TO_CHAR`, `TO_NUMBER` and `TO_DATE`, because `TO_CHAR` takes dates and numbers, and code also applies the other two to values that already have the target type.
- `MAX`, `MIN`, `COUNT` and `LISTAGG`, because they take every type.

Type evidence is not proof, because Oracle converts types implicitly.
Each type has its own evidence count of distinct queries ([ADR 0001](0001-evidence-counts-and-no-attribution-on-ambiguity.md)), and an ambiguous column gives type evidence to no candidate.

ichnos keeps its own table of Oracle functions and their parameter types.
Without a schema, sqlglot 30.26.0's `annotate_types` leaves `ADD_MONTHS`, `SUM`, `NVL`, `TO_CHAR` and `TO_NUMBER` as `UNKNOWN`, types `SYSDATE` as `TIMESTAMP` and `ROUND(x, 2)` as `DOUBLE PRECISION`, and never infers a column's type from the expression around it.

## Columns compared with columns

A type never passes from one column to another.
`c.customer_id = o.customer_id`, one column position across set-operation branches, and `INSERT ... SELECT` of a column give neither side type evidence, even when one side has a type from another query.
So `CUSTOMER_ID` has no type anywhere in the synthetic corpus, because its queries compare it only with bind variables and other columns.
A type does not pass along a dependency either ([ADR 0009](0009-lineage-from-clause-positions-with-openlineage-subtypes.md)).

A column's name gives no type.

## Declared columns and report output columns

A creating query's declared column, or a report's output column, whose expression has a fixed type gets that type as evidence.
A declared column takes that type outright, because Oracle gives a table or view column the data type of its expression ([ADR 0008](0008-declarations-settle-ambiguities-until-contradicted.md)).
Type evidence for another type from other queries raises no ambiguity for it.
`COUNT(*) AS order_count` gives number, and 021's `'CURRENT' AS source` gives text.
A projected literal gives no observed value, as ADR 0003 says.
A bare column, or an expression whose type follows an upstream column such as `MAX(p.paid_at)`, gets no type, because a type does not pass along a dependency.

## Two types

A column with evidence for two types lists each type with its own evidence count.
ichnos flags an ambiguity and picks neither type, unless the column's declarations give it one type.

## Nullable

ichnos claims that a column is nullable, and never claims `NOT NULL`, because no query can show that a column never holds `NULL`.
`IS NULL`, `IS NOT NULL`, the first argument of `NVL`, `NVL2` or `COALESCE`, and `NULL` assigned by `INSERT`, `UPDATE` or `MERGE` give nullable evidence.
The column must be bare, and no outer join may make its table reference the null-supplying side.

In the corpus, the rule finds `DISCOUNT_PCT`, `PARENT_CATEGORY_ID`, `"ExternalRef"` and `SALES_REP_ID`, and the answer key has all four as nullable.
The outer-join condition drops 005's `o.order_id IS NULL` and 007's `NVL(sl.qty_shipped, 0)`, which test for an absent row.
The answer key has both columns as `NOT NULL`.

## Considered options

- A type passes between columns that a query compares, or across a relationship.
  Rejected because it is cross-query inference, which ADR 0001 rejects for ambiguity, and one wrong type would spread across every join.
- A type from a column name, such as datetime from `_AT`.
  Rejected because no other inference depends on types, as direction depends on keys, and a reader of `CREATED_AT` sees the name.
- Oracle type names such as `VARCHAR2`, `NUMBER` and `DATE`.
  Rejected because they claim a subtype that the evidence cannot show.
- Oracle's conversion rules settle two types.
  `code = 'A'` against a `NUMBER` column raises ORA-01722, while `code = 5` against a `VARCHAR2` column runs when every value is a numeral, so a text literal that is not a numeral would show text.
  Rejected because the rule assumes that every query ran, and the reader sees both counts.
- No nullable claim.
  Rejected because the rule finds four nullable columns in the corpus and no wrong one, and a reader who writes a filter needs to know which columns hold `NULL`.
