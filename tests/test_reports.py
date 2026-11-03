import pytest

import ichnos


def _outputs(sql: str, **files: str) -> list[str]:
    graph = ichnos.infer({"r": sql, **files})
    [report] = [r for r in graph.reports if r.name == "r"]
    return [c.name for c in report.output_columns]


@pytest.mark.parametrize(
    ("select", "names"),
    [
        ("o.id, o.status AS state", ["ID", "STATE"]),
        ('o."ExternalRef", o.amount AS "Paid Amount"', ["ExternalRef", "Paid Amount"]),
        ("count( * ), o.qty * o.price", ["COUNT(*)", "O.QTY*O.PRICE"]),
        ("o.qty /* units */ * o.price, 'a b' || o.x", ["O.QTY*O.PRICE", "'AB'||O.X"]),
        ("TRUNC(SYSDATE), NVL(o.rep, -1)", ["TRUNC(SYSDATE)", "NVL(O.REP,-1)"]),
        ("o.id, o2.id, o.id", ["ID", "ID (2)", "ID (3)"]),
        ('o.a AS "ID (2)", o.b AS id, o.c AS id', ["ID (2)", "ID", "ID (3)"]),
        ('o.id, o.b AS "ID"', ["ID", "ID (2)"]),
    ],
)
def test_an_output_column_takes_the_name_oracle_gives_it(select: str, names: list[str]):
    assert _outputs(f"SELECT {select} FROM s.orders o, s.orders o2") == names  # noqa: S608 # fixed test text


def test_a_parenthesized_first_branch_names_the_output_columns():
    assert _outputs(
        "(SELECT o.a + 1 FROM s.orders o) UNION SELECT p.b FROM s.pay p"
    ) == ["O.A+1"]
    assert _outputs("WITH c AS (SELECT o.a FROM s.orders o) SELECT c.a * 2 FROM c") == [
        "C.A*2"
    ]


def test_a_hint_and_distinct_stay_out_of_the_first_name():
    assert _outputs("SELECT /*+ FULL(o) */ DISTINCT o.qty + 1 FROM s.orders o") == [
        "O.QTY+1"
    ]


def test_a_star_expands_through_local_relations_and_declarations():
    assert _outputs("SELECT * FROM (SELECT o.a, o.b FROM s.orders o)") == ["A", "B"]
    declared = {"c": "CREATE TABLE m.t AS SELECT s.x, s.y FROM s"}
    assert _outputs("SELECT t.*, 1 AS one FROM m.t t", **declared) == ["X", "Y", "ONE"]
    assert _outputs("SELECT u.*, 1 AS one FROM u") == ["ONE"]


def test_a_query_that_reads_no_table_is_no_report():
    graph = ichnos.infer({"a": "SELECT SYSDATE FROM dual", "b": "SELECT 1 AS one"})
    assert graph.reports == ()
    assert graph.unparsed == ()


def test_a_query_over_dual_that_reads_a_table_through_a_scalar_subquery_is_a_report():
    assert _outputs("SELECT (SELECT MAX(o.id) FROM s.orders o) AS top FROM dual") == [
        "TOP"
    ]


def test_a_file_with_several_queries_numbers_its_reports():
    graph = ichnos.infer(
        {"f": "CREATE TABLE m.t AS SELECT s.x FROM s; SELECT t.x FROM m.t t"}
    )
    assert [r.name for r in graph.reports] == ["f#2"]


def test_a_comment_after_the_last_query_adds_no_query():
    graph = ichnos.infer(
        {"f": "SELECT t.x FROM t;\n-- end of file\n", "g": "-- only a note"}
    )
    assert ([r.name for r in graph.reports], graph.unparsed) == (["f"], ())


def test_an_output_column_with_a_fixed_type_takes_it():
    graph = ichnos.infer(
        {"r": "SELECT COUNT(*) AS n, 'x' AS label, o.id FROM s.orders o"}
    )
    [report] = graph.reports
    assert [list(c.types) for c in report.output_columns] == [["number"], ["text"], []]
    text = ichnos.dbml(graph)
    assert (
        "Table report.r [kind: 'report'] {\n  N number\n  LABEL text\n  ID unknown\n}"
        in text
    )


def test_a_report_with_no_known_output_column_takes_a_placeholder():
    assert "Table report.r [kind: 'report'] {\n  \"*\" unknown\n}" in ichnos.dbml(
        ichnos.infer({"r": "SELECT * FROM u"})
    )


def test_dbml_raises_on_an_owner_named_report():
    graph = ichnos.infer({"q": 'SELECT t.x FROM "report".t t'})
    with pytest.raises(
        ichnos.IchnosError, match=r'the owner "report" of T is the schema'
    ):
        ichnos.dbml(graph)
