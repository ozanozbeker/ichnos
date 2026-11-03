from typing import TYPE_CHECKING

import answer_key

import ichnos

if TYPE_CHECKING:
    from collections.abc import Callable

    from conftest import Parsed
    from syrupy.assertion import SnapshotAssertion


def test_the_synthetic_corpus_matches_its_golden_file(snapshot_dbml: SnapshotAssertion):
    assert ichnos.dbml(ichnos.read(answer_key.QUERIES)) == snapshot_dbml


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
    [table] = parsed["tables"]
    assert (table["schema"], table["name"]) == ("sales", "pay ments")
    assert [c["name"] for c in table["columns"]] == ["1st", "Paid At"]
