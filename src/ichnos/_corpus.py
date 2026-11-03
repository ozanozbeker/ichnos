"""Read a corpus from disk and build its graph with `infer`.

The graph module builds a graph from text, and this module decides which files that text comes from (ADR 0014).
"""

from pathlib import Path

from ichnos._graph import Graph, IchnosError, infer


def read(path: str | Path) -> Graph:
    """Read a folder of `.sql` files, or one file, and build its graph.

    Parameters
    ----------
    path
        A folder, whose `.sql` files ichnos reads in every subfolder, or one file of any suffix.

    Returns
    -------
    :
        The graph of the corpus.

    Raises
    ------
    IchnosError
        When the folder holds no `.sql` file.

    Examples
    --------
    ```python
    import tempfile
    from pathlib import Path

    import ichnos

    folder = Path(tempfile.mkdtemp())
    (folder / "q.sql").write_text("SELECT o.order_id FROM sales.orders o")
    ichnos.read(folder).tables
    ```
    """
    path = Path(path)
    if not path.is_dir():
        return infer({path.stem: path.read_text(encoding="utf-8")})
    files = {
        p.relative_to(path).with_suffix("").as_posix(): p
        for p in sorted(path.rglob("*.sql"))
    }
    if not files:
        message = f"no .sql file in {path}"
        raise IchnosError(message)
    return infer({key: file.read_text(encoding="utf-8") for key, file in files.items()})
