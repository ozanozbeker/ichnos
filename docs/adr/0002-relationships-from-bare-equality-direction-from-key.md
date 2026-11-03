# Infer relationships from bare column equality, and take direction from the key

A relationship gets evidence only from a bare column compared with `=` to a bare column of another table reference, in an AND-connected conjunct.
A function, a comparison other than `=`, an `OR` or a `NOT` gives no evidence, because such a predicate rarely encodes a key and is the usual shape of an incidental join, such as `LOWER(c.email) = LOWER(e.email)`.
Every such equality between the same two table references in one query forms one relationship, so a composite key such as `(ORDER_ID, LINE_NO)` stays whole.
`CONNECT BY PRIOR a = b` with bare columns also gives evidence, for a relationship between two columns of one table, because it compares a column of one row with a column of another row.
`USING (col)` reads as `left.col = right.col`.
A `NATURAL JOIN` gives evidence only between two declared tables, where it reads as `USING` over their shared declared names ([ADR 0008](0008-declarations-settle-ambiguities-until-contradicted.md)).

A relationship has no direction of its own.
The side whose columns equal one of its table's keys ([ADR 0006](0006-keys-from-name-matches-and-four-query-shapes.md)) is the referenced side, and with no such side, or two, the direction stays unknown.
The outer-join side says nothing: in the synthetic corpus, 005 makes the child optional and 006 makes the parent optional.
ichnos claims no cardinality beyond the many-to-one that a known direction implies.

A relationship whose sides both refer to the same key of a third table is flagged as a shared reference and kept, because dropping it would suppress evidence on a heuristic.

## Considered options

- Every comparison between two columns counts.
  Rejected because function-wrapped and non-equality joins add incidental relationships with no gain in recall.
- Each column pair is its own relationship.
  Rejected because it can never produce a composite relationship.
- Direction from naming, the outer-join side, the subquery side or the `PRIOR` side.
  Rejected because naming belongs to key inference and the other three point either way.
