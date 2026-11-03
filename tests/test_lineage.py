import ichnos


def _name(
    end: ichnos.Table | ichnos.Column | ichnos.Report | ichnos.OutputColumn,
) -> str:
    match end:
        case ichnos.Table():
            return end.name
        case ichnos.Column():
            return f"{end.table.name}.{end.name}"
        case ichnos.Report():
            return f"report {end.name}"
        case ichnos.OutputColumn():
            return f"report {end.report.name}.{end.name}"


def _deps(graph: ichnos.Graph) -> set[str]:
    return {
        f"{_name(d.upstream)} -> {_name(d.downstream)} {','.join(d.subtypes)}"
        for d in graph.dependencies
    }


def test_a_report_depends_on_each_column_its_values_compute_from():
    graph = ichnos.infer(
        {
            "r": "SELECT o.id, o.qty * o.price AS total, SUM(o.qty) AS units FROM s.orders o GROUP BY o.id",
        }
    )
    assert _deps(graph) == {
        "ORDERS.ID -> report r.ID IDENTITY",
        "ORDERS.QTY -> report r.TOTAL TRANSFORMATION",
        "ORDERS.PRICE -> report r.TOTAL TRANSFORMATION",
        "ORDERS.QTY -> report r.UNITS AGGREGATION",
    }
    [rollup] = graph.rollups
    assert (_name(rollup.upstream), _name(rollup.downstream), len(rollup.queries)) == (
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
    assert _deps(graph) == {
        "ORDERS.QTY -> report r.M AGGREGATION",
        "ORDERS.ID -> report r.ID IDENTITY",
    }


def test_an_insert_with_no_column_list_into_an_undeclared_table_depends_on_the_table():
    graph = ichnos.infer({"i": "INSERT INTO s.t SELECT u.a, u.b + 1 FROM s.u u"})
    assert _deps(graph) == {"U.A -> T IDENTITY", "U.B -> T TRANSFORMATION"}


def test_an_insert_with_a_column_list_maps_each_value():
    graph = ichnos.infer({"i": "INSERT INTO s.t (x, y) SELECT u.a, u.b FROM s.u u"})
    assert _deps(graph) == {"U.A -> T.X IDENTITY", "U.B -> T.Y IDENTITY"}


def test_an_unexpanded_star_gives_a_table_level_dependency():
    graph = ichnos.infer(
        {
            "c": "CREATE VIEW m.v AS SELECT * FROM s.u",
            "r": "SELECT u.*, u.k FROM s.u u",
        }
    )
    assert _deps(graph) == {
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
    assert {d for d in _deps(graph) if not d.startswith("SRC")} == {
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
    assert _deps(graph) == {"B.Y -> A.X IDENTITY", "A.X -> B.Y IDENTITY"}


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
