from typing import TYPE_CHECKING

import pytest

import ichnos

if TYPE_CHECKING:
    from pathlib import Path


def test_read_builds_each_key_from_the_relative_path(tmp_path: Path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.sql").write_text(
        "SELECT t.x FROM t; SELECT t.y FROM t", encoding="utf-8"
    )
    (tmp_path / "b.sql").write_text("SELECT t.z FROM t", encoding="utf-8")
    assert [q.name for q in ichnos.read(tmp_path).queries] == [
        "b",
        "sub/a#1",
        "sub/a#2",
    ]


def test_read_takes_one_file_of_any_suffix(tmp_path: Path):
    path = tmp_path / "one.txt"
    path.write_text("SELECT t.x FROM t", encoding="utf-8")
    assert [q.name for q in ichnos.read(path).queries] == ["one"]


def test_read_raises_on_a_folder_with_no_query_file(tmp_path: Path):
    with pytest.raises(ichnos.IchnosError, match=r"no \.sql file in"):
        ichnos.read(tmp_path)


def test_read_raises_os_error_on_a_missing_path(tmp_path: Path):
    with pytest.raises(OSError, match="No such file"):
        ichnos.read(tmp_path / "missing")


def test_a_slash_line_ends_a_query():
    text = "SELECT t.x FROM t\n/\nSELECT t.y FROM t;\n  /  \nSELECT '/\n' FROM t\n"
    assert [q.text for q in ichnos.infer({"f": text}).queries] == [
        "SELECT t.x FROM t",
        "SELECT t.y FROM t",
        "SELECT '/\n' FROM t",
    ]


def test_text_that_does_not_tokenize_is_one_query():
    assert [q.text for q in ichnos.infer({"f": "SELECT 'open; SELECT 2"}).queries] == [
        "SELECT 'open; SELECT 2"
    ]
