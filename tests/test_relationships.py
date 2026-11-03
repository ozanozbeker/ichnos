import pytest

import ichnos


def _relationships(graph: ichnos.Graph) -> list[str]:
    def side(columns: tuple[ichnos.Column, ...]) -> str:
        return f"{columns[0].table.name}({', '.join(c.name for c in columns)})"

    return [
        f"{side(r.sides[0])} {'>' if r.direction else '<>'} {side(r.sides[1])} {len(r.join)}"
        for r in graph.relationships
    ]


@pytest.mark.parametrize(
    ("sql", "found"),
    [
        ("SELECT 1 FROM s.a a JOIN s.b b ON a.x = b.y", ["A(X) <> B(Y) 1"]),
        ("SELECT 1 FROM s.a a, s.b b WHERE a.x = b.y AND a.z = 1", ["A(X) <> B(Y) 1"]),
        (
            "SELECT 1 FROM s.a a, s.b b WHERE a.p = b.q AND a.x = b.y",
            ["A(P, X) <> B(Q, Y) 1"],
        ),
        ("SELECT 1 FROM s.a a, s.b b WHERE a.x = b.y OR a.z = 1", []),
        ("SELECT 1 FROM s.a a, s.b b WHERE NOT a.x = b.y", []),
        ("SELECT 1 FROM s.a a, s.b b WHERE LOWER(a.x) = LOWER(b.y)", []),
        ("SELECT 1 FROM s.a a, s.b b WHERE a.x > b.y", []),
        ("SELECT 1 FROM s.a a WHERE a.x = a.y", []),
        ("SELECT 1 FROM s.a a JOIN s.b b USING (x)", ["A(X) <> B(X) 1"]),
        ("SELECT 1 FROM s.a a, s.b b WHERE a.x = b.y (+)", ["A(X) <> B(Y) 1"]),
        (
            "SELECT 1 FROM s.a a WHERE EXISTS (SELECT 1 FROM s.b b WHERE b.y = a.x)",
            ["A(X) <> B(Y) 1"],
        ),
        (
            "SELECT a.x FROM s.a a START WITH a.p IS NULL CONNECT BY PRIOR a.x = a.p",
            ["A(P) <> A(X) 1"],
        ),
        ("SELECT 1 FROM s.a a, s.b b WHERE x = b.y", []),
        (
            "SELECT 1 FROM s.a a JOIN s.b b ON a.x = b.y JOIN s.c c USING (x)",
            ["A(X) <> B(Y) 1"],
        ),
        # The merge key on A(X) gives the relationship its direction.
        (
            "MERGE INTO s.a t USING s.b u ON (t.x = u.y) WHEN MATCHED THEN UPDATE SET t.z = 1",
            ["B(Y) > A(X) 1"],
        ),
        (
            "SELECT 1 FROM s.a a WHERE EXISTS (SELECT 1 FROM (SELECT b.k FROM s.b b) v WHERE v.k = y)",
            [],
        ),
        ("SELECT 1 FROM (SELECT b.k FROM s.b b) v WHERE v.k = y", []),
    ],
)
def test_a_bare_equality_between_two_table_references_gives_evidence(
    sql: str, found: list[str]
):
    assert _relationships(ichnos.infer({"q": sql})) == found


def test_the_side_that_equals_a_key_is_the_referenced_side():
    graph = ichnos.infer(
        {
            "q": "SELECT 1 FROM s.orders o JOIN s.customers c ON o.customer_id = c.customer_id"
        }
    )
    [relationship] = graph.relationships
    assert _relationships(graph) == ["ORDERS(CUSTOMER_ID) > CUSTOMERS(CUSTOMER_ID) 1"]
    assert relationship.direction is not None
    assert relationship.direction.columns == relationship.sides[1]
    assert (
        'Ref "join 1": S.ORDERS.CUSTOMER_ID >? S.CUSTOMERS.CUSTOMER_ID'
        in ichnos.dbml(graph)
    )


def test_two_key_sides_leave_the_direction_unknown():
    graph = ichnos.infer(
        {"q": "SELECT 1 FROM s.orders o JOIN s.items i ON o.order_id = i.item_id"}
    )
    [relationship] = graph.relationships
    assert relationship.direction is None
    assert 'Ref "join 1": S.ITEMS.ITEM_ID ?-? S.ORDERS.ORDER_ID' in ichnos.dbml(graph)


def test_a_shared_reference_is_flagged_and_kept():
    graph = ichnos.infer(
        {
            "a": "SELECT 1 FROM s.lines l JOIN s.products p ON l.product_id = p.product_id",
            "b": "SELECT 1 FROM s.stock k JOIN s.products p ON k.product_id = p.product_id",
            "c": "SELECT 1 FROM s.lines l JOIN s.stock k ON l.product_id = k.product_id",
        }
    )
    shared = [r for r in graph.relationships if r.shared is not None]
    [relationship] = shared
    assert relationship.shared is not None
    assert [c.name for c in relationship.shared.columns] == ["PRODUCT_ID"]
    assert (
        'Ref "join 1, shared reference to S.PRODUCTS.PRODUCT_ID": S.LINES.PRODUCT_ID ?<>? S.STOCK.PRODUCT_ID'
        in ichnos.dbml(graph)
    )


def test_a_natural_join_over_declared_tables_reads_as_using():
    graph = ichnos.infer(
        {
            "a": "CREATE TABLE m.a AS SELECT s.k, s.x FROM s",
            "b": "CREATE TABLE m.b AS SELECT s.k, s.y FROM s",
            "q": "SELECT 1 FROM m.a NATURAL JOIN m.b",
            "r": "SELECT 1 FROM m.a NATURAL JOIN u",
        }
    )
    assert _relationships(graph) == ["A(K) <> B(K) 1"]


def test_a_column_lookup_folds_an_unquoted_name():
    graph = ichnos.infer({"q": 'SELECT o.status, o."Mixed" FROM s.orders o'})
    [table] = graph.tables
    assert table.column("status").name == "STATUS"
    assert table.column('"Mixed"').name == "Mixed"
    with pytest.raises(KeyError):
        table.column("mixed")


@pytest.mark.parametrize(
    ("sql", "found"),
    [
        ("SELECT 1 FROM m.t x JOIN u y ON c = y.c_id", ["U(C_ID) <> T(C) 1"]),
        (
            "SELECT 1 FROM m.t x JOIN u y ON x.a = y.a AND c = y.c_id",
            ["U(A, C_ID) <> T(A, C) 1"],
        ),
        (
            "SELECT 1 FROM m.t x JOIN u y USING (c) JOIN w z USING (c)",
            ["U(C) <> T(C) 1", "W(C) <> T(C) 1"],
        ),
        ("SELECT 1 FROM m.t x JOIN s.w y ON c = y.c_id", ["T(C) <> W(C_ID) 1"]),
        ("SELECT 1 FROM v x, u y WHERE z = y.z", []),
        ("SELECT 1 FROM m.t x, u y WHERE c = x.a", []),
    ],
)
def test_a_column_that_a_declaration_settles_gives_relationship_evidence(
    sql: str, found: list[str]
):
    graph = ichnos.infer(
        {"c": "CREATE TABLE m.t AS SELECT s.a, s.b AS c FROM s", "q": sql}
    )
    assert _relationships(graph) == found
