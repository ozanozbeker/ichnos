"""Read a corpus from disk, decoding each file on its own, and build its graph with `infer`.

The graph module builds a graph from text, and this module picks which files that text comes from (ADR 0014).
One corpus can mix files from several Windows editors, so a fixed rule, not the locale, picks each file's codec.
"""

import codecs
from pathlib import Path

from ichnos._graph import Graph, IchnosError, infer

# UTF-32 LE comes before UTF-16 LE, because its BOM starts with UTF-16 LE's.
_BOMS = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)


def read(
    path: str | Path, suffixes: tuple[str, ...] = (".sql",), encoding: str = "cp1252"
) -> Graph:
    r"""Read a folder of query files, or one file, and build its graph.

    In a folder, `read` reads every file whose suffix is in `suffixes`, ignoring case, in every subfolder.
    It skips each file and folder whose name starts with `.`.
    Each file decodes by its BOM, then as strict UTF-8, then as strict `encoding`, and every `\r\n` and `\r` becomes `\n`.

    Parameters
    ----------
    path
        A folder, or one file of any suffix.
        A file's key is its path relative to the folder, without the suffix, with `/` between folders.
    suffixes
        The suffixes of the files to read in a folder. The default reads `.sql` files only.
    encoding
        The codec for a file with no BOM that fails UTF-8. The default, cp1252, is what most Windows editors in the West write.

    Returns
    -------
    :
        The graph of the corpus.

    Raises
    ------
    IchnosError
        When the folder holds no matching file, two files give one key, a file does not decode, or `encoding` names no codec.
    OSError
        When `path` does not exist or a file cannot be read.

    Examples
    --------
    ```python
    import tempfile
    from pathlib import Path

    import ichnos

    folder = Path(tempfile.mkdtemp())
    (folder / "q.sql").write_bytes(
        "SELECT o.order_id FROM sales.orders o\r\n".encode("cp1252")
    )
    ichnos.read(folder).queries
    ```
    """
    try:
        codecs.lookup(encoding)
    except LookupError:
        message = f"unknown encoding {encoding}"
        raise IchnosError(message) from None
    path = Path(path)
    files = _files(path, suffixes) if path.is_dir() else {path.stem: path}
    return infer({key: _decode(file, encoding) for key, file in files.items()})


def _files(folder: Path, suffixes: tuple[str, ...]) -> dict[str, Path]:
    # `Path.glob` ignores case on Windows only, so the suffix test runs here on every OS.
    wanted = {s.lower() for s in suffixes}
    files: dict[str, Path] = {}
    for root, folders, names in folder.walk():
        folders[:] = sorted(f for f in folders if not f.startswith("."))
        for name in sorted(names):
            file = root / name
            if name.startswith(".") or file.suffix.lower() not in wanted:
                continue
            key = file.relative_to(folder).with_suffix("").as_posix()
            if key in files:
                message = f"two files give the key {key}: {files[key].relative_to(folder)} and {file.relative_to(folder)}"
                raise IchnosError(message)
            files[key] = file
    if not files:
        message = f"no {' or '.join(suffixes)} file in {folder}"
        raise IchnosError(message)
    return files


def _decode(file: Path, fallback: str) -> str:
    data = file.read_bytes()
    for bom, codec in _BOMS:
        if data.startswith(bom):
            text = _strict(file, data, codec, len(bom))
            break
    else:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = _strict(file, data, fallback, 0)
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _strict(file: Path, data: bytes, codec: str, start: int) -> str:
    try:
        return data[start:].decode(codec)
    except UnicodeDecodeError as error:
        offset = start + error.start
        message = f"{file} does not decode as {codec} at byte {offset}; name its codec with --encoding"
        raise IchnosError(message) from None
