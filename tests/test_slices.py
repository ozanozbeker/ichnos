from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

import ichnos

if TYPE_CHECKING:
    from collections.abc import Callable

    from conftest import DbmlChecker
    from syrupy.assertion import SnapshotAssertion


def _neighborhood(graph: ichnos.Graph) -> ichnos.Slice:
    return graph.neighborhood([graph.table("sales.orders")])


def _join_path(graph: ichnos.Graph) -> ichnos.Slice:
    return graph.join_path([graph.table("ref.countries"), graph.table("inv.products")])


def test_the_neighborhood_slice_matches_its_golden_file(
    synthetic: ichnos.Graph,
    snapshot_dbml: SnapshotAssertion,
):
    # The budget runs through every cut step (ADR 0015).
    text = ichnos.dbml(_neighborhood(synthetic), budget=2750, examples=True)
    assert text == snapshot_dbml


def test_the_join_path_slice_matches_its_golden_file(
    synthetic: ichnos.Graph, snapshot_dbml: SnapshotAssertion
):
    # The budget runs through every cut step (ADR 0015).
    text = ichnos.dbml(_join_path(synthetic), budget=3300, examples=True)
    assert text == snapshot_dbml


def _cuts(text: str) -> list[str]:
    found = re.search(r"Cut to fit [\d,]+ characters: (.*)\.\n", text)
    return found[1].split(", ") if found else []


@pytest.mark.parametrize("walk", [_neighborhood, _join_path])
def test_the_budget_cuts_one_step_at_a_time_down_to_the_core(
    synthetic: ichnos.Graph,
    dbml_checker: DbmlChecker,
    walk: Callable[[ichnos.Graph], ichnos.Slice],
):
    found = walk(synthetic)
    text = ichnos.dbml(found, examples=True)
    previous: list[str] = []
    while "The core is" not in text:
        # One character under the last text forces the next cut (ADR 0015).
        budget = len(text) - 1
        text = ichnos.dbml(found, budget=budget, examples=True)
        dbml_checker.check(text)
        assert len(text) <= budget or f"over the {budget:,}-character budget" in text
        cuts = _cuts(text)
        assert cuts[: len(previous)] == previous
        assert len(cuts) > len(previous) or "The core is" in text
        previous = cuts
    assert re.search(rf"The core is {len(text):,} characters", text)


def test_a_neighborhood_keeps_every_ref_between_its_tables_and_names_the_outside(
    synthetic: ichnos.Graph,
):
    found = synthetic.neighborhood([synthetic.table("inv.warehouses")], depth=2)
    assert {
        t.name: d for t, d in found.distances.items() if isinstance(t, ichnos.Table)
    } == {
        "WAREHOUSES": 0,
        "SHIPMENTS": 1,
        "STOCK_LEVELS": 1,
        "COUNTRIES": 1,
        "ORDER_LINES": 2,
        "CUSTOMER_ADDRESSES": 2,
        "DEPARTMENTS": 2,
    }
    text = ichnos.dbml(found)
    assert "Neighborhood of INV.WAREHOUSES at depth 2: 7 of 32 tables." in text
    assert "Outside the slice, these tables join it: EMP, HR.EMPLOYEES," in text


def test_a_join_path_names_the_tables_no_relationship_connects(synthetic: ichnos.Graph):
    found = synthetic.join_path(
        [synthetic.table("sales.orders"), synthetic.table("ref.currencies")]
    )
    assert found.unconnected == (
        synthetic.table("sales.orders"),
        synthetic.table("ref.currencies"),
    )
    assert "No relationship connects SALES.ORDERS, REF.CURRENCIES." in ichnos.dbml(
        found
    )


def test_full_detail_keeps_every_count(synthetic: ichnos.Graph):
    text = ichnos.dbml(_join_path(synthetic), detail="full")
    assert "select:" in text
    assert "select:" not in ichnos.dbml(_join_path(synthetic))


@pytest.mark.parametrize(
    ("name", "found"),
    [
        ("sales.orders", ("SALES", "ORDERS")),
        ('"SALES"."ORDERS"', ("SALES", "ORDERS")),
        ("sales.orders@archive", ("SALES", "ORDERS@ARCHIVE")),
        ("customers", (None, "CUSTOMERS")),
    ],
)
def test_a_table_lookup_parses_the_name_as_oracle_does(
    synthetic: ichnos.Graph, name: str, found: tuple[str | None, str]
):
    table = synthetic.table(name)
    assert (table.owner, table.name) == found


@pytest.mark.parametrize("name", ["sales.order", "a.b.c", "mart.x"])
def test_a_missing_table_raises_key_error(synthetic: ichnos.Graph, name: str):
    with pytest.raises(KeyError):
        synthetic.table(name)


def test_a_report_and_its_output_columns_look_up_by_name(synthetic: ichnos.Graph):
    report = synthetic.report("038_daily_reports#2")
    assert report.output_column("new_customers").name == "NEW_CUSTOMERS"
    assert (
        synthetic.report("028_payments_quoted_identifiers")
        .output_column('"Paid At"')
        .name
        == "Paid At"
    )
    with pytest.raises(KeyError):
        synthetic.report("038_DAILY_REPORTS#2")
    with pytest.raises(KeyError):
        report.output_column("missing")


def test_a_slice_writes_the_legend_lines_it_needs():
    graph = ichnos.infer(
        {
            "a": "SELECT 1 FROM s.t t JOIN s.u u ON u.k = t.k WHERE t.c = 'x'",
            "b": "SELECT 1 FROM s.t t WHERE t.c = 5 AND t.n IS NULL",
        }
    )
    text = ichnos.dbml(graph.neighborhood([graph.table("s.t")]))
    assert (
        "A column with evidence for two types writes both, such as `text|number`, an ambiguity."
        in text
    )
    assert '  C "text|number" [text: 1, number: 1' in text
    assert "`>?` means" not in text
