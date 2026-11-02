# ruff: noqa: T201, INP001
"""Run the construct probes, or writing queries 022 to 026, through one column lineage tool.

DataHub pins its own sqlglot, so each tool runs in its own environment, for example
`uv run --no-project --python 3.13 --with sqllineage==1.5.9 python -I docs/research/column_lineage_probes.py sqllineage`.
The other `--with` values are `sqlglot==30.26.0`, `openlineage-sql==1.55.0` and `"acryl-datahub[sql-parser]==1.7.0.19"`, and a corpus `queries` folder after the tool name selects the writing queries.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# t1 (k, x, y) and t3 (k, w) are read; t2 (a, b) is written.
SCHEMA = {
    "T1": {"K": "NUMBER", "X": "NUMBER", "Y": "NUMBER"},
    "T3": {"K": "NUMBER", "W": "NUMBER"},
}
PROBES = {
    "insert_column_list": "INSERT INTO t2 (a, b) SELECT x, y + 1 FROM t1",
    "insert_no_list": "INSERT INTO t2 SELECT x, y FROM t1",
    "ctas": "CREATE TABLE t2 AS SELECT x AS a, y FROM t1",
    "view_column_list": "CREATE VIEW v2 (a, b) AS SELECT x, y FROM t1",
    "update_bare": "UPDATE t2 SET a = b",
    "update_expr_subquery": "UPDATE t2 SET a = a + 1, b = (SELECT MAX(t1.y) FROM t1 WHERE t1.k = t2.a)",
    "merge": (
        "MERGE INTO t2 tgt USING (SELECT k, y FROM t1) src ON (tgt.a = src.k) "
        "WHEN MATCHED THEN UPDATE SET tgt.b = src.y "
        "WHEN NOT MATCHED THEN INSERT (a, b) VALUES (src.k, src.y + 1)"
    ),
    "star": "INSERT INTO t2 SELECT * FROM t1",
    "cte": "INSERT INTO t2 (a) WITH c AS (SELECT x AS z FROM t1) SELECT z FROM c",
    "derived": "INSERT INTO t2 (a) SELECT d.z FROM (SELECT x AS z FROM t1) d",
    "set_op": "INSERT INTO t2 (a) SELECT x FROM t1 UNION ALL SELECT w FROM t3",
    "correlated": "INSERT INTO t2 (a, b) SELECT t1.x, (SELECT MAX(t3.w) FROM t3 WHERE t3.k = t1.k) FROM t1",
    "indirect_count": (
        "INSERT INTO t2 (a, b) SELECT t1.x, COUNT(*) FROM t1 JOIN t3 ON t3.k = t1.k "
        "WHERE t1.y > 0 GROUP BY t1.x ORDER BY t1.x"
    ),
    "case_window": (
        "INSERT INTO t2 (a, b) SELECT CASE WHEN t1.y > 0 THEN t1.x ELSE 0 END, "
        "ROW_NUMBER() OVER (PARTITION BY t1.k ORDER BY t1.y) FROM t1"
    ),
    "report": "SELECT t1.x, COUNT(*) AS n FROM t1 GROUP BY t1.x",
    "unqualified_two_tables": "INSERT INTO t2 (a) SELECT w FROM t1 JOIN t3 ON t3.k = t1.k",
}


def run_sqlglot(sql: str) -> dict:
    """Return lineage() output names and leaves, with no schema and with the probe schema."""
    from sqlglot.lineage import lineage  # noqa: PLC0415

    out = {}
    for label, schema in (("no_schema", {}), ("schema", SCHEMA)):
        try:
            result = lineage(None, sql, schema, dialect="oracle")
        except Exception as e:  # noqa: BLE001 - the error is the measurement
            out[label] = f"raises {type(e).__name__}: {str(e).splitlines()[0]}"
            continue
        out[label] = {
            name: sorted(
                f"{type(n.expression).__name__}:{n.name}"
                for n in node.walk()
                if not n.downstream and n is not node
            )
            for name, node in result.items()
        }
    return out


def run_sqllineage(sql: str) -> dict:
    """Return sqllineage's column paths and tables for the oracle dialect."""
    from sqllineage.runner import LineageRunner  # noqa: PLC0415

    try:
        runner = LineageRunner(sql, dialect="oracle")
        paths = [
            " <- ".join(str(c) for c in reversed(path))
            for path in runner.get_column_lineage()
        ]
        return {
            "paths": sorted(paths),
            "read": sorted(map(str, runner.source_tables)),
            "write": sorted(map(str, runner.target_tables)),
        }
    except Exception as e:  # noqa: BLE001
        return {"raises": f"{type(e).__name__}: {str(e).splitlines()[0]}"}


def run_openlineage(sql: str) -> dict:
    """Return openlineage-sql's column lineage for the generic dialect, the closest to Oracle."""
    import openlineage_sql  # noqa: PLC0415

    meta = openlineage_sql.parse([sql], dialect="generic")

    def col(c: object) -> str:
        return f"{c.origin.name if c.origin else None}.{c.name}"

    return {
        "columns": sorted(
            f"{col(cl.descendant)} <- {sorted(col(x) for x in cl.lineage)}"
            for cl in meta.column_lineage
        ),
        "read": sorted(t.name for t in meta.in_tables),
        "write": sorted(t.name for t in meta.out_tables),
        "errors": [e.message for e in meta.errors],
    }


def run_datahub(sql: str) -> dict:
    """Return DataHub's column lineage with no registered schema, then with the probe schema."""
    from datahub.sql_parsing.schema_resolver import SchemaResolver  # noqa: PLC0415
    from datahub.sql_parsing.sqlglot_lineage import sqlglot_lineage  # noqa: PLC0415

    out = {}
    urns: list[str] = []
    for label in ("no_schema", "schema"):
        # sqlglot_lineage() caches by resolver, so the second pass needs a new one.
        resolver = SchemaResolver(platform="oracle")
        for urn in urns:
            name = urn.split(",")[1].upper()
            if name in SCHEMA:
                resolver.add_raw_schema_info(
                    urn, {k.lower(): v for k, v in SCHEMA[name].items()}
                )
        res = sqlglot_lineage(sql, resolver)
        urns = [*res.in_tables, *res.out_tables]
        out[label] = {
            "columns": sorted(
                f"{c.downstream.table and c.downstream.table.split(',')[1]}.{c.downstream.column} <- "
                f"{sorted(u.table.split(',')[1] + '.' + u.column for u in c.upstreams)} "
                f"copy={c.logic.is_direct_copy if c.logic else None}"
                for c in res.column_lineage or []
            ),
            "read": sorted(u.split(",")[1] for u in res.in_tables),
            "write": sorted(u.split(",")[1] for u in res.out_tables),
            "column_error": str(res.debug_info.column_error).splitlines()[0]
            if res.debug_info.column_error
            else None,
            "confidence": res.debug_info.confidence,
        }
    return out


def main() -> None:
    """Print one JSON line per probe, or per writing query when a corpus folder follows the tool."""
    tool = sys.argv[1]
    run = {
        "sqlglot": run_sqlglot,
        "sqllineage": run_sqllineage,
        "openlineage": run_openlineage,
        "datahub": run_datahub,
    }[tool]
    probes = PROBES
    if len(sys.argv) > 2:  # noqa: PLR2004
        files = sorted(Path(sys.argv[2]).glob("02[2-6]_*.sql"))
        probes = {f.stem: f.read_text().strip().rstrip(";") for f in files}
    for name, sql in probes.items():
        print(
            json.dumps(
                {"tool": tool, "probe": name, "result": run(sql)}, sort_keys=True
            )
        )


if __name__ == "__main__":
    main()
