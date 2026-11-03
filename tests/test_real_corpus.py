"""Run every walk and command over the user's real corpus, which stays on their machine (ADR 0015).

The test runs only when `ICHNOS_CORPUS` names a folder, and it writes nothing to the repo.
"""

import itertools
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import ichnos
from ichnos._cli import app

if TYPE_CHECKING:
    from conftest import DbmlChecker

CORPUS = os.environ.get("ICHNOS_CORPUS", "")
pytestmark = pytest.mark.skipif(
    not Path(CORPUS).is_dir() if CORPUS else True,
    reason="set ICHNOS_CORPUS to a folder of queries",
)
BUDGET = 8000


def _check(dbml_checker: DbmlChecker, text: str) -> None:
    dbml_checker.check(text)
    core = re.search(r"The core is ([\d,]+) characters", text)
    assert len(text) <= BUDGET or (
        core is not None and int(core[1].replace(",", "")) == len(text)
    )


def test_real_corpus(
    dbml_checker: DbmlChecker, capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    graph = ichnos.read(CORPUS)
    dbml_checker.check(ichnos.dbml(graph))
    ichnos.summary(graph)
    for table in graph.tables:
        _check(dbml_checker, ichnos.dbml(graph.neighborhood([table])))
    for report in graph.reports:
        _check(dbml_checker, ichnos.dbml(graph.upstream(report)))
    for table in (t for t in graph.tables if t.read):
        _check(dbml_checker, ichnos.dbml(graph.downstream(table)))
    pairs = {
        tuple(sorted((a, b), key=lambda t: (t.owner or "", t.name)))
        for report in graph.reports
        for a, b in itertools.combinations(
            [r.upstream for r in graph.rollups if r.downstream is report], 2
        )
    }
    for pair in pairs:
        _check(dbml_checker, ichnos.dbml(graph.join_path(pair)))
    _commands(graph, capsys, tmp_path)


def _commands(
    graph: ichnos.Graph, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Run each command once on the first start, and check its exit code and its stderr lines."""
    table = graph.tables[0]
    # An unquoted name folds to uppercase, so only an uppercase part stays bare.
    quoted = ".".join(
        p if re.fullmatch(r"[A-Z][A-Z0-9_$#]*", p) else f'"{p}"'
        for p in (table.owner, table.name)
        if p is not None
    )
    starts = [
        ["neighborhood", quoted],
        ["join-path", quoted, quoted],
        ["downstream", "--table", quoted],
    ]
    if graph.reports:
        starts.append(["upstream", "--report", graph.reports[0].name])
    commands = [["dbml"], ["summary"], ["unparsed"], *starts]
    unparsed = f"ichnos: {len(graph.unparsed)} of {len(graph.queries) + len(graph.unparsed)} queries unparsed"
    for command in commands:
        with pytest.raises(SystemExit) as exit_:
            app([command[0], CORPUS, *command[1:], "-o", str(tmp_path / "out")])
        _, err = capsys.readouterr()
        assert exit_.value.code in {0, None}
        for line in err.splitlines():
            assert line.startswith((unparsed, "ichnos: the core of this slice is")), (
                line
            )
