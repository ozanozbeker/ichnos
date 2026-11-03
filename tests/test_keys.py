import pytest

import ichnos


def _keys(
    graph: ichnos.Graph, table: str
) -> dict[tuple[str, ...], tuple[str | None, dict[str, int]]]:
    [found] = [t for t in graph.tables if t.name == table]
    return {
        tuple(c.name for c in k.columns): (
            k.name_match,
            {s: len(q) for s, q in k.evidence.items()},
        )
        for k in found.keys
    }


@pytest.mark.parametrize(
    ("table", "column", "match"),
    [
        ("WAREHOUSES", "ID", "ID"),
        ("WAREHOUSES", "WAREHOUSE_CODE", "<S>_CODE"),
        ("ADDRESSES", "ADDRESS_ID", "<S>_ID"),
        ("COUNTRIES", "COUNTRY_CODE", "<S>_CODE"),
        ("STATUS", "STATUS_ID", "<S>_ID"),
        ("CUSTOMER_ADDRESSES", "ADDRESS_ID", "<S>_ID"),
        ("ORDERS@ARCHIVE", "ORDER_ID", "<S>_ID"),
        ("ORDER_LINES", "LINE_NO", None),
        ("PROMOTIONS", "PROMO_ID", None),
    ],
)
def test_a_name_match_supports_a_key_on_its_own(
    table: str, column: str, match: str | None
):
    graph = ichnos.infer({"q": f"SELECT t.{column} FROM s.{table} t"})  # noqa: S608 # fixed test text
    assert _keys(graph, table) == ({(column,): (match, {})} if match else {})


def test_the_last_word_pattern_yields_to_a_table_of_that_name():
    graph = ichnos.infer(
        {
            "q": "SELECT ur.role_id FROM s.user_roles ur",
            "r": "SELECT r.x FROM s.roles r",
        }
    )
    assert _keys(graph, "USER_ROLES") == {}


@pytest.mark.parametrize(
    ("sql", "keys"),
    [
        (
            "INSERT INTO s.orders (order_id) VALUES (s.seq.NEXTVAL)",
            {("ORDER_ID",): ("<S>_ID", {"generated": 1})},
        ),
        (
            "UPDATE s.notes n SET n.guid = SYS_GUID()",
            {("GUID",): (None, {"generated": 1})},
        ),
        ("INSERT INTO s.notes (guid) VALUES (s.seq.CURRVAL)", {}),
        (
            "MERGE INTO s.stock t USING s.src u ON (t.a = u.a AND t.b = :b) WHEN MATCHED THEN UPDATE SET t.c = 1",
            {("A", "B"): (None, {"merge": 1})},
        ),
        (
            "MERGE INTO s.stock t USING s.src u ON (t.a = u.a AND t.flag = 'Y') WHEN MATCHED THEN UPDATE SET t.c = 1",
            {},
        ),
        (
            "MERGE INTO s.stock t USING s.src u ON (t.a = u.a OR t.b = u.b) WHEN MATCHED THEN UPDATE SET t.c = 1",
            {},
        ),
        (
            "MERGE INTO s.stock t USING s.src u ON (a = u.a) WHEN MATCHED THEN UPDATE SET t.c = 1",
            {},
        ),
    ],
)
def test_dml_shapes_give_key_evidence(
    sql: str, keys: dict[tuple[str, ...], tuple[str | None, dict[str, int]]]
):
    graph = ichnos.infer({"q": sql})
    assert (
        _keys(
            graph,
            next(t.name for t in graph.tables if t.write),
        )
        == keys
    )


@pytest.mark.parametrize(
    ("subquery", "found"),
    [
        ("(SELECT x.v FROM s.ships x WHERE x.ref = :id)", True),
        ("(SELECT x.v FROM s.ships x WHERE x.ref = o.ship_id)", True),
        ("(SELECT v FROM s.ships WHERE ref = o.ship_id)", True),
        ("(SELECT MAX(x.v) FROM s.ships x WHERE x.ref = :id)", False),
        ("(SELECT x.v FROM s.ships x WHERE x.ref = 5)", False),
        ("(SELECT x.v FROM s.ships x WHERE x.ref = :id OR x.ref = :j)", False),
        ("(SELECT x.v FROM s.ships x WHERE x.ref = :id AND ROWNUM = 1)", False),
        ("(SELECT DISTINCT x.v FROM s.ships x WHERE x.ref = :id)", False),
        ("(SELECT x.v FROM s.ships x, s.more m WHERE x.ref = :id)", False),
        ("(SELECT 1 FROM dual)", False),
        ("(SELECT x.v FROM s.ships x)", False),
        ("(WITH c AS (SELECT 1 AS v FROM dual) SELECT c.v FROM c)", False),
    ],
)
def test_a_single_row_subquery_gives_key_evidence(subquery: str, found: bool):
    graph = ichnos.infer({"q": f"SELECT o.a FROM s.orders o WHERE o.b = {subquery}"})  # noqa: S608 # fixed test text
    ships = [t for t in graph.tables if t.name == "SHIPS"]
    keys = {tuple(c.name for c in k.columns) for t in ships for k in t.keys}
    assert keys == ({("REF",)} if found else set())


def test_a_subquery_that_takes_many_rows_gives_no_key_evidence():
    graph = ichnos.infer(
        {
            "q": "SELECT o.a FROM s.orders o WHERE o.b IN (SELECT x.v FROM s.ships x WHERE x.ref = :id)"
        }
    )
    assert all(not t.keys for t in graph.tables if t.name == "SHIPS")


@pytest.mark.parametrize(
    ("select", "key"),
    [
        ("SELECT s.a, s.b, SUM(s.c) AS c FROM s GROUP BY s.a, s.b", ("A", "B")),
        ("SELECT DISTINCT s.a, s.b FROM s", ("A", "B")),
        ("SELECT s.a FROM s UNION SELECT u.a FROM u", ("A",)),
        ("SELECT s.a FROM s MINUS SELECT u.a FROM u", ("A",)),
        ("SELECT s.a FROM s UNION ALL SELECT u.a FROM u", None),
        ("SELECT s.a, SUM(s.c) AS c FROM s GROUP BY ROLLUP (s.a)", None),
        ("SELECT * FROM s", None),
    ],
)
def test_a_creating_query_gives_grouped_key_evidence(
    select: str, key: tuple[str, ...] | None
):
    graph = ichnos.infer({"q": f"CREATE TABLE m.t AS {select}"})
    assert _keys(graph, "T") == ({key: (None, {"grouped": 1})} if key else {})


def test_a_mapped_insert_value_gives_generated_key_evidence():
    graph = ichnos.infer(
        {
            "c": "CREATE TABLE m.t AS SELECT s.a AS id, s.b FROM s",
            "i": "INSERT INTO m.t VALUES (m.seq.NEXTVAL, 'x')",
        }
    )
    assert _keys(graph, "T") == {("ID",): ("ID", {"generated": 1})}


def test_dbml_writes_each_key_as_a_unique_index_and_never_a_primary_key():
    graph = ichnos.infer(
        {
            "q": "SELECT w.id, w.warehouse_code FROM inv.warehouses w",
            "m": "MERGE INTO inv.stock t USING s u ON (t.a = u.a AND t.b = u.b) WHEN MATCHED THEN UPDATE SET t.c = 1",
        }
    )
    text = ichnos.dbml(graph)
    assert "keys: 'ID: name match ID; WAREHOUSE_CODE: name match <S>_CODE'" in text
    assert "keys: '(A, B): merge 1'" in text
    assert "    (A, B) [unique]" in text
    assert "pk" not in text
