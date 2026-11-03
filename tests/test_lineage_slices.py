from __future__ import annotations

import re
from typing import TYPE_CHECKING

import answer_key
import pytest

import ichnos

if TYPE_CHECKING:
    from collections.abc import Callable

    from conftest import DbmlChecker
    from syrupy.assertion import SnapshotAssertion

GRAPH = ichnos.read(answer_key.QUERIES)


def _upstream() -> ichnos.Slice:
    return GRAPH.upstream(GRAPH.report("054_segment_summary"))


def _downstream() -> ichnos.Slice:
    return GRAPH.downstream(GRAPH.table("sales.order_lines").column("quantity"))


def _deps(found: ichnos.Slice) -> set[str]:
    def name(
        end: ichnos.Table | ichnos.Column | ichnos.Report | ichnos.OutputColumn,
    ) -> str:
        match end:
            case ichnos.Column():
                return f"{end.table.name}.{end.name}"
            case ichnos.OutputColumn():
                return f"{end.report.name}.{end.name}"
            case _:
                return end.name

    return {
        f"{name(d.upstream)} -> {name(d.downstream)} {','.join(d.subtypes)}"
        for d in found.dependencies
    }


def test_the_upstream_slice_matches_its_golden_file(snapshot_dbml: SnapshotAssertion):
    assert ichnos.dbml(_upstream(), examples=True) == snapshot_dbml


def test_the_downstream_slice_matches_its_golden_file(snapshot_dbml: SnapshotAssertion):
    assert ichnos.dbml(_downstream(), examples=True) == snapshot_dbml


@pytest.mark.parametrize("walk", [_upstream, _downstream])
def test_the_budget_cuts_one_step_at_a_time_down_to_the_chain(
    dbml_checker: DbmlChecker, walk: Callable[[], ichnos.Slice]
):
    found = walk()
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


def test_a_count_star_ends_the_walk_at_the_table_it_reads():
    found = GRAPH.upstream(
        GRAPH.report("054_segment_summary").output_column("customer_count")
    )
    assert _deps(found) == {
        "CUSTOMER_SEGMENTS -> 054_segment_summary.CUSTOMER_COUNT AGGREGATION",
        "CUSTOMER_SEGMENTS.SEGMENT -> 054_segment_summary GROUP_BY",
        "CUSTOMER_SEGMENTS.NET_AMOUNT_12M -> 054_segment_summary SORT",
    }


def test_indirect_dependencies_stay_on_the_first_hop_unless_all_are_asked_for():
    first = _deps(GRAPH.upstream(GRAPH.table("mart.customer_segments")))
    every = _deps(GRAPH.upstream(GRAPH.table("mart.customer_segments"), indirect="all"))
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
    assert _deps(found) == {"B.Y -> C.Z IDENTITY", "A.X -> B.Y IDENTITY"}


def test_a_cycle_ends_the_walk():
    graph = ichnos.infer(
        {
            "a": "INSERT INTO s.a (x) SELECT b.y FROM s.b b",
            "b": "INSERT INTO s.b (y) SELECT a.x FROM s.a a",
        }
    )
    assert _deps(graph.upstream(graph.table("s.a").column("x"))) == {
        "B.Y -> A.X IDENTITY",
        "A.X -> B.Y IDENTITY",
    }


def test_a_downstream_slice_of_a_table_writes_rollups_only():
    found = GRAPH.downstream(GRAPH.table("mart.customer_segments"))
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


def test_a_lineage_slice_writes_a_self_dependency_as_a_property():
    text = ichnos.dbml(
        GRAPH.upstream(GRAPH.table("mart.customer_segments").column("segment"))
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
