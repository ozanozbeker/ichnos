"""Run ichnos from the command line, with one command per API call (ADR 0014).

The commands call the public API alone, so the CLI prints nothing that a Python caller cannot get.
This module is the only one that imports cyclopts.
"""

import functools
import io
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts

from ichnos._corpus import read
from ichnos._dbml import dbml as write_dbml
from ichnos._graph import Graph, IchnosError

if TYPE_CHECKING:
    from collections.abc import Callable

app = cyclopts.App(
    name="ichnos", help="Infer an Oracle schema and its lineage from SQL queries alone."
)

type Output = Annotated[Path | None, cyclopts.Parameter(name=["--output", "-o"])]


def _command[**P](function: Callable[P, None]) -> Callable[P, None]:
    """Turn a user error into the `ichnos: <message>` line and exit code 1."""

    @functools.wraps(function)
    def run(*args: P.args, **kwargs: P.kwargs) -> None:
        try:
            function(*args, **kwargs)
        except IchnosError as error:
            sys.stderr.write(f"ichnos: {error}\n")
            raise SystemExit(1) from None

    return run


def _graph(corpus: Path) -> Graph:
    try:
        return read(corpus)
    except OSError as error:
        message = f"{error.strerror}: {corpus}"
        raise IchnosError(message) from None


def _write(text: str, output: Path | None) -> None:
    # A command writes through `sys.stdout`, because cyclopts would print a returned string through Rich.
    if output is None:
        sys.stdout.write(text)
    else:
        output.write_text(text, encoding="utf-8", newline="\n")


@app.command
@_command
def dbml(corpus: Path, /, *, output: Output = None) -> None:
    """Write the DBML file of the inferred schema.

    Parameters
    ----------
    corpus
        A folder of `.sql` files, or one file.
    output
        The file to write, instead of stdout.
    """
    _write(write_dbml(_graph(corpus)), output)


def main() -> None:
    r"""Run the CLI, writing UTF-8 with `\n` line endings on every OS."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", newline="\n")
    app(sys.argv[1:])
