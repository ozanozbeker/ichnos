import json
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, override

import pytest
from syrupy.extensions.single_file import SingleFileSnapshotExtension, WriteMode

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from syrupy.assertion import SnapshotAssertion

DBML = Path(__file__).parent / "dbml"

type Parsed = dict[str, Any]


class DbmlChecker:
    """One Node process that parses DBML texts with the pinned `@dbml/core` (ADR 0015)."""

    def __init__(self) -> None:
        node = shutil.which("node")
        if node is None or not (DBML / "node_modules").is_dir():
            pytest.fail(
                "the DBML tests need node and `npm ci --ignore-scripts` in tests/dbml"
            )
        self.process = subprocess.Popen(  # noqa: S603 # runs the checker this repo ships
            [node, "check.mjs"],
            cwd=DBML,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            encoding="utf-8",
        )

    def parse(self, text: str) -> Parsed:
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.write(json.dumps(text) + "\n")
        self.process.stdin.flush()
        return json.loads(self.process.stdout.readline())

    def check(self, text: str) -> Parsed:
        """Parse a text, and fail on any error or diagnostic."""
        parsed = self.parse(text)
        assert parsed["error"] is None, parsed["error"]
        assert parsed["diagnostics"] == [], parsed["diagnostics"]
        return parsed

    def close(self) -> None:
        assert self.process.stdin is not None
        assert self.process.stdout is not None
        self.process.stdin.close()
        self.process.wait()
        self.process.stdout.close()


@pytest.fixture(scope="session")
def dbml_checker() -> Iterator[DbmlChecker]:
    checker = DbmlChecker()
    yield checker
    checker.close()


@pytest.fixture
def assert_dbml_valid(dbml_checker: DbmlChecker) -> Callable[[str], Parsed]:
    return dbml_checker.check


class DbmlSnapshot(SingleFileSnapshotExtension):
    """Store a golden file as `.dbml`, so a reviewer opens it in dbdiagram, and check every text it compares."""

    file_extension = "dbml"
    _write_mode = WriteMode.TEXT
    checker: ClassVar[DbmlChecker]

    @override
    def serialize(self, data: Any, **_: Any) -> str:
        self.checker.check(data)
        return data


@pytest.fixture
def snapshot_dbml(
    snapshot: SnapshotAssertion, dbml_checker: DbmlChecker
) -> SnapshotAssertion:
    extension = type("BoundDbmlSnapshot", (DbmlSnapshot,), {"checker": dbml_checker})
    return snapshot.use_extension(extension)


class TextSnapshot(SingleFileSnapshotExtension):
    """Store a golden file as `.txt`, so a reviewer reads it as the CLI prints it."""

    file_extension = "txt"
    _write_mode = WriteMode.TEXT


@pytest.fixture
def snapshot_text(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    return snapshot.use_extension(TextSnapshot)
