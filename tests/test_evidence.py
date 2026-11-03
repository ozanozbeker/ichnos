import pytest

import ichnos


def _column(graph: ichnos.Graph, table: str, column: str) -> ichnos.Column:
    return next(
        c
        for t in graph.tables
        if t.name == table
        for c in t.columns
        if c.name == column
    )


def test_identical_text_counts_once():
    text = "SELECT o.status FROM sales.orders o"
    graph = ichnos.infer({"a": text, "b": text})
    status = _column(graph, "ORDERS", "STATUS")
    assert [q.name for q in status.references["select"]] == ["a", "b"]
    assert "STATUS unknown [select: 1]" in ichnos.dbml(graph)


def test_a_count_is_of_queries_not_of_references():
    graph = ichnos.infer(
        {
            "q": "SELECT o.status FROM sales.orders o WHERE o.status = 'A' OR o.status = 'B'"
        }
    )
    assert "STATUS unknown [select: 1, where: 1]" in ichnos.dbml(graph)


def test_an_unqualified_column_over_two_tables_gives_no_evidence():
    graph = ichnos.infer(
        {"q": "SELECT order_id FROM sales.orders o, sales.customers c"}
    )
    assert all(t.columns == () for t in graph.tables)


def test_each_reference_position_counts_on_its_own():
    graph = ichnos.infer(
        {
            "q": """
            SELECT o.status, SUM(o.total), ROW_NUMBER() OVER (PARTITION BY o.region ORDER BY o.day)
              FROM sales.orders o
              JOIN sales.lines l ON l.order_id = o.order_id
             WHERE o.flag = 1 AND o.a = l.b
             GROUP BY o.status
            HAVING COUNT(o.x) > 1
             ORDER BY o.status
        """,
            "u": "UPDATE sales.orders o SET o.flag = 0 WHERE o.status = 'X'",
            "i": "INSERT INTO sales.orders (order_id) VALUES (1)",
        }
    )
    positions = {
        c.name: sorted(c.references)
        for t in graph.tables
        if t.name == "ORDERS"
        for c in t.columns
    }
    assert positions == {
        "A": ["join"],
        "DAY": ["order_by"],
        "FLAG": ["set", "where"],
        "ORDER_ID": ["insert", "join"],
        "REGION": ["group_by"],
        "STATUS": ["group_by", "order_by", "select", "where"],
        "TOTAL": ["aggregate"],
        "X": ["aggregate"],
    }


def test_two_queries_with_one_name_raise():
    with pytest.raises(
        ichnos.IchnosError, match=r"two queries are named a#1, in a and a#1"
    ):
        ichnos.infer(
            {"a#1": "SELECT 1 FROM t", "a": "SELECT 1 FROM t; SELECT 2 FROM t"}
        )
