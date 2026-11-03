from conftest import dependency_lines, end_name

import ichnos


def test_a_report_depends_on_each_column_its_values_compute_from():
    graph = ichnos.infer(
        {
            "r": "SELECT o.id, o.qty * o.price AS total, SUM(o.qty) AS units FROM s.orders o GROUP BY o.id",
        }
    )
    assert dependency_lines(graph.dependencies) == {
        "ORDERS.ID -> report r.ID IDENTITY",
        "ORDERS.QTY -> report r.TOTAL TRANSFORMATION",
        "ORDERS.PRICE -> report r.TOTAL TRANSFORMATION",
        "ORDERS.QTY -> report r.UNITS AGGREGATION",
        "ORDERS.ID -> report r GROUP_BY",
    }
    [rollup] = graph.rollups
    assert (
        end_name(rollup.upstream),
        end_name(rollup.downstream),
        len(rollup.queries),
    ) == (
        "ORDERS",
        "report r",
        1,
    )


def test_a_path_through_a_local_relation_takes_its_first_direct_subtype():
    graph = ichnos.infer(
        {
            "r": "WITH c AS (SELECT SUM(o.qty) AS n, o.id FROM s.orders o GROUP BY o.id) SELECT c.n + 1 AS m, c.id FROM c",
        }
    )
    assert dependency_lines(graph.dependencies) == {
        "ORDERS.QTY -> report r.M AGGREGATION",
        "ORDERS.ID -> report r.ID IDENTITY",
        "ORDERS.ID -> report r GROUP_BY",
    }


def test_an_insert_with_no_column_list_into_an_undeclared_table_depends_on_the_table():
    graph = ichnos.infer({"i": "INSERT INTO s.t SELECT u.a, u.b + 1 FROM s.u u"})
    assert dependency_lines(graph.dependencies) == {
        "U.A -> T IDENTITY",
        "U.B -> T TRANSFORMATION",
    }


def test_an_insert_with_a_column_list_maps_each_value():
    graph = ichnos.infer({"i": "INSERT INTO s.t (x, y) SELECT u.a, u.b FROM s.u u"})
    assert dependency_lines(graph.dependencies) == {
        "U.A -> T.X IDENTITY",
        "U.B -> T.Y IDENTITY",
    }


def test_an_unexpanded_star_gives_a_table_level_dependency():
    graph = ichnos.infer(
        {
            "c": "CREATE VIEW m.v AS SELECT * FROM s.u",
            "r": "SELECT u.*, u.k FROM s.u u",
        }
    )
    assert dependency_lines(graph.dependencies) == {
        "U -> V IDENTITY",
        "U -> report r IDENTITY",
        "U.K -> report r.K IDENTITY",
    }
    assert "Dep: S.U -> M.V [queries: 1, identity: 1]" in ichnos.dbml(graph)


def test_a_star_that_a_declaration_expands_depends_on_each_column():
    graph = ichnos.infer(
        {
            "c": "CREATE TABLE m.t AS SELECT s.a, s.b FROM s.src s",
            "v": "CREATE VIEW m.v AS SELECT * FROM m.t",
            "i": "INSERT INTO m.t SELECT * FROM m.t",
            "r": "SELECT * FROM m.t",
        }
    )
    assert {
        d for d in dependency_lines(graph.dependencies) if not d.startswith("SRC")
    } == {
        "T.A -> V.A IDENTITY",
        "T.B -> V.B IDENTITY",
        "T.A -> T.A IDENTITY",
        "T.B -> T.B IDENTITY",
        "T.A -> report r.A IDENTITY",
        "T.B -> report r.B IDENTITY",
    }


def test_a_cycle_through_two_tables_keeps_both_dependencies():
    graph = ichnos.infer(
        {
            "a": "INSERT INTO s.a (x) SELECT b.y FROM s.b b",
            "b": "INSERT INTO s.b (y) SELECT a.x FROM s.a a",
        }
    )
    assert dependency_lines(graph.dependencies) == {
        "B.Y -> A.X IDENTITY",
        "A.X -> B.Y IDENTITY",
    }


def test_a_self_dependency_is_a_column_property():
    graph = ichnos.infer({"u": "UPDATE s.t SET t.a = t.a + 1"})
    text = ichnos.dbml(graph)
    assert "Metadata Column S.T.A {\n  self_dependency: 'TRANSFORMATION 1'\n}" in text
    assert "Dep: S.T.A -> S.T.A" not in text
    assert "Dep: S.T -> S.T [queries: 1]" in text


def test_an_ambiguous_upstream_column_gives_a_dependency_ambiguity():
    graph = ichnos.infer(
        {
            "i": "INSERT INTO s.t (x) SELECT a FROM s.u, s.w",
            "j": "INSERT INTO s.v SELECT a FROM s.u, s.w",
            "r": "SELECT a FROM s.u, s.w",
        }
    )
    dependencies = [a for a in graph.ambiguities if a.kind == "dependency"]
    assert [(a.query.name if a.query else None, a.subject) for a in dependencies] == [
        ("i", "A"),
        ("j", "A"),
        ("r", "A"),
    ]
    assert graph.dependencies == ()
    t, v = (next(t for t in graph.tables if t.name == n) for n in ("T", "V"))
    assert [a.kind for a in t.columns[0].ambiguities] == ["dependency"]
    assert [a.kind for a in v.ambiguities] == ["dependency"]
    text = ichnos.dbml(graph)
    assert "  A unknown [ambiguity: 'r: upstream A is S.U.A (0) or S.W.A (0)']" in text
    assert (
        "  X unknown [insert: 1, ambiguity: 'i: upstream A is S.U.A (0) or S.W.A (0)']"
        in text
    )


def test_a_clause_gives_an_indirect_dependency_on_the_downstream_end():
    graph = ichnos.infer(
        {
            "r": """SELECT o.id, CASE WHEN o.total > 10 THEN 'L' END AS band,
                       ROW_NUMBER() OVER (PARTITION BY o.region ORDER BY o.day) AS rn
                  FROM s.orders o JOIN s.lines l ON l.order_id = o.id
                 WHERE o.status = 'A' GROUP BY o.id, o.total, o.region, o.day ORDER BY o.id""",
        }
    )
    assert {d for d in dependency_lines(graph.dependencies) if "->" in d} >= {
        "ORDERS.TOTAL -> report r.BAND CONDITIONAL",
        "ORDERS.REGION -> report r.RN WINDOW",
        "ORDERS.DAY -> report r.RN WINDOW",
        "LINES.ORDER_ID -> report r JOIN",
        "ORDERS.ID -> report r JOIN,GROUP_BY,SORT",
        "ORDERS.STATUS -> report r FILTER",
    }
    [dependency] = [
        d
        for d in graph.dependencies
        if end_name(d.downstream) == "report r" and end_name(d.upstream) == "ORDERS.ID"
    ]
    assert (dependency.direct, dependency.indirect) == (False, True)


def test_count_of_a_star_or_a_literal_reads_whole_rows():
    graph = ichnos.infer(
        {
            "r": "SELECT COUNT(*) AS n, COUNT(1) AS m, COUNT(DISTINCT o.id) AS k FROM s.orders o HAVING COUNT(*) > 1",
        }
    )
    assert dependency_lines(graph.dependencies) == {
        "ORDERS -> report r.N AGGREGATION",
        "ORDERS -> report r.M AGGREGATION",
        "ORDERS.ID -> report r.K AGGREGATION",
        "ORDERS -> report r FILTER",
    }
    assert "Dep: S.ORDERS -> report.r [queries: 1, filter: 1]" in ichnos.dbml(graph)


def test_count_over_a_window_reads_whole_rows_and_its_window_columns():
    graph = ichnos.infer(
        {"r": "SELECT COUNT(*) OVER (PARTITION BY o.region) AS n FROM s.orders o"}
    )
    assert dependency_lines(graph.dependencies) == {
        "ORDERS -> report r.N AGGREGATION",
        "ORDERS.REGION -> report r.N WINDOW",
    }


def test_an_insert_all_when_condition_filters_its_into_target():
    graph = ichnos.infer(
        {
            "i": "INSERT ALL WHEN k > 1 THEN INTO s.big (x) VALUES (v) INTO s.every (x) VALUES (v) SELECT u.k, u.v FROM s.u u",
        }
    )
    assert dependency_lines(graph.dependencies) == {
        "U.K -> BIG FILTER",
        "U.V -> BIG.X IDENTITY",
        "U.V -> EVERY.X IDENTITY",
    }


def test_every_minus_branch_after_the_first_filters_the_rows():
    graph = ichnos.infer(
        {"r": "SELECT a.x FROM s.a a MINUS SELECT b.y FROM s.b b WHERE b.z = 1"}
    )
    assert dependency_lines(graph.dependencies) == {
        "A.X -> report r.X IDENTITY",
        "B.Y -> report r FILTER",
        "B.Z -> report r FILTER",
    }


def test_a_delete_gives_no_dependency():
    graph = ichnos.infer({"d": "DELETE FROM s.t WHERE t.a IN (SELECT u.b FROM s.u u)"})
    assert graph.dependencies == ()


def test_merge_and_update_clauses_select_the_written_rows():
    graph = ichnos.infer(
        {
            "m": """MERGE INTO s.t t USING s.u u ON (t.k = u.k)
                WHEN MATCHED THEN UPDATE SET t.v = u.v WHERE u.flag = 1
                WHEN NOT MATCHED THEN INSERT VALUES (u.k, u.v)""",
            "u": "UPDATE s.w w SET w.a = 1 WHERE w.b = 2",
        }
    )
    # The INSERT has no column list and T no declaration, so its values depend on the table.
    assert dependency_lines(graph.dependencies) == {
        "T.K -> T JOIN",
        "U.K -> T IDENTITY,JOIN",
        "U.V -> T IDENTITY",
        "U.V -> T.V IDENTITY",
        "U.FLAG -> T FILTER",
        "W.B -> W FILTER",
    }
