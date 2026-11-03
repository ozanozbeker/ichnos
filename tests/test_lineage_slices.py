from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from conftest import dependency_lines

import ichnos

if TYPE_CHECKING:
    from collections.abc import Callable

    from conftest import DbmlChecker
    from syrupy.assertion import SnapshotAssertion


def _upstream(graph: ichnos.Graph) -> ichnos.Slice:
    return graph.upstream(graph.report("054_segment_summary"))


def _downstream(graph: ichnos.Graph) -> ichnos.Slice:
    return graph.downstream(graph.table("sales.order_lines").column("quantity"))


def test_the_upstream_slice_matches_its_golden_file(
    synthetic: ichnos.Graph, snapshot_dbml: SnapshotAssertion
):
    # The budget runs through every cut step (ADR 0015).
    text = ichnos.dbml(_upstream(synthetic), budget=2850, examples=True)
    assert text == snapshot_dbml


def test_the_downstream_slice_matches_its_golden_file(
    synthetic: ichnos.Graph, snapshot_dbml: SnapshotAssertion
):
    # The budget runs through every cut step (ADR 0015).
    text = ichnos.dbml(_downstream(synthetic), budget=5050, examples=True)
    assert text == snapshot_dbml


@pytest.mark.parametrize("walk", [_upstream, _downstream])
def test_the_budget_cuts_one_step_at_a_time_down_to_the_chain(
    synthetic: ichnos.Graph,
    dbml_checker: DbmlChecker,
    walk: Callable[[ichnos.Graph], ichnos.Slice],
):
    found = walk(synthetic)
    text = ichnos.dbml(found, examples=True)
    previous: list[str] = []
    while "The core is" not in text:
        budget = len(text) - 1
        text = ichnos.dbml(found, budget=budget, examples=True)
        dbml_checker.check(text)
        assert len(text) <= budget or f"over the {budget:,}-character budget" in text
        match = re.search(r"Cut to fit [\d,]+ characters: (.*)\.\n", text)
        cuts = match[1].split(", ") if match else []
        assert cuts[: len(previous)] == previous
        assert len(cuts) > len(previous) or "The core is" in text
        previous = cuts
    assert "the first hop's indirect dependencies" in previous[-1]


def test_a_count_star_ends_the_walk_at_the_table_it_reads(synthetic: ichnos.Graph):
    found = synthetic.upstream(
        synthetic.report("054_segment_summary").output_column("customer_count")
    )
    assert dependency_lines(found.dependencies) == {
        "CUSTOMER_SEGMENTS -> report 054_segment_summary.CUSTOMER_COUNT AGGREGATION",
        "CUSTOMER_SEGMENTS.SEGMENT -> report 054_segment_summary GROUP_BY",
        "CUSTOMER_SEGMENTS.NET_AMOUNT_12M -> report 054_segment_summary SORT",
    }


def test_indirect_dependencies_stay_on_the_first_hop_unless_all_are_asked_for(
    synthetic: ichnos.Graph,
):
    first = dependency_lines(
        synthetic.upstream(synthetic.table("mart.customer_segments")).dependencies
    )
    every = dependency_lines(
        synthetic.upstream(
            synthetic.table("mart.customer_segments"), indirect="all"
        ).dependencies
    )
    assert "CUSTOMER_DAILY_SALES.SALES_DATE -> CUSTOMER_SEGMENTS FILTER" in first
    deeper = "ORDER_LINE_FACTS.SALES_DATE -> CUSTOMER_DAILY_SALES JOIN,FILTER,GROUP_BY"
    assert deeper not in first
    assert deeper in every
    assert (
        "ORDER_LINE_FACTS.NET_AMOUNT -> CUSTOMER_DAILY_SALES.NET_AMOUNT AGGREGATION"
        in first
    )


def test_a_dependency_past_the_first_hop_keeps_only_its_direct_subtypes():
    graph = ichnos.infer(
        {
            "a": "CREATE TABLE m.b AS SELECT s.x AS y FROM s.a s GROUP BY s.x",
            "b": "CREATE TABLE m.c AS SELECT b.y AS z FROM m.b b",
        }
    )
    found = graph.upstream(graph.table("m.c"))
    assert dependency_lines(found.dependencies) == {
        "B.Y -> C.Z IDENTITY",
        "A.X -> B.Y IDENTITY",
    }


def test_a_cycle_ends_the_walk():
    graph = ichnos.infer(
        {
            "a": "INSERT INTO s.a (x) SELECT b.y FROM s.b b",
            "b": "INSERT INTO s.b (y) SELECT a.x FROM s.a a",
        }
    )
    assert dependency_lines(
        graph.upstream(graph.table("s.a").column("x")).dependencies
    ) == {
        "B.Y -> A.X IDENTITY",
        "A.X -> B.Y IDENTITY",
    }


def test_a_downstream_slice_of_a_table_writes_rollups_only(synthetic: ichnos.Graph):
    found = synthetic.downstream(synthetic.table("mart.customer_segments"))
    assert found.dependencies == ()
    assert {(r.upstream.name, r.downstream.name) for r in found.rollups} == {
        ("CUSTOMER_SEGMENTS", "CUSTOMER_SEGMENTS"),
        ("CUSTOMER_SEGMENTS", "V_KEY_CUSTOMERS"),
        ("CUSTOMER_SEGMENTS", "054_segment_summary"),
        ("V_KEY_CUSTOMERS", "055_key_customers"),
        ("V_KEY_CUSTOMERS", "056_key_customers_dashboard"),
    }
    text = ichnos.dbml(found)
    assert (
        'Dep: MART.V_KEY_CUSTOMERS -> report."055_key_customers" [queries: 1]' in text
    )
    assert (
        "Downstream of MART.CUSTOMER_SEGMENTS, with indirect dependencies on the first hop"
        in text
    )


def test_a_lineage_slice_writes_a_self_dependency_as_a_property(
    synthetic: ichnos.Graph,
):
    text = ichnos.dbml(
        synthetic.upstream(synthetic.table("mart.customer_segments").column("segment"))
    )
    assert (
        "Metadata Column MART.CUSTOMER_SEGMENTS.SEGMENT {\n  self_dependency: 'TRANSFORMATION 1'\n}"
        in text
    )


def test_dropping_the_first_hop_keeps_the_direct_subtypes_of_a_mixed_dependency():
    graph = ichnos.infer(
        {
            "m": "MERGE INTO s.t t USING s.u u ON (t.k = u.k) WHEN NOT MATCHED THEN INSERT VALUES (u.k, u.v)",
        }
    )
    text = ichnos.dbml(graph.upstream(graph.table("s.t")), budget=1)
    assert "the first hop's indirect dependencies" in text
    assert "Dep: S.U.K -> S.T [identity: 1]" in text
    assert "S.T.K" not in text


def test_a_downstream_slice_of_a_table_ends_with_the_queries_of_its_rollups(
    synthetic: ichnos.Graph,
):
    found = synthetic.downstream(synthetic.table("mart.customer_segments"))
    names = {q.name for r in found.rollups for q in r.queries}
    text = ichnos.dbml(found, budget=100_000, examples=True)
    assert names
    assert set(re.findall(r"(?m)^// (\S+)$", text)) == names
