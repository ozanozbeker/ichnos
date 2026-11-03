from typing import TYPE_CHECKING

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import ichnos

if TYPE_CHECKING:
    from conftest import DbmlChecker


def _column(graph: ichnos.Graph, name: str) -> ichnos.Column:
    return next(c for t in graph.tables for c in t.columns if c.name == name)


def _types(sql: str) -> dict[str, list[str]]:
    graph = ichnos.infer({"q": sql})
    return {c.name: list(c.types) for t in graph.tables for c in t.columns if c.types}


@pytest.mark.parametrize(
    ("sql", "types"),
    [
        (
            "SELECT 1 FROM t WHERE t.a = 'x' AND t.b > 10 AND t.c >= DATE '2024-01-01'",
            {"A": ["text"], "B": ["number"], "C": ["datetime"]},
        ),
        (
            "SELECT 1 FROM t WHERE t.a >= ADD_MONTHS(SYSDATE, -1) AND t.b < SYSTIMESTAMP - INTERVAL '1' DAY",
            {"A": ["datetime"], "B": ["datetime"]},
        ),
        (
            "SELECT 1 FROM t WHERE t.a = s.q.NEXTVAL AND t.b = INTERVAL '1' DAY AND t.c BETWEEN 1 AND 2",
            {"A": ["number"], "B": ["interval"], "C": ["number"]},
        ),
        (
            "SELECT t.a * t.b, -t.c, SUM(t.d), MOD(t.e, 2), ABS(t.f) FROM t",
            {k: ["number"] for k in "ABCDEF"},
        ),
        (
            "SELECT UPPER(t.a), SUBSTR(t.b, 1), INSTR(t.c, 'x'), LPAD(t.d, 2), LENGTH(t.e) FROM t",
            {k: ["text"] for k in "ABCDE"},
        ),
        (
            "SELECT ADD_MONTHS(t.a, 1), MONTHS_BETWEEN(t.b, t.c), LAST_DAY(t.d), EXTRACT(YEAR FROM t.e) FROM t",
            {k: ["datetime"] for k in "ABCDE"},
        ),
        (
            "SELECT TRUNC(t.a, 'MM'), TRUNC(t.b, 2), ROUND(t.c, 'YYYY'), ROUND(t.d, 1), TRUNC(t.e) FROM t",
            {"A": ["datetime"], "B": ["number"], "C": ["datetime"], "D": ["number"]},
        ),
        (
            "SELECT NVL(t.a, -1), COALESCE(t.b, 'x'), GREATEST(t.c, SYSDATE), NULLIF(t.d, 0), NVL2(t.e, t.f, 'y') FROM t",
            {
                "A": ["number"],
                "B": ["text"],
                "C": ["datetime"],
                "D": ["number"],
                "F": ["text"],
            },
        ),
        (
            "SELECT CASE WHEN t.a > 0 THEN t.b ELSE 'x' END, DECODE(t.c, 1, t.d, 2) FROM t",
            {"A": ["number"], "B": ["text"], "C": ["number"], "D": ["number"]},
        ),
        ("SELECT t.a FROM t UNION ALL SELECT 'x' FROM u", {"A": ["text"]}),
        (
            "SELECT t.a + 1, t.b || 'x', TO_CHAR(t.c), MAX(t.d), COUNT(t.e) FROM t WHERE t.f = u.g",
            {},
        ),
        (
            "SELECT 1 FROM t WHERE t.a = CAST(x AS VARCHAR2(10)) AND t.b = CAST(y AS NUMBER) AND t.c = CAST(z AS DATE) AND t.d = CAST(w AS BLOB)",
            {"A": ["text"], "B": ["number"], "C": ["datetime"]},
        ),
        (
            "SELECT 1 FROM t WHERE t.a = TRUNC(SYSDATE) - 7 AND t.b = SYSDATE - SYSDATE AND t.c = 1 + 2 AND t.d = SYSDATE + :x AND t.e = 'x' + 1",
            {"A": ["datetime"], "B": ["number"], "C": ["number"]},
        ),
        (
            "SELECT 1 FROM t WHERE t.a = MAX(SYSDATE) AND t.b = ROUND(SYSDATE) AND t.c = CASE WHEN 1 = 1 THEN 'x' END",
            {"A": ["datetime"], "B": ["datetime"], "C": ["text"]},
        ),
    ],
)
def test_a_fixed_type_expression_gives_a_bare_column_its_type(
    sql: str, types: dict[str, list[str]]
):
    assert _types(sql) == types


def test_assigned_values_give_types_observed_values_and_nullable():
    graph = ichnos.infer(
        {
            "i": "INSERT INTO t (a, b, c, d) VALUES ('x', 5, NULL, SYSDATE)",
            "u": "UPDATE t SET t.e = 'y', (f, g) = (SELECT 1, 2 FROM dual)",
            "m": "MERGE INTO t USING u ON (t.a = u.a) WHEN MATCHED THEN UPDATE SET t.h = NULL WHEN NOT MATCHED THEN INSERT (a) VALUES ('z')",
            "s": "INSERT INTO t (k) SELECT 'w' FROM dual",
        }
    )
    columns = {c.name: c for t in graph.tables if t.name == "T" for c in t.columns}
    assert list(columns["A"].observed) == ["'x'", "'z'"]
    assert list(columns["B"].observed) == ["5"]
    assert [q.name for q in columns["C"].nullable] == ["i"]
    assert list(columns["D"].types) == ["datetime"]
    assert list(columns["E"].observed) == ["'y'"]
    assert columns["F"].types == {}
    assert [q.name for q in columns["H"].nullable] == ["m"]
    assert list(columns["K"].observed) == ["'w'"]


def test_equality_gives_observed_values_and_a_range_gives_none():
    graph = ichnos.infer(
        {
            "q": """SELECT DECODE(t.a, 'N', 1, 'P', 2, 0), CASE t.b WHEN 'X' THEN 1 END FROM t
                 WHERE t.c IN ('A', 'B') AND t.d NOT IN (1, -2) AND t.e <> 'C' AND t.f > 10 AND t.g LIKE 'S%'
                   AND t.h = DATE '2024-01-01'""",
        }
    )
    observed = {
        c.name: list(c.observed) for t in graph.tables for c in t.columns if c.observed
    }
    assert observed == {
        "A": ["'N'", "'P'"],
        "B": ["'X'"],
        "C": ["'A'", "'B'"],
        "D": ["-2", "1"],
        "E": ["'C'"],
    }


def test_nullable_comes_from_null_tests_off_the_null_supplying_side():
    graph = ichnos.infer(
        {
            "q": """SELECT NVL(a.x, 0), NVL2(a.y, 1, 2), COALESCE(b.z, 0) FROM s.a a LEFT JOIN s.b b ON b.i = a.i
                 WHERE a.w IS NULL AND b.v IS NOT NULL""",
            "p": "SELECT 1 FROM s.a a, s.b b WHERE a.i = b.i (+) AND b.u IS NULL",
            "r": "SELECT 1 FROM s.a a RIGHT JOIN s.b b ON b.i = a.i WHERE a.t IS NULL AND b.r IS NULL",
        }
    )
    nullable = sorted(
        f"{t.name}.{c.name}" for t in graph.tables for c in t.columns if c.nullable
    )
    assert nullable == ["A.W", "A.X", "A.Y", "B.R"]
    assert "  W unknown [null, where: 1, nullable: 1]" in ichnos.dbml(graph)


def test_two_types_give_an_ambiguity():
    graph = ichnos.infer(
        {"a": "SELECT 1 FROM t WHERE t.c = 'x'", "b": "SELECT 1 FROM t WHERE t.c = 5"}
    )
    [ambiguity] = graph.ambiguities
    assert (ambiguity.kind, ambiguity.query, ambiguity.subject) == ("type", None, "T.C")
    assert list(ambiguity.candidates) == ["text", "number"]
    assert _column(graph, "C").ambiguities == (ambiguity,)
    assert (
        "  C \"text|number\" [where: 2, text: 1, number: 1, observed: 'x, 5']"
        in ichnos.dbml(graph)
    )


def test_a_declared_type_settles_a_reference_that_contradicts_it():
    graph = ichnos.infer(
        {
            "c": "CREATE TABLE m.t AS SELECT COUNT(*) AS n, s.x FROM s GROUP BY s.x",
            "q": "SELECT 1 FROM m.t t WHERE t.n = 'many'",
        }
    )
    assert graph.ambiguities == ()
    [table] = [t for t in graph.tables if t.name == "T"]
    assert [d.types for d in table.declarations] == [{"N": "number"}]
    assert (
        "  N number [declared: 1, where: 1, text: 1, number: 1, observed: 'many']"
        in ichnos.dbml(graph)
    )


def test_more_than_twenty_observed_values_write_their_count():
    values = ", ".join(str(n) for n in range(21))
    sql = f"SELECT 1 FROM t WHERE t.id IN ({values})"  # noqa: S608 # generated test text
    text = ichnos.dbml(ichnos.infer({"q": sql}))
    assert "observed_count: 21" in text
    assert "observed:" not in text


NAMES = st.text(
    st.characters(exclude_characters='"', exclude_categories=("Cs", "Cc")),
    min_size=1,
    max_size=12,
)
VALUES = st.text(
    st.characters(exclude_categories=("Cs",), exclude_characters="\x00\r"),
    min_size=1,
    max_size=12,
)


@given(name=NAMES, value=VALUES)
@settings(max_examples=60, deadline=None)
def test_dbml_core_reads_back_every_quoted_name_and_observed_value(
    dbml_checker: DbmlChecker, name: str, value: str
):
    literal = value.replace("'", "''")
    sql = f'SELECT 1 FROM "o"."{name}" t WHERE t."{name}" = \'{literal}\''  # noqa: S608 # generated test text
    graph = ichnos.infer({"q": sql})
    tables = dbml_checker.check(ichnos.dbml(graph))["tables"]
    [table] = [t for t in tables if t["schema"] != "report"]
    [column] = table["columns"]
    assert (table["name"], column["name"]) == (name, name)
    plain = "," not in value and value == value.strip(" ")
    assert column["properties"]["observed"] == (value if plain else f"'{literal}'")


def test_an_unqualified_column_of_an_outer_joined_table_shows_no_nullable():
    graph = ichnos.infer(
        {
            "q": "SELECT 1 FROM (SELECT 1 AS k FROM dual) v LEFT JOIN s.b b ON b.i = v.k WHERE z IS NULL"
        }
    )
    assert _column(graph, "Z").nullable == ()


def test_a_column_list_over_a_star_declares_no_type():
    graph = ichnos.infer({"v": "CREATE VIEW m.v (x, y) AS SELECT * FROM s"})
    [declaration] = graph.tables[-1].declarations
    assert (declaration.columns, declaration.types) == (("X", "Y"), {})
