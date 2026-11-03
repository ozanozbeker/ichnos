from typing import TYPE_CHECKING

import ichnos

if TYPE_CHECKING:
    from collections.abc import Callable

    from conftest import Parsed
    from syrupy.assertion import SnapshotAssertion


def test_the_synthetic_corpus_matches_its_golden_file(
    synthetic: ichnos.Graph, snapshot_dbml: SnapshotAssertion
):
    assert ichnos.dbml(synthetic) == snapshot_dbml


def test_a_table_with_no_known_column_takes_a_placeholder(
    assert_dbml_valid: Callable[[str], Parsed],
):
    text = ichnos.dbml(ichnos.infer({"q": "SELECT COUNT(*) FROM sales.orders"}))
    assert '  "*" unknown' in text
    assert_dbml_valid(text)


def test_a_name_that_dbml_cannot_write_bare_is_quoted(
    assert_dbml_valid: Callable[[str], Parsed],
):
    text = ichnos.dbml(
        ichnos.infer({"q": 'SELECT p."Paid At", p."1st" FROM "sales"."pay ments" p'})
    )
    parsed = assert_dbml_valid(text)
    [table] = [t for t in parsed["tables"] if t["schema"] != "report"]
    assert (table["schema"], table["name"]) == ("sales", "pay ments")
    assert [c["name"] for c in table["columns"]] == ["1st", "Paid At"]
