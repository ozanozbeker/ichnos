"""Run ichnos from the command line, with one command per API call (ADR 0014).

The commands call the public API alone, so the CLI prints nothing that a Python caller cannot get.
This module is the only one that imports cyclopts.
"""

import difflib
import functools
import io
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts

from ichnos._corpus import read
from ichnos._dbml import BUDGET, Detail, table_name
from ichnos._dbml import dbml as write_dbml
from ichnos._graph import Graph, IchnosError, Table
from ichnos._llm import summary as write_summary

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

app = cyclopts.App(
    name="ichnos", help="Infer an Oracle schema and its lineage from SQL queries alone."
)

type Output = Annotated[Path | None, cyclopts.Parameter(name=["--output", "-o"])]
type Budget = Annotated[
    int, cyclopts.Parameter(validator=cyclopts.validators.Number(gt=0))
]
type Suffix = Annotated[
    tuple[str, ...],
    cyclopts.Parameter(name="--suffix", negative="", consume_multiple=False),
]


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


def _graph(corpus: Path, suffix: tuple[str, ...], encoding: str) -> Graph:
    try:
        return read(corpus, suffix, encoding)
    except OSError as error:
        message = f"{error.strerror}: {corpus}"
        raise IchnosError(message) from None


def _note_unparsed(graph: Graph, corpus: Path) -> None:
    """Write one stderr line when any query is unparsed, so a slice stays clean to paste."""
    if graph.unparsed:
        total = len(graph.queries) + len(graph.unparsed)
        sys.stderr.write(
            f"ichnos: {len(graph.unparsed)} of {total} queries unparsed;"
            f" run ichnos unparsed {corpus} to list them\n"
        )


def _tables(graph: Graph, names: Iterable[str]) -> list[Table]:
    """Look each table up, and turn a missing one into a user error that names up to three close matches."""
    found: list[Table] = []
    for name in names:
        try:
            found.append(graph.table(name))
        except KeyError:
            known = [table_name(t) for t in graph.tables]
            close = difflib.get_close_matches(name.upper(), known, n=3)
            hint = f"; did you mean {' or '.join(close)}?" if close else ""
            message = f"no table {name}{hint}"
            raise IchnosError(message) from None
    return found


def _write_slice(text: str, budget: int, output: Path | None) -> None:
    _write(text, output)
    if len(text) > budget:
        # stderr reaches a user who pastes the slice without reading its header (ADR 0014).
        sys.stderr.write(
            f"ichnos: the core of this slice is {len(text):,} characters,"
            f" over the {budget:,}-character budget\n"
        )


def _write(text: str, output: Path | None) -> None:
    # A command writes through `sys.stdout`, because cyclopts would print a returned string through Rich.
    if output is None:
        sys.stdout.write(text)
    else:
        output.write_text(text, encoding="utf-8", newline="\n")


@app.command
@_command
def dbml(
    corpus: Path,
    /,
    *,
    output: Output = None,
    suffix: Suffix = (".sql",),
    encoding: str = "cp1252",
) -> None:
    """Write the DBML file of the inferred schema.

    Parameters
    ----------
    corpus
        A folder of query files, or one file.
    output
        The file to write, instead of stdout.
    suffix
        The suffix of the files to read in a folder, which can repeat.
    encoding
        The codec for a file with no BOM that fails UTF-8.
    """
    graph = _graph(corpus, suffix, encoding)
    _write(write_dbml(graph), output)
    _note_unparsed(graph, corpus)


@app.command
@_command
def summary(  # noqa: PLR0913 # one parameter per API parameter (ADR 0014)
    corpus: Path,
    /,
    *,
    owner: str | None = None,
    keyword: str | None = None,
    budget: Budget = BUDGET,
    output: Output = None,
    suffix: Suffix = (".sql",),
    encoding: str = "cp1252",
) -> None:
    """Write one line per table and report, so you can choose what to slice.

    Parameters
    ----------
    corpus
        A folder of query files, or one file.
    owner
        Keep only the tables of this owner, and the reports that read one.
    keyword
        Keep only the tables and reports whose names, column names or observed values contain it, ignoring case.
    budget
        The most characters the summary holds.
    output
        The file to write, instead of stdout.
    suffix
        The suffix of the files to read in a folder, which can repeat.
    encoding
        The codec for a file with no BOM that fails UTF-8.
    """
    graph = _graph(corpus, suffix, encoding)
    _write(write_summary(graph, owner, keyword, budget), output)
    _note_unparsed(graph, corpus)


@app.command
@_command
def neighborhood(  # noqa: PLR0913 # one parameter per API parameter (ADR 0014)
    corpus: Path,
    tables: Annotated[tuple[str, ...], cyclopts.Parameter(consume_multiple=True)],
    /,
    *,
    depth: Annotated[
        int, cyclopts.Parameter(validator=cyclopts.validators.Number(gte=0))
    ] = 1,
    budget: Budget = BUDGET,
    detail: Detail = "compact",
    examples: bool = False,
    output: Output = None,
    suffix: Suffix = (".sql",),
    encoding: str = "cp1252",
) -> None:
    """Write the tables within some relationships of one or more centers, as a DBML slice.

    Parameters
    ----------
    corpus
        A folder of query files, or one file.
    tables
        The center tables, such as `SALES.ORDERS`.
    depth
        The most relationships between a center and a table in the slice.
    budget
        The most characters the slice holds, which it cuts to fit down to its core.
    detail
        `compact` drops each column's position and type counts, and `full` keeps them.
    examples
        End the slice with example queries as comments.
    output
        The file to write, instead of stdout.
    suffix
        The suffix of the files to read in a folder, which can repeat.
    encoding
        The codec for a file with no BOM that fails UTF-8.
    """
    graph = _graph(corpus, suffix, encoding)
    found = graph.neighborhood(_tables(graph, tables), depth)
    _write_slice(write_dbml(found, budget, detail, examples), budget, output)
    _note_unparsed(graph, corpus)


@app.command(name="join-path")
@_command
def join_path(  # noqa: PLR0913 # one parameter per API parameter (ADR 0014)
    corpus: Path,
    tables: Annotated[tuple[str, ...], cyclopts.Parameter(consume_multiple=True)],
    /,
    *,
    budget: Budget = BUDGET,
    detail: Detail = "compact",
    examples: bool = False,
    output: Output = None,
    suffix: Suffix = (".sql",),
    encoding: str = "cp1252",
) -> None:
    """Write the shortest join paths between two or more tables, as a DBML slice.

    Parameters
    ----------
    corpus
        A folder of query files, or one file.
    tables
        Two or more tables, such as `SALES.ORDERS INV.PRODUCTS`.
    budget
        The most characters the slice holds, which it cuts to fit down to its core.
    detail
        `compact` drops each column's position and type counts, and `full` keeps them.
    examples
        End the slice with example queries as comments.
    output
        The file to write, instead of stdout.
    suffix
        The suffix of the files to read in a folder, which can repeat.
    encoding
        The codec for a file with no BOM that fails UTF-8.
    """
    graph = _graph(corpus, suffix, encoding)
    found = graph.join_path(_tables(graph, tables))
    _write_slice(write_dbml(found, budget, detail, examples), budget, output)
    _note_unparsed(graph, corpus)


@app.command
@_command
def unparsed(
    corpus: Path,
    /,
    *,
    output: Output = None,
    suffix: Suffix = (".sql",),
    encoding: str = "cp1252",
) -> None:
    """List each query that ichnos could not read, with the first line of its error.

    Parameters
    ----------
    corpus
        A folder of query files, or one file.
    output
        The file to write, instead of stdout.
    suffix
        The suffix of the files to read in a folder, which can repeat.
    encoding
        The codec for a file with no BOM that fails UTF-8.
    """
    graph = _graph(corpus, suffix, encoding)
    _write(
        "".join(f"{q.name}: {q.error.splitlines()[0]}\n" for q in graph.unparsed),
        output,
    )


def main() -> None:
    r"""Run the CLI, writing UTF-8 with `\n` line endings on every OS."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8", newline="\n")
    app(sys.argv[1:])
