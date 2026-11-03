# Contributing

ichnos follows the release standard in [Epistole's `CONTRIBUTING.md`](https://github.com/ozanozbeker/epistole/blob/main/CONTRIBUTING.md).
Copied from Epistole at `cc9437a`.

## Departures

ichnos departs from the standard in these places:

| Standard | ichnos | Reason |
| --- | --- | --- |
| The floor is the oldest CPython that has not reached its end of life, 3.11 today. | The floor is 3.14. | uv installs a Python that meets the floor, on the maintainer's Windows work machine too ([ADR 0005](docs/adr/0005-runtime-dependencies-stop-at-the-newest-tested-release.md)). |
| Each `dev` tool has a floor at its newest release that is at least 7 days old. | Each `dev` tool is a bare name. | Users never install the group, and `uv.lock` already pins the version that runs. |
| rumdl skips `docs/adr/`. | rumdl checks `docs/adr/`. | The ADRs already pass, so the check costs nothing. |
| prek runs no spell checker. | prek runs `typos`. | It catches misspellings in prose and identifiers that ruff and rumdl do not check. |
