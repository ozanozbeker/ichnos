import os
import runpy
import subprocess
import sys
from typing import TYPE_CHECKING

import answer_key
import pytest

import ichnos
from ichnos._cli import app

if TYPE_CHECKING:
    from pathlib import Path


def _run(capsys: pytest.CaptureFixture[str], *tokens: str) -> tuple[int, str, str]:
    with pytest.raises(SystemExit) as exit_:
        app(list(tokens))
    out, err = capsys.readouterr()
    return int(exit_.value.code or 0), out, err


def test_dbml_writes_the_full_file_to_stdout(
    synthetic: ichnos.Graph, capsys: pytest.CaptureFixture[str]
):
    code, out, err = _run(capsys, "dbml", str(answer_key.QUERIES))
    assert (code, err) == (0, "")
    assert out == ichnos.dbml(synthetic)


def test_dbml_writes_the_output_file(
    synthetic: ichnos.Graph, capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    output = tmp_path / "schema.dbml"
    code, out, _ = _run(capsys, "dbml", str(answer_key.QUERIES), "-o", str(output))
    assert (code, out) == (0, "")
    assert output.read_bytes() == ichnos.dbml(synthetic).encode()


@pytest.mark.parametrize(
    ("tokens", "line"),
    [
        (["dbml", "missing"], "ichnos: No such file or directory: missing\n"),
        (["dbml", "."], "ichnos: no .sql file in .\n"),
    ],
)
def test_a_user_error_exits_1_with_one_line(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    tokens: list[str],
    line: str,
):
    monkeypatch.chdir(tmp_path)
    assert _run(capsys, *tokens) == (1, "", line)


def test_a_usage_error_exits_2(capsys: pytest.CaptureFixture[str]):
    code, _, err = _run(capsys, "dbml", str(answer_key.QUERIES), "--unknown")
    assert code == 2
    assert err


def test_join_path_takes_two_or_more_tables(capsys: pytest.CaptureFixture[str]):
    code, _, err = _run(capsys, "join-path", str(answer_key.QUERIES), "SALES.ORDERS")
    assert code == 2
    assert err


def test_a_bug_exits_1_with_its_traceback():
    # A KeyError inside a walk is a bug, because the CLI catches KeyError only around its lookups (ADR 0014).
    script = f"""
import sys
from ichnos import _cli

def walk(*args, **kwargs):
    raise KeyError("inside a walk")

_cli.Graph.neighborhood = walk
sys.argv = ["ichnos", "neighborhood", {str(answer_key.QUERIES)!r}, "SALES.ORDERS"]
_cli.main()
"""
    command = [sys.executable, "-c", script]
    result = subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603 # runs ichnos itself
    assert result.returncode == 1
    assert result.stderr.startswith("Traceback (most recent call last):\n")
    assert result.stderr.endswith("KeyError: 'inside a walk'\n")


def test_main_runs_the_app(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(sys, "argv", ["ichnos", "dbml", str(answer_key.QUERIES)])
    with pytest.raises(SystemExit):
        runpy.run_module("ichnos", run_name="__main__")
    assert capsys.readouterr().out.startswith("Project ichnos {")


def test_suffix_and_encoding_mirror_the_api(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    (tmp_path / "q.txt").write_bytes('SELECT t."é" FROM t'.encode("cp1252"))
    tokens = [
        "dbml",
        str(tmp_path),
        "--suffix",
        ".sql",
        "--suffix",
        ".txt",
        "--encoding",
        "latin-1",
    ]
    code, out, _ = _run(capsys, *tokens)
    assert code == 0
    assert out == ichnos.dbml(ichnos.read(tmp_path, (".sql", ".txt"), "latin-1"))


def test_python_m_ichnos_writes_the_same_utf_8_bytes_as_the_output_file(tmp_path: Path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "q.sql").write_text(
        'SELECT t."café" FROM t WHERE t."café" = \'é\'\n', encoding="utf-8"
    )
    output = tmp_path / "schema.dbml"
    command = [sys.executable, "-m", "ichnos", "dbml", str(corpus)]
    stdout = subprocess.run(command, capture_output=True, check=True).stdout  # noqa: S603 # runs ichnos itself
    subprocess.run([*command, "-o", str(output)], check=True)  # noqa: S603 # runs ichnos itself
    assert stdout == output.read_bytes()
    assert (
        "\"café\" text [select: 1, where: 1, text: 1, observed: 'é']".encode() in stdout
    )
    assert not stdout.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in stdout


def test_unparsed_lists_each_query_with_the_first_line_of_its_error(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    (tmp_path / "a.sql").write_text(
        "SELECT t.x FROM t;\nALTER TABLE t ADD y NUMBER", encoding="utf-8"
    )
    (tmp_path / "b.sql").write_text(
        "SELECT t.y FROM t WHERE t.z = :1", encoding="utf-8"
    )
    code, out, err = _run(capsys, "unparsed", str(tmp_path))
    assert (code, err) == (0, "")
    first, second = out.splitlines()
    assert first == "a#2: not a SELECT, DML or a creating query: ALTER"
    # The rest of sqlglot's message names its own class path, which can move between releases.
    assert second.startswith("b: Required keyword: 'expression' missing")
    # The line names the path as given, with its trailing separator.
    code, out, err = _run(capsys, "dbml", f"{tmp_path}{os.sep}")
    assert code == 0
    assert out.startswith("Project ichnos {")
    assert (
        err
        == f"ichnos: 2 of 3 queries unparsed; run ichnos unparsed {tmp_path}{os.sep} to list them\n"
    )


def test_summary_mirrors_the_api(
    synthetic: ichnos.Graph, capsys: pytest.CaptureFixture[str]
):
    tokens = [
        "summary",
        str(answer_key.QUERIES),
        "--owner",
        "mart",
        "--keyword",
        "sales",
        "--budget",
        "300",
    ]
    code, out, err = _run(capsys, *tokens)
    assert (code, err) == (0, "")
    assert out == ichnos.summary(synthetic, "mart", "sales", 300)


def test_a_budget_below_one_is_a_usage_error(capsys: pytest.CaptureFixture[str]):
    code, _, err = _run(capsys, "summary", str(answer_key.QUERIES), "--budget", "0")
    assert code == 2
    assert err


def test_neighborhood_and_join_path_mirror_the_api(
    synthetic: ichnos.Graph, capsys: pytest.CaptureFixture[str]
):
    graph = synthetic
    code, out, err = _run(
        capsys,
        "neighborhood",
        str(answer_key.QUERIES),
        "sales.orders",
        "--depth",
        "0",
        "--examples",
    )
    assert (code, err) == (0, "")
    assert out == ichnos.dbml(
        graph.neighborhood([graph.table("sales.orders")], 0), examples=True
    )
    code, out, err = _run(
        capsys,
        "join-path",
        str(answer_key.QUERIES),
        "ref.countries",
        "inv.products",
        "--detail",
        "full",
    )
    assert (code, err) == (0, "")
    assert out == ichnos.dbml(
        graph.join_path([graph.table("ref.countries"), graph.table("inv.products")]),
        detail="full",
    )


def test_a_missing_table_names_up_to_three_close_matches(
    capsys: pytest.CaptureFixture[str],
):
    code, out, err = _run(
        capsys, "join-path", str(answer_key.QUERIES), "sales.orderz", "zzz"
    )
    assert (code, out) == (1, "")
    assert (
        err
        == "ichnos: no table sales.orderz; did you mean SALES.ORDERS or SALES.ORDER_LINES or SALES.V_ORDER_SUMMARY?\n"
    )
    assert (
        _run(capsys, "neighborhood", str(answer_key.QUERIES), "zzz")[2]
        == "ichnos: no table zzz\n"
    )


def test_a_core_over_the_budget_is_written_whole_with_one_stderr_line(
    capsys: pytest.CaptureFixture[str],
):
    code, out, err = _run(
        capsys,
        "neighborhood",
        str(answer_key.QUERIES),
        "sales.orders",
        "--budget",
        "100",
    )
    assert code == 0
    assert f"The core is {len(out):,} characters, over the 100-character budget." in out
    assert (
        err
        == f"ichnos: the core of this slice is {len(out):,} characters, over the 100-character budget\n"
    )


def test_upstream_and_downstream_mirror_the_api(
    synthetic: ichnos.Graph, capsys: pytest.CaptureFixture[str]
):
    graph = synthetic
    report = graph.report("055_key_customers")
    cases = [
        (["upstream", "--report", "055_key_customers"], graph.upstream(report)),
        (
            ["upstream", "--report", "055_key_customers", "--column", "customer_name"],
            graph.upstream(report.output_column("customer_name")),
        ),
        (
            ["upstream", "--table", "mart.customer_segments", "--indirect", "all"],
            graph.upstream(graph.table("mart.customer_segments"), "all"),
        ),
        (
            ["downstream", "--table", "sales.orders"],
            graph.downstream(graph.table("sales.orders")),
        ),
        (
            ["downstream", "--table", "sales.orders", "--column", "order_id"],
            graph.downstream(graph.table("sales.orders").column("order_id")),
        ),
    ]
    for tokens, found in cases:
        command, *options = tokens
        code, out, err = _run(capsys, command, str(answer_key.QUERIES), *options)
        assert (code, err) == (0, "")
        assert out == ichnos.dbml(found)


@pytest.mark.parametrize(
    ("tokens", "line"),
    [
        (
            ["upstream", "--report", "055_KEY_CUSTOMERS"],
            "ichnos: no report 055_KEY_CUSTOMERS; did you mean 055_key_customers or 056_key_customers_dashboard or 001_active_customers?\n",
        ),
        (
            ["upstream", "--report", "055_key_customers", "--column", "nope"],
            "ichnos: no output column nope in 055_key_customers\n",
        ),
        (
            ["downstream", "--table", "sales.orders", "--column", "order_idd"],
            "ichnos: no column order_idd in SALES.ORDERS; did you mean ORDER_ID or ORDER_DATE or ORDER_TOTAL?\n",
        ),
    ],
)
def test_a_missing_start_names_its_close_matches(
    capsys: pytest.CaptureFixture[str], tokens: list[str], line: str
):
    command, *options = tokens
    assert _run(capsys, command, str(answer_key.QUERIES), *options) == (1, "", line)


def test_upstream_takes_exactly_one_of_table_and_report(
    capsys: pytest.CaptureFixture[str],
):
    code, _, err = _run(capsys, "upstream", str(answer_key.QUERIES))
    assert code == 2
    assert err
    code, _, err = _run(
        capsys, "upstream", str(answer_key.QUERIES), "--table", "x", "--report", "y"
    )
    assert code == 2
