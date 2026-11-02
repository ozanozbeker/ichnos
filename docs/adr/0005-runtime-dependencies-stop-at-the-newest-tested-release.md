# Runtime dependencies stop at the newest tested release, and the floor Python is 3.14

ichnos has two runtime dependencies: sqlglot and cyclopts.
Everything else comes from the standard library.
The records and the graph use `dataclasses`, the join path uses ichnos's own breadth-first search, and the DBML and LLM text are plain strings.
A new runtime dependency needs its own decision.

Users run ichnos with `uvx ichnos` or `uv tool install ichnos`.
Both resolve fresh from the ranges in `pyproject.toml` and ignore `uv.lock`.
So each range stops at the newest release that CI has tested, or a user gets an untested release on their next run.

sqlglot's README says a minor release is backwards-incompatible and only a patch is compatible.
Major 30 had 34 minors between 2026-03-16 and 2026-10-30, so a `<31` cap protects nothing.
The sqlglot cap sits one minor above the newest tested minor, starting at `sqlglot>=30.26.0,<30.28`.
cyclopts follows semver, and its last two majors came on 2025-10-20 and 2026-09-23, so its cap is the next major, `<6`.

Dependabot's weekly `uv` group pull request widens a cap once a new release is 7 days old, as it widened `uv_build`'s cap in Epistole.
CI's answer-key tests gate that pull request.
It is a `chore:` commit, so a raised cap reaches users at the next ichnos release.
A floor rises only in a `deps:` commit, which starts a release, when ichnos needs a fix from a newer release, such as sqlglot's `:1` bug.
Otherwise each floor is the oldest release that the `lowest` job passes, as Epistole's standard sets.

The `c` extra installs `sqlglot[c]`, so `uvx "ichnos[c]"` runs on the compiled build.
sqlglotc 30.27.0 ships cp314 and cp315 wheels for Windows, macOS and Linux, so the extra needs no compiler.

`requires-python` is `>=3.14`.
uv installs a Python that meets the floor, and it does so on the maintainer's Windows work machine.
CI tests every final CPython from the floor up.
The floor rises only when the code needs a newer feature, in a `feat!:` commit.
This departs from Epistole's rule to support every CPython that has not reached its end of life, which would set the floor at 3.11.

## Considered options

- A cap at sqlglot's major, `<31`.
  Rejected because a sqlglot minor can break ichnos.
- No cap on sqlglot.
  Rejected for the same reason.
- An exact pin, `==30.26.0`.
  Rejected because sqlglot's patches are backwards-compatible and carry fixes.
- typer for the CLI.
  Rejected because its help text goes in `Annotated[..., Option(help=...)]`, so each parameter is documented twice.
  cyclopts reads the help text from the numpydoc docstring.
- argparse for the CLI.
  Rejected because it reads nothing from annotations.
- A floor of 3.11, as Epistole's rule sets.
  Rejected because uv supplies the Python, and 3.14 has PEP 695 syntax and `typing.override` without a shim.
- Only `uvx --with "sqlglot[c]" ichnos`, as ADR 0004 first said.
  It still works, but the extra names the option in the package metadata.
