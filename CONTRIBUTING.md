# Contributing

ichnos follows the release standard in [Epistole's `CONTRIBUTING.md`](https://github.com/ozanozbeker/epistole/blob/main/CONTRIBUTING.md).
Copied from Epistole at `cc9437a`.

## Departures

ichnos departs from the standard in these places:

| Standard | ichnos | Reason |
| --- | --- | --- |
| The floor is the oldest CPython that has not reached its end of life, 3.11 today. | The floor is 3.14. | uv installs a Python that meets the floor, on the maintainer's Windows work machine too ([ADR 0005](https://github.com/ozanozbeker/ichnos/blob/main/docs/adr/0005-runtime-dependencies-stop-at-the-newest-tested-release.md)). |
| rumdl skips `docs/adr/`. | rumdl checks `docs/adr/`. | The ADRs already pass, so the check costs nothing. |
| prek runs no spell checker. | prek runs `typos`. | It catches misspellings in prose and identifiers that ruff and rumdl do not check. |
| `test` runs on Ubuntu, macOS and Windows. | `test` and `uvx` run on Ubuntu only. | macOS jobs waited over 15 minutes for a runner on 2026-11-03 and hit `timeout-minutes`. The maintainer runs ichnos on Windows, and CI no longer checks its Windows stdout and path code ([ADR 0015](https://github.com/ozanozbeker/ichnos/blob/main/docs/adr/0015-tests-score-the-answer-key-through-deviation-lists-and-parse-dbml-with-dbml-core.md)). |
