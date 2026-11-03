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
    (tmp_path / "notes.txt").write_text("SELECT t.x FROM t", encoding="utf-8")
    with pytest.raises(ichnos.IchnosError, match=r"no \.sql file in"):
        ichnos.read(tmp_path)


def test_read_matches_a_suffix_without_regard_to_case(tmp_path: Path):
    (tmp_path / "a.SQL").write_text("SELECT t.x FROM t", encoding="utf-8")
    (tmp_path / "b.txt").write_text("SELECT t.y FROM t", encoding="utf-8")
    assert [q.name for q in ichnos.read(tmp_path).queries] == ["a"]
    assert [q.name for q in ichnos.read(tmp_path, (".sql", ".TXT")).queries] == [
        "a",
        "b",
    ]


def test_read_skips_hidden_files_and_folders(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "a.sql").write_text("SELECT t.x FROM t", encoding="utf-8")
    (tmp_path / ".b.sql").write_text("SELECT t.x FROM t", encoding="utf-8")
    (tmp_path / "c.sql").write_text("SELECT t.x FROM t", encoding="utf-8")
    assert [q.name for q in ichnos.read(tmp_path).queries] == ["c"]


def test_read_raises_on_two_files_with_one_key(tmp_path: Path):
    (tmp_path / "x.sql").write_text("SELECT t.x FROM t", encoding="utf-8")
    (tmp_path / "x.txt").write_text("SELECT t.x FROM t", encoding="utf-8")
    with pytest.raises(
        ichnos.IchnosError, match=r"two files give the key x: x\.sql and x\.txt"
    ):
        ichnos.read(tmp_path, (".sql", ".txt"))


QUERY = 'SELECT t."é" FROM t'


@pytest.mark.parametrize(
    ("bom", "codec"),
    [
        (b"\xff\xfe\x00\x00", "utf-32-le"),
        (b"\x00\x00\xfe\xff", "utf-32-be"),
        (b"\xef\xbb\xbf", "utf-8"),
        (b"\xff\xfe", "utf-16-le"),
        (b"\xfe\xff", "utf-16-be"),
    ],
)
def test_a_bom_picks_the_codec(tmp_path: Path, bom: bytes, codec: str):
    (tmp_path / "q.sql").write_bytes(bom + QUERY.encode(codec))
    graph = ichnos.read(tmp_path, encoding="ascii")
    assert graph.queries[0].text == QUERY
    assert [c.name for c in graph.tables[0].columns] == ["é"]


def test_a_file_that_fails_utf_8_decodes_as_cp1252(tmp_path: Path):
    (tmp_path / "q.sql").write_bytes(QUERY.encode("cp1252"))
    assert ichnos.read(tmp_path).queries[0].text == QUERY


def test_a_file_that_fails_cp1252_raises_with_its_byte_offset(tmp_path: Path):
    (tmp_path / "q.sql").write_bytes(b"SELECT '\x81' FROM t")
    with pytest.raises(
        ichnos.IchnosError,
        match=r"q\.sql does not decode as cp1252 at byte 8; name its codec with --encoding",
    ):
        ichnos.read(tmp_path)
    assert (
        ichnos.read(tmp_path, encoding="latin-1").queries[0].text
        == "SELECT '\x81' FROM t"
    )


def test_a_bom_file_that_fails_its_codec_raises(tmp_path: Path):
    (tmp_path / "q.sql").write_bytes(b"\xef\xbb\xbfSELECT '\xff' FROM t")
    with pytest.raises(
        ichnos.IchnosError, match=r"does not decode as utf-8 at byte 11"
    ):
        ichnos.read(tmp_path)


def test_an_unknown_encoding_raises(tmp_path: Path):
    with pytest.raises(ichnos.IchnosError, match=r"unknown encoding nope"):
        ichnos.read(tmp_path, encoding="nope")


def test_read_turns_every_line_ending_into_a_newline(tmp_path: Path):
    (tmp_path / "q.sql").write_bytes(b"SELECT t.x\r\n  FROM t\r  WHERE t.y = 1")
    assert (
        ichnos.read(tmp_path).queries[0].text == "SELECT t.x\n  FROM t\n  WHERE t.y = 1"
    )


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


def test_text_that_does_not_tokenize_is_one_unparsed_query():
    graph = ichnos.infer({"f": "SELECT 'open; SELECT 2"})
    assert [q.text for q in graph.unparsed] == ["SELECT 'open; SELECT 2"]
