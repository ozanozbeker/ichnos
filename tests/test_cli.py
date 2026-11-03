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


def test_dbml_writes_the_full_file_to_stdout(capsys: pytest.CaptureFixture[str]):
    code, out, err = _run(capsys, "dbml", str(answer_key.QUERIES))
    assert (code, err) == (0, "")
    assert out == ichnos.dbml(ichnos.read(answer_key.QUERIES))


def test_dbml_writes_the_output_file(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    output = tmp_path / "schema.dbml"
    code, out, _ = _run(capsys, "dbml", str(answer_key.QUERIES), "-o", str(output))
    assert (code, out) == (0, "")
    assert output.read_bytes() == ichnos.dbml(ichnos.read(answer_key.QUERIES)).encode()


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
    (corpus / "q.sql").write_text('SELECT t."café" FROM t\n', encoding="utf-8")
    output = tmp_path / "schema.dbml"
    command = [sys.executable, "-m", "ichnos", "dbml", str(corpus)]
    stdout = subprocess.run(command, capture_output=True, check=True).stdout  # noqa: S603 # runs ichnos itself
    subprocess.run([*command, "-o", str(output)], check=True)  # noqa: S603 # runs ichnos itself
    assert stdout == output.read_bytes()
    assert '"café" unknown'.encode() in stdout
    assert not stdout.startswith(b"\xef\xbb\xbf")
    assert b"\r" not in stdout
