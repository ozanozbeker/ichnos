import ichnos


def _columns(graph: ichnos.Graph) -> dict[str, list[str]]:
    return {
        f"{t.owner}.{t.name}" if t.owner else t.name: [c.name for c in t.columns]
        for t in graph.tables
    }


def test_pseudocolumns_and_functions_read_as_columns_are_dropped():
    graph = ichnos.infer(
        {
            "q": 'SELECT ROWNUM, t.ROWID, LEVEL, USER, s.seq.NEXTVAL, t."LEVEL", t."USER" FROM t CONNECT BY PRIOR t.a = t.b',
        }
    )
    assert _columns(graph) == {"T": ["A", "B", "LEVEL", "USER"]}


def test_dual_is_not_a_table():
    assert ichnos.infer({"q": "SELECT SYSDATE FROM dual"}).tables == ()


def test_a_column_qualified_by_owner_and_table_resolves():
    assert _columns(
        ichnos.infer({"q": "SELECT sales.orders.order_id FROM sales.orders"})
    ) == {"SALES.ORDERS": ["ORDER_ID"]}


def test_a_star_names_no_column():
    graph = ichnos.infer({"q": "SELECT t.*, v.* FROM t, (SELECT u.a FROM u) v"})
    assert _columns(graph) == {"T": [], "U": ["A"]}


def test_a_local_relation_that_holds_a_name_takes_the_reference():
    graph = ichnos.infer({"q": "SELECT a, b FROM (SELECT u.a FROM u) v, t"})
    assert _columns(graph) == {"T": ["B"], "U": ["A"]}


def test_a_local_relation_whose_names_a_star_hides_takes_no_reference():
    graph = ichnos.infer({"q": "WITH c AS (SELECT * FROM u) SELECT a, c.b FROM c, t"})
    assert _columns(graph) == {"T": [], "U": []}


def test_a_cte_without_a_column_list_takes_the_names_of_its_first_branch():
    graph = ichnos.infer(
        {
            "q": "WITH c AS (SELECT u.a FROM u UNION SELECT w.b FROM w) SELECT a FROM c, t"
        }
    )
    assert _columns(graph) == {"T": [], "U": ["A"], "W": ["B"]}


def test_a_set_operation_orders_by_its_output_names():
    graph = ichnos.infer({"q": "SELECT u.a FROM u UNION SELECT w.b FROM w ORDER BY a"})
    assert {c.name: sorted(c.references) for t in graph.tables for c in t.columns} == {
        "A": ["select"],
        "B": ["select"],
    }


def test_using_with_two_tables_on_the_left_gives_no_evidence_for_the_left():
    graph = ichnos.infer(
        {"q": "SELECT t1.x FROM t1 JOIN t2 ON t1.i = t2.i JOIN t3 USING (k)"}
    )
    assert _columns(graph) == {"T1": ["I", "X"], "T2": ["I"], "T3": ["K"]}


def test_a_query_ichnos_cannot_read_records_nothing():
    graph = ichnos.infer(
        {
            "alter": "ALTER TABLE t ADD x NUMBER",
            "alias": "SELECT x.a FROM t",
            "owner": "SELECT s.u.a FROM t",
            "values": "SELECT v.a FROM (VALUES (1)) v (a)",
        }
    )
    assert graph.tables == ()
    assert len(graph.unparsed) == 4
