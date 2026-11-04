"""Run ichnos on the synthetic corpus from a CLI page, so each build shows the current output."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Final

CORPUS: Final = Path("../../tests/fixtures/oracle_synthetic/queries")
"""The corpus the examples read, relative to a page in the build directory."""


def ichnos(*arguments: str) -> None:
    """Write a command line and its output, with `queries` standing for the synthetic corpus.

    Parameters
    ----------
    arguments
        The arguments after `ichnos`, where `queries` or a path under it names the corpus.
    """
    corpus = (Path.cwd() / CORPUS).resolve()
    if not corpus.is_dir():
        message = f"no corpus at {corpus}"
        raise FileNotFoundError(message)
    sys.stdout.write(f"$ ichnos {' '.join(arguments)}\n")
    command = [sys.executable, "-m", "ichnos"]
    command.extend(_argument(argument, corpus) for argument in arguments)
    # Rich reads the width from COLUMNS, and NO_COLOR keeps ANSI codes out of the page.
    environment = {**os.environ, "COLUMNS": "80", "NO_COLOR": "1"}
    environment.pop("FORCE_COLOR", None)
    # A page shows a user error on purpose, so a nonzero exit code is output, not a failure.
    result = subprocess.run(  # noqa: S603 # the arguments are the page's own
        command,
        capture_output=True,
        encoding="utf-8",
        env=environment,
        check=False,
    )
    sys.stdout.write(result.stdout)
    sys.stdout.write(result.stderr)
    if result.returncode != 0:
        sys.stdout.write(f"(exit code {result.returncode})\n")


def _argument(argument: str, corpus: Path) -> str:
    """Return the argument to pass, with the synthetic corpus in place of `queries`."""
    if argument == "queries":
        return str(corpus)
    if argument.startswith("queries/"):
        return str(corpus / argument.removeprefix("queries/"))
    return argument
