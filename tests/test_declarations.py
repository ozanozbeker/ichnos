import ichnos


def _table(graph: ichnos.Graph, name: str) -> ichnos.Table:
    return next(t for t in graph.tables if t.name == name)


def _columns(table: ichnos.Table) -> dict[str, list[str]]:
    return {c.name: sorted(c.references) for c in table.columns}


CREATE = "CREATE TABLE m.t AS SELECT s.a, s.b AS c FROM s"


def test_a_creating_query_declares_its_kind_and_column_list():
    graph = ichnos.infer(
        {
            "table": CREATE,
            "view": "CREATE OR REPLACE FORCE VIEW m.v (x, y) AS SELECT s.a, s.b FROM s",
            "mview": "CREATE MATERIALIZED VIEW m.mv AS SELECT s.a FROM s",
        }
    )
    table, view, mview = (_table(graph, n) for n in ("T", "V", "MV"))
    assert (table.kind, view.kind, mview.kind) == (
        "base table",
        "view",
        "materialized view",
    )
    assert [d.columns for d in view.declarations] == [("X", "Y")]
    assert [c.name for c in table.columns] == ["A", "C"]
    assert [q.name for q in table.columns[1].declared] == ["table"]
    assert table.complete
    assert "Table m.T" not in ichnos.dbml(graph)
    assert (
        "Table M.T [kind: 'base table', complete: true, declared: 1] {\n  A unknown [declared: 1]\n  C unknown [declared: 1]\n}"
        in ichnos.dbml(graph)
    )


def test_a_declaration_settles_an_ambiguity():
    graph = ichnos.infer({"c": CREATE, "q": "SELECT c, z FROM m.t, u"})
    assert graph.ambiguities == ()
    assert _columns(_table(graph, "T")) == {"A": [], "C": ["select"]}
    assert _columns(_table(graph, "U")) == {"Z": ["select"]}


def test_a_declaration_removes_a_candidate_that_lacks_the_column():
    graph = ichnos.infer({"c": CREATE, "q": "SELECT 1 FROM m.t, w WHERE z = 1"})
    assert graph.ambiguities == ()
    assert _columns(_table(graph, "W")) == {"Z": ["where"]}


def test_an_outer_candidate_takes_a_column_only_when_every_inner_one_is_removed():
    graph = ichnos.infer(
        {
            "c": CREATE,
            "d": "CREATE VIEW m.v AS SELECT s.x FROM s",
            "q": "SELECT 1 FROM u WHERE EXISTS (SELECT 1 FROM m.t, m.v WHERE z = 1 AND c = 2)",
        }
    )
    assert graph.ambiguities == ()
    assert _columns(_table(graph, "U")) == {"Z": ["where"]}
    assert _columns(_table(graph, "T"))["C"] == ["where"]
    assert _table(graph, "T").contradictions == ()


def test_an_ambiguity_whose_every_candidate_lacks_the_column_contradicts_them():
    graph = ichnos.infer(
        {
            "c": CREATE,
            "d": "CREATE VIEW m.v AS SELECT s.x FROM s",
            "q": "SELECT z FROM m.t, m.v",
        }
    )
    t, v = _table(graph, "T"), _table(graph, "V")
    assert [(c.query.name, c.reason, c.column) for c in t.contradictions] == [
        ("q", "undeclared column", "Z")
    ]
    assert [a.kind for a in graph.ambiguities] == ["column"]
    assert not t.complete
    assert not v.complete


def test_an_undeclared_column_contradicts_the_declaration_and_stays():
    graph = ichnos.infer(
        {"c": CREATE, "q": "SELECT t.z FROM m.t t", "r": "SELECT c FROM m.t, u"}
    )
    table = _table(graph, "T")
    assert [(c.query.name, c.reason, c.column) for c in table.contradictions] == [
        ("q", "undeclared column", "Z")
    ]
    assert table.kind == "base table"
    assert not table.complete
    [z] = [c for c in table.columns if c.undeclared]
    assert z.name == "Z"
    # A contradicted declaration settles nothing more.
    assert [a.subject for a in graph.ambiguities] == ["C"]
    text = ichnos.dbml(graph)
    assert (
        "Table M.T [kind: 'base table', declared: 1, read: 2, contradicted: 'q: undeclared column Z'"
        in text
    )
    assert "  Z unknown [select: 1, undeclared: true]" in text


def test_two_declarations_that_differ_give_an_ambiguity():
    graph = ichnos.infer({"c": CREATE, "d": "CREATE VIEW m.t AS SELECT s.a FROM s"})
    table = _table(graph, "T")
    assert table.kind is None
    assert [(d.kind, d.columns) for d in table.declarations] == [
        ("base table", ("A", "C")),
        ("view", ("A",)),
    ]
    assert {(c.query.name, c.reason) for c in table.contradictions} == {
        ("c", "declaration"),
        ("d", "declaration"),
    }
    [ambiguity] = graph.ambiguities
    assert (ambiguity.kind, ambiguity.query, ambiguity.subject) == (
        "declaration",
        None,
        "M.T",
    )
    assert list(ambiguity.candidates) == ["base table (A, C)", "view (A)"]
    assert "kind: 'base table|view'" in ichnos.dbml(graph)
    assert "ambiguity: 'M.T is base table (A, C) (1) or view (A) (1)'" in ichnos.dbml(
        graph
    )


def test_two_declarations_that_match_count_twice():
    graph = ichnos.infer({"c": CREATE, "d": CREATE.replace("SELECT", "SELECT  ")})
    table = _table(graph, "T")
    [declaration] = table.declarations
    assert [q.name for q in declaration.queries] == ["c", "d"]
    assert "A unknown [declared: 2]" in ichnos.dbml(graph)


def test_an_insert_with_no_column_list_maps_each_value_by_position():
    graph = ichnos.infer(
        {
            "c": CREATE,
            "i": "INSERT INTO m.t SELECT u.p, u.q FROM u",
            "v": "INSERT INTO m.t VALUES (1, 2)",
            "a": "INSERT ALL INTO m.t INTO m.t VALUES (x, y) SELECT u.x, u.y FROM u",
            "m": "MERGE INTO m.t t USING u ON (t.a = u.a) WHEN NOT MATCHED THEN INSERT VALUES (u.a, u.c)",
        }
    )
    table = _table(graph, "T")
    assert table.contradictions == ()
    assert {
        c.name: [q.name for q in c.references["insert"]] for c in table.columns
    } == {
        "A": ["a", "i", "m", "v"],
        "C": ["a", "i", "m", "v"],
    }


def test_an_insert_with_a_different_value_count_contradicts_the_declaration():
    graph = ichnos.infer({"c": CREATE, "i": "INSERT INTO m.t SELECT u.p FROM u"})
    table = _table(graph, "T")
    assert [(c.query.name, c.reason, c.column) for c in table.contradictions] == [
        ("i", "value count", None)
    ]
    assert all("insert" not in c.references for c in table.columns)


def test_a_star_over_a_declared_table_expands_to_its_columns():
    graph = ichnos.infer(
        {
            "c": CREATE,
            "v": "CREATE VIEW m.v AS SELECT * FROM m.t WHERE c = 1",
            "w": "CREATE VIEW m.w AS SELECT t.*, u.z FROM m.t t, u",
        }
    )
    assert [d.columns for d in _table(graph, "V").declarations] == [("A", "C")]
    assert [d.columns for d in _table(graph, "W").declarations] == [("A", "C", "Z")]
    assert _table(graph, "W").complete


def test_a_star_over_an_undeclared_table_stays_unexpanded():
    graph = ichnos.infer({"v": "CREATE VIEW m.v AS SELECT u.*, 1 AS one FROM u"})
    view = _table(graph, "V")
    assert [d.columns for d in view.declarations] == [("ONE",)]
    assert not view.complete


def test_user_read_as_a_column_contradicts_nothing():
    graph = ichnos.infer(
        {"c": CREATE, "q": "SELECT t.a, USER FROM m.t t WHERE t.c = UID"}
    )
    assert _table(graph, "T").contradictions == ()


def test_a_star_among_inserted_values_expands_through_a_declaration():
    graph = ichnos.infer(
        {
            "c": CREATE,
            "d": "CREATE TABLE m.u AS SELECT s.p, s.q FROM s",
            "i": "INSERT INTO m.t SELECT * FROM m.u",
            "j": "INSERT INTO m.t SELECT * FROM x",
        }
    )
    table = _table(graph, "T")
    assert table.contradictions == ()
    assert [q.name for q in table.columns[0].references["insert"]] == ["i"]
