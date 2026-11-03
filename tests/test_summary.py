from typing import TYPE_CHECKING

import pytest

import ichnos

if TYPE_CHECKING:
    from syrupy.assertion import SnapshotAssertion


def test_the_synthetic_corpus_matches_its_golden_summary(
    synthetic: ichnos.Graph,
    snapshot_text: SnapshotAssertion,
):
    assert ichnos.summary(synthetic) == snapshot_text


def test_a_table_line_holds_its_kind_columns_counts_and_joins(synthetic: ichnos.Graph):
    lines = ichnos.summary(synthetic).splitlines()
    assert (
        "MART.ORDER_LINE_FACTS: base table, 9 columns, complete, read 3, write 1; joins INV.PRODUCT_CATEGORIES"
        in lines
    )
    assert (
        "MART.LAPSED_CUSTOMERS: base table, 1 column, complete, read 1; joins SALES.CUSTOMERS"
        in lines
    )
    assert (
        'report."055_key_customers": report, 3 columns; from MART.V_KEY_CUSTOMERS'
        in lines
    )


def test_the_owner_filter_keeps_that_owner_and_the_reports_that_read_it(
    synthetic: ichnos.Graph,
):
    lines = ichnos.summary(synthetic, owner="mart").splitlines()
    assert (
        lines[0]
        == "Summary of 60 queries, inferred with no database connection, owner mart."
    )
    assert {line.split(":")[0].split(".")[0] for line in lines[1:]} == {
        "MART",
        "report",
    }
    assert (
        'report."001_active_customers": report, 3 columns; from SALES.CUSTOMERS'
        not in lines
    )


def test_the_keyword_filter_matches_names_and_observed_values(synthetic: ichnos.Graph):
    lines = ichnos.summary(synthetic, keyword="paid").splitlines()
    assert (
        lines[0]
        == "Summary of 60 queries, inferred with no database connection, keyword 'paid'."
    )
    assert any(
        line.startswith("SALES.ORDERS:") and line.endswith("matches STATUS ('PAID')")
        for line in lines
    )
    assert any(
        line.startswith("SALES.PAYMENTS:") and line.endswith("matches PAID_AT")
        for line in lines
    )
    assert any(
        line.startswith('report."015_last_payment_per_order"')
        and line.endswith("matches LAST_PAID_AT")
        for line in lines
    )
    assert any(
        line.startswith('report."028_payments_quoted_identifiers"')
        and "matches Paid Amount, Paid At" in line
        for line in lines
    )


def test_the_keyword_filter_matches_a_table_name(synthetic: ichnos.Graph):
    lines = ichnos.summary(synthetic, keyword="segment").splitlines()
    assert lines[1].startswith("MART.CUSTOMER_SEGMENTS: base table, 4 columns")
    assert lines[1].endswith("matches name, SEGMENT")
    assert any(
        line.startswith('report."054_segment_summary"')
        and line.endswith("matches name, SEGMENT")
        for line in lines
    )


def test_the_budget_cuts_the_lowest_read_plus_write_first_down_to_the_first_line(
    synthetic: ichnos.Graph,
):
    text = ichnos.summary(synthetic)
    first, *rest = text.splitlines()
    previous = set(rest)
    cuts = 0
    while len(text.splitlines()) > 1:
        # One character under the last text forces the next cut (ADR 0015).
        budget = len(text) - 1
        text = ichnos.summary(synthetic, budget=budget)
        first, *kept = text.splitlines()
        assert len(text) <= budget or kept == []
        assert set(kept) < previous
        cut = int(first.split("; cut ")[1].split()[0])
        assert cut == cuts + len(previous - set(kept))
        cuts, previous = cut, set(kept)
    assert first.startswith(
        "Summary of 60 queries, inferred with no database connection; cut "
    )
    assert first.endswith("lines with read plus write of 20 or less.")


@pytest.mark.parametrize("budget", [1, 200, 2000])
def test_the_summary_fits_its_budget_until_only_the_first_line_remains(
    synthetic: ichnos.Graph, budget: int
):
    text = ichnos.summary(synthetic, budget=budget)
    assert len(text) <= budget or len(text.splitlines()) == 1


def test_a_quoted_owner_keeps_its_case():
    graph = ichnos.infer({"q": 'SELECT t.x FROM "lower".t t, "LOWER".u u'})
    lines = ichnos.summary(graph, owner='"lower"').splitlines()
    assert [line.split(":")[0] for line in lines[1:]] == ["lower.T", "report.q"]


def test_the_cut_order_adds_a_table_read_count_to_its_write_count():
    graph = ichnos.infer(
        {
            "u": "UPDATE s.t1 SET a = a + 1",
            "r1": "SELECT x.b FROM s.t2 x",
            "r2": "SELECT x.c FROM s.t2 x WHERE x.c = 1",
        }
    )
    text = ichnos.summary(graph)
    while len(text.splitlines()) > 2:
        text = ichnos.summary(graph, budget=len(text) - 1)
    assert text.splitlines()[1].startswith("S.T1:")
