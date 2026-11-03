import pytest

import ichnos


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("SELECT t.a FROM t WHERE t.b = :1", "Required keyword: 'expression' missing"),
        (
            "CREATE MATERIALIZED VIEW m.v REFRESH FAST ON COMMIT AS SELECT t.a FROM t",
            "sqlglot reads the statement as an opaque command",
        ),
        ("ALTER TABLE t ADD x NUMBER", "not a SELECT, DML or a creating query: ALTER"),
        ("SET DEFINE OFF", "sqlglot reads the statement as an opaque command"),
        ("SELECT x.a FROM t", "unknown table or alias X"),
    ],
)
def test_a_query_ichnos_cannot_read_whole_is_listed(text: str, error: str):
    graph = ichnos.infer({"f": f"SELECT t.ok FROM t;\n{text}"})  # noqa: S608 # fixed test text
    [query] = graph.unparsed
    assert (query.name, query.file, query.position, query.text) == ("f#2", "f", 2, text)
    assert query.error.startswith(error)
    assert [q.name for q in graph.queries] == ["f#1"]
    assert [c.name for t in graph.tables for c in t.columns] == ["OK"]


def test_a_later_step_that_raises_makes_the_query_unparsed():
    graph = ichnos.infer({"f": "SELECT v.a FROM (VALUES (1)) v (a)"})
    assert graph.unparsed[0].error == "unsupported query: VALUES"


def test_a_statement_that_writes_a_query_is_unparsed():
    graph = ichnos.infer({"f": "UPDATE (SELECT t.a FROM t) v SET v.a = 1"})
    assert graph.unparsed[0].error == "the statement writes a query, not a table"


def test_a_cte_names_an_expression_position_for_no_reference():
    graph = ichnos.infer({"f": "WITH c AS (SELECT 1, u.a FROM u) SELECT a FROM c"})
    assert graph.unparsed == ()
