# Literals give type and observed-value evidence, and ichnos never claims an enum

A bare column compared with a literal, or assigned one, gives evidence of the column's type: text, number, datetime or interval.
A value in an `INSERT` with no column list is assigned to the column that [ADR 0008](0008-declarations-settle-ambiguities-until-contradicted.md) maps it to by position.
Oracle converts types implicitly, so `code = 5` runs against a text column, and the literal is evidence, not proof.

A text or number literal under equality or assignment also gives an observed value.
Equality means `=`, `<>`, `!=`, `IN`, `NOT IN`, a `DECODE` search argument or a simple `CASE col WHEN`.
A range comparison or a `LIKE` pattern gives type evidence only, because `> 10000` and `'SPRING%'` are thresholds and patterns, not values a column holds.
A datetime literal under `=` picks one point in a range, so it gives type evidence only too.

ichnos never writes a DBML `enum` and never calls observed values allowed values.
A corpus shows only the values its queries mention, never a column's full set.
The output lists a column's observed values when it has at most 20, and only their number above that, because a column with hundreds of values is usually ad hoc ID lookups.

A literal gives no key evidence and no relationship evidence.
`WHERE status = 'A'` and `WHERE customer_id = 1042` have the same shape, so a literal comparison cannot tell a key lookup from a filter.

## Considered options

- Literals give no evidence.
  Rejected because an LLM that knows `STATUS` holds `PAID` and `SHIPPED` writes correct filters, and the design does not hide data.
- Every comparison with a literal gives an observed value.
  Rejected because thresholds and `LIKE` patterns would fill the list with values no row holds.
- A DBML `enum` for a column with few values.
  Rejected because an enum claims a closed set.
- A length claim from the longest literal, such as `CHAR(1)` from `'A'`.
  Rejected because the listed values already show the length, and the claim would guess between `CHAR(1)` and `VARCHAR2(10)`.
