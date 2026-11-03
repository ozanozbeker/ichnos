"""PROTOTYPE, throwaway: write sample DBML for a slice of the synthetic corpus in three variants.

The schema claims and their counts are hand-entered and illustrative. The lineage comes from
`answer_key/lineage.csv`, with 016's unqualified columns turned into ambiguities as ichnos would.
Run: uv run --no-project python prototypes/dbml_output/build.py
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
CORPUS = HERE.parent.parent / "tests" / "fixtures" / "oracle_synthetic"
VARIANTS = {"a_settings": "A", "b_notes": "B", "c_comments": "C"}

# --- escaping and names -------------------------------------------------------------------

ESCAPES = {"\\": "\\\\", '"': '\\"', "'": "\\'", "\n": "\\n", "\r": "\\r", "\t": "\\t"}


def esc(text):
    return "".join(ESCAPES.get(c, c) for c in text)


def lit(text):
    return f"'{esc(text)}'"


def name(part):
    return part if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", part) else f'"{esc(part)}"'


def tname(table):
    return ".".join(name(p) for p in table.split("."))


def cref(table, cols):
    if isinstance(cols, str):
        return f"{tname(table)}.{name(cols)}"
    return f"{tname(table)}.({', '.join(name(c) for c in cols)})"


# --- schema slice: hand-entered claims -----------------------------------------------------
# column: (name, type, {evidence kind: count}, {fact: text}); type None means no type evidence.
# A fact key "null" marks a nullable claim; its value is the nullable evidence count.


def col(n, typ=None, nullable=0, observed=(), declared=0, undeclared=False, **ev):
    return {
        "name": n,
        "type": typ,
        "nullable": nullable,
        "observed": list(observed),
        "declared": declared,
        "undeclared": undeclared,
        "ev": ev,
        "facts": {},
    }


TABLES = {}


def table(t, cols, keys=(), kind=None, complete=False, ev=None, facts=None):
    TABLES[t] = {
        "cols": {c["name"]: c for c in cols},
        "keys": list(keys),
        "kind": kind,
        "complete": complete,
        "ev": ev or {},
        "facts": facts or {},
    }


AMB_016 = (
    "016 reads CREDIT_LIMIT, CUSTOMER_NAME, ORDER_DATE, ORDER_ID and ORDER_TOTAL unqualified "
    "over SALES.CUSTOMERS and SALES.ORDERS"
)

table(
    "SALES.CUSTOMERS",
    [
        col("CUSTOMER_ID", select=6, join=12, where=1),
        col("CUSTOMER_NAME", select=9),
        col("CUSTOMER_TYPE", "text", observed=["RETAIL", "TRADE"], select=2, where=2, text=2),
        col("EMAIL", "text", select=2, join=1, text=1),
        col("STATUS", "text", observed=["A"], where=2, text=2),
        col("CREATED_AT", "datetime", where=1, datetime=1),
    ],
    keys=[(["CUSTOMER_ID"], "<S>_ID", {})],
    ev={"read": 16},
    facts={"ambiguity": AMB_016},
)
table(
    "CUSTOMERS",
    [
        col("CUSTOMER_ID", select=1, join=1),
        col("CUSTOMER_NAME", select=1),
        col("CUSTOMER_TYPE", "text", observed=["TRADE"], select=1, where=1, text=1),
    ],
    keys=[(["CUSTOMER_ID"], "<S>_ID", {})],
    ev={"read": 1},
    facts={"ambiguity": "may be SALES.CUSTOMERS (read 16)"},
)
table(
    "ORDERS",
    [
        col("ORDER_ID", select=1),
        col("ORDER_DATE", select=1),
        col("CUSTOMER_ID", join=1),
    ],
    keys=[(["ORDER_ID"], "<S>_ID", {})],
    ev={"read": 1},
    facts={"ambiguity": "may be SALES.ORDERS (read 24)"},
)
table(
    "SALES.ORDERS",
    [
        col("ORDER_ID", "number", select=14, join=9, insert=1, number=1),
        col("CUSTOMER_ID", select=8, join=6, where=3, insert=1),
        col("ORDER_DATE", "datetime", select=9, where=4, insert=1, datetime=3),
        col("STATUS", "text", observed=["CANCELLED", "NEW", "SHIPPED"], select=3, where=6, insert=1, text=6),
        col("SALES_REP_ID", "number", nullable=2, select=3, insert=1, number=1),
        col("ORDER_TOTAL", select=2, where=1),
        col("CURRENCY_CODE", select=3, join=1, insert=1),
        col("SHIP_TO_ADDRESS_ID", join=1, insert=1),
        col("BILL_TO_ADDRESS_ID", join=1, insert=1),
        col("CREATED_AT", "datetime", insert=1, datetime=1),
    ],
    keys=[(["ORDER_ID"], "<S>_ID", {"generated": 1})],
    ev={"read": 24, "write": 1},
    facts={"ambiguity": AMB_016},
)
table(
    "SALES.ORDER_LINES",
    [
        col("ORDER_ID", select=4, join=7),
        col("LINE_NO", select=3, join=2),
        col("PRODUCT_ID", select=2, join=5),
        col("QUANTITY", "number", select=5, number=4),
        col("UNIT_PRICE", "number", select=3, number=3),
        col("DISCOUNT_PCT", "number", nullable=2, select=2, number=2),
    ],
    ev={"read": 9},
)
table(
    "SALES.PROMOTIONS",
    [
        col("PROMO_ID", join=1),
        col("PROMO_CODE", "text", select=1, where=1, text=1),
        col("PERCENT_OFF", select=1),
    ],
    ev={"read": 2},
)
table(
    "SALES.ORDER_PROMOTIONS",
    [col("ORDER_ID", join=1), col("PROMO_ID", join=1)],
    ev={"read": 1},
)
table(
    "HR.EMPLOYEES",
    [
        col("EMPLOYEE_ID", select=4, join=3),
        col("LAST_NAME", select=3),
        col("MANAGER_ID", select=1, join=2),
        col("EMAIL", "text", join=1, text=1),
        col("STATUS", "text", observed=["A"], where=1, text=1),
    ],
    keys=[(["EMPLOYEE_ID"], "<S>_ID", {})],
    ev={"read": 6},
)
table(
    "INV.PRODUCTS",
    [
        col("PRODUCT_ID", select=3, join=6),
        col("SKU", select=2),
        col("CATEGORY_ID", select=2, join=2),
        col("CREATED_AT", "datetime", where=1, datetime=1),
    ],
    keys=[(["PRODUCT_ID"], "<S>_ID", {})],
    ev={"read": 7},
)
table(
    "INV.WAREHOUSES",
    [col("ID", select=1, join=3), col("WAREHOUSE_CODE", select=2), col("NAME", select=2)],
    keys=[(["ID"], "ID", {}), (["WAREHOUSE_CODE"], "<S>_CODE", {})],
    ev={"read": 3},
)
table(
    "INV.STOCK_LEVELS",
    [
        col("PRODUCT_ID", select=1, join=3, insert=1),
        col("WAREHOUSE_ID", join=2, where=1, insert=1),
        col("QTY_ON_HAND", "number", select=1, where=1, set=1, insert=1, number=1),
        col("REORDER_POINT", select=1, where=1),
        col("UPDATED_AT", "datetime", set=1, insert=1, datetime=2),
    ],
    keys=[(["PRODUCT_ID", "WAREHOUSE_ID"], None, {"merge": 1})],
    ev={"read": 3, "write": 2},
)
table(
    "INV.SHIPMENTS",
    [col("SHIPMENT_ID", where=2), col("WAREHOUSE_ID", select=2, join=1)],
    keys=[(["SHIPMENT_ID"], "<S>_ID", {"single_row": 1})],
    ev={"read": 3},
)
table(
    "INV.SHIPMENT_LINES",
    [
        col("SHIPMENT_ID", where=1, join=1),
        col("ORDER_ID", join=2),
        col("LINE_NO", join=2),
        col("QTY_SHIPPED", "number", select=1, number=1),
    ],
    ev={"read": 2},
)
table(
    "MART.ORDER_LINE_FACTS",
    [
        col("ORDER_ID", declared=1, insert=1),
        col("LINE_NO", declared=1, insert=1),
        col("CUSTOMER_ID", declared=1, insert=1, select=2, group_by=2),
        col("SALES_DATE", "datetime", declared=1, insert=1, select=2, where=1, group_by=2, datetime=1),
        col("CURRENCY_CODE", declared=1, insert=1, select=2, group_by=2),
        col("PRODUCT_ID", declared=1, insert=1),
        col("CATEGORY_ID", declared=1, insert=1, select=1),
        col("UNITS", declared=1, insert=1, aggregate=2),
        col("NET_AMOUNT", "number", declared=1, insert=1, aggregate=3, number=1),
    ],
    kind="base table",
    complete=True,
    ev={"declared": 1, "read": 3, "write": 1},
)
table(
    "MART.CUSTOMER_DAILY_SALES",
    [
        col("CUSTOMER_ID", declared=1, insert=1, select=1, join=1, group_by=1),
        col("SALES_DATE", declared=1, insert=1, join=1, where=1),
        col("CURRENCY_CODE", declared=1, insert=1, join=1),
        col("LINE_COUNT", "number", declared=1, insert=1, set=1, number=1),
        col("UNITS", "number", declared=1, insert=1, set=1, number=1),
        col("NET_AMOUNT", "number", declared=1, insert=1, set=1, aggregate=1, number=1),
    ],
    keys=[(["CUSTOMER_ID", "SALES_DATE", "CURRENCY_CODE"], None, {"grouped": 1, "merge": 1})],
    kind="base table",
    complete=True,
    ev={"declared": 1, "read": 2, "write": 1},
)
table(
    "MART.CUSTOMER_SEGMENTS",
    [
        col("CUSTOMER_ID", declared=1, select=1),
        col("CUSTOMER_NAME", declared=1, select=1),
        col("NET_AMOUNT_12M", "number", declared=1, select=1, aggregate=1, where=1, order_by=1, number=1),
        col("SEGMENT", "text", observed=["KEY", "STRATEGIC"], declared=1, select=2, where=2, set=1, group_by=1, text=1),
    ],
    kind="base table",
    complete=True,
    ev={"declared": 1, "read": 3, "write": 1},
)
table(
    "MART.V_KEY_CUSTOMERS",
    [
        col("CUSTOMER_ID", declared=1, select=1),
        col("CUSTOMER_NAME", declared=1, select=1),
        col("NET_AMOUNT_12M", declared=1, select=1, order_by=1),
        col("SEGMENT", declared=1),
    ],
    kind="view",
    complete=True,
    ev={"declared": 1, "read": 1},
)
# Invented cases that the corpus lacks.
table(
    "DEMO.PRICE_LIST",
    [col("PRICE_ID", select=2), col("PRICE_CODE", "text|number", select=2, where=4, text=3, number=1)],
    keys=[(["PRICE_ID"], "<S>_ID", {})],
    ev={"read": 4},
    facts={"note": "invented: two types"},
)
table(
    "DEMO.V_OPEN_TICKETS",
    [
        col("TICKET_ID", declared=1, select=3),
        col("OPENED_AT", "datetime", declared=1, select=2, datetime=1),
        col("REGION", undeclared=True, select=1, where=1),
    ],
    kind="view",
    ev={"declared": 1, "read": 3},
    facts={"contradicted": "REGION is undeclared", "note": "invented: contradicted declaration"},
)
table(
    "DEMO.DAILY_TOTALS",
    [
        col("DAY_DATE", "datetime", declared=2, select=1, datetime=1),
        col("TOTAL", "number", declared=2, select=1, number=1),
        col("CURRENCY_CODE", declared=1),
    ],
    kind="base table|view",
    ev={"declared": 2, "read": 1},
    facts={
        "ambiguity": "two declarations differ: base table (1) or view (1); CURRENCY_CODE declared once",
        "note": "invented: two declarations",
    },
)

RELATIONSHIPS = [
    # (left table, left cols, op, right table, right cols, join count, extra fact)
    ("SALES.ORDERS", "CUSTOMER_ID", ">?", "SALES.CUSTOMERS", "CUSTOMER_ID", 6, None),
    ("SALES.ORDER_LINES", "ORDER_ID", ">?", "SALES.ORDERS", "ORDER_ID", 7, None),
    ("SALES.ORDER_LINES", "PRODUCT_ID", ">?", "INV.PRODUCTS", "PRODUCT_ID", 4, None),
    ("SALES.ORDER_PROMOTIONS", "ORDER_ID", ">?", "SALES.ORDERS", "ORDER_ID", 1, None),
    ("SALES.ORDER_PROMOTIONS", "PROMO_ID", "?<>?", "SALES.PROMOTIONS", "PROMO_ID", 1, None),
    ("HR.EMPLOYEES", "MANAGER_ID", ">?", "HR.EMPLOYEES", "EMPLOYEE_ID", 2, None),
    ("INV.STOCK_LEVELS", "WAREHOUSE_ID", ">?", "INV.WAREHOUSES", "ID", 2, None),
    ("INV.STOCK_LEVELS", "PRODUCT_ID", ">?", "INV.PRODUCTS", "PRODUCT_ID", 1, None),
    ("INV.SHIPMENT_LINES", ["ORDER_ID", "LINE_NO"], "?<>?", "SALES.ORDER_LINES", ["ORDER_ID", "LINE_NO"], 1, None),
    (
        "SALES.ORDER_LINES",
        "PRODUCT_ID",
        "?<>?",
        "INV.STOCK_LEVELS",
        "PRODUCT_ID",
        1,
        "shared reference to INV.PRODUCTS.PRODUCT_ID",
    ),
    ("ORDERS", "CUSTOMER_ID", ">?", "CUSTOMERS", "CUSTOMER_ID", 1, None),
    ("MART.CUSTOMER_DAILY_SALES", "CUSTOMER_ID", ">?", "SALES.CUSTOMERS", "CUSTOMER_ID", 1, None),
    (
        "MART.ORDER_LINE_FACTS",
        ["CUSTOMER_ID", "SALES_DATE", "CURRENCY_CODE"],
        ">?",
        "MART.CUSTOMER_DAILY_SALES",
        ["CUSTOMER_ID", "SALES_DATE", "CURRENCY_CODE"],
        1,
        None,
    ),
]

# --- lineage slice: from the answer key -----------------------------------------------------

LINEAGE_FILES = {"016", "024", "038", "045", "046", "047", "048", "049", "051", "052", "054", "055"}
MULTI_QUERY_FILES = {"038", "057"}
UNQUALIFIED_016 = {"ORDER_ID", "ORDER_DATE", "CUSTOMER_NAME", "CREDIT_LIMIT", "ORDER_TOTAL"}

REPORTS = {
    # report name: [(output column, type, {fact: text})]
    "016_unqualified_columns_in_join": [
        (c, None, {"ambiguity": f"upstream SALES.ORDERS.{c} ({n_o}) or SALES.CUSTOMERS.{c} ({n_c})"})
        for c, n_o, n_c in [("ORDER_ID", 14, 0), ("ORDER_DATE", 9, 0), ("CUSTOMER_NAME", 0, 9), ("CREDIT_LIMIT", 0, 0)]
    ],
    "038_daily_reports#1": [("NEW_ORDERS", "number", {})],
    "038_daily_reports#2": [("NEW_CUSTOMERS", "number", {})],
    "054_segment_summary": [("SEGMENT", None, {}), ("CUSTOMER_COUNT", "number", {}), ("NET_AMOUNT", "number", {})],
    "055_key_customers": [("CUSTOMER_ID", None, {}), ("CUSTOMER_NAME", None, {}), ("NET_AMOUNT_12M", None, {})],
    # Invented: a report in a folder, second query in its file, with unaliased and repeated names.
    "demo/unaliased_columns#2": [
        ("ORDER_ID", None, {}),
        ("ORDER_ID (2)", None, {}),
        ("COUNT(*)", "number", {}),
        ("NVL(O.SALES_REP_ID,-1)", "number", {}),
    ],
}
REPORT_FACTS = {
    "016_unqualified_columns_in_join": {
        "ambiguity": "filter on ORDER_TOTAL and CREDIT_LIMIT: SALES.ORDERS or SALES.CUSTOMERS"
    },
    "demo/unaliased_columns#2": {"note": "invented: unaliased and repeated output names"},
}
DEMO_DEPS = [
    (("SALES.ORDERS", "ORDER_ID"), ("report.demo/unaliased_columns#2", "ORDER_ID"), "IDENTITY"),
    (("SALES.ORDER_LINES", "ORDER_ID"), ("report.demo/unaliased_columns#2", "ORDER_ID (2)"), "IDENTITY"),
    (("SALES.ORDER_LINES", None), ("report.demo/unaliased_columns#2", "COUNT(*)"), "AGGREGATION"),
    (("SALES.ORDERS", "SALES_REP_ID"), ("report.demo/unaliased_columns#2", "NVL(O.SALES_REP_ID,-1)"), "TRANSFORMATION"),
    (("SALES.ORDER_LINES", "ORDER_ID"), ("report.demo/unaliased_columns#2", None), "JOIN"),
    (("SALES.ORDERS", "ORDER_ID"), ("report.demo/unaliased_columns#2", None), "JOIN"),
]
SUBTYPE_ORDER = ["IDENTITY", "TRANSFORMATION", "AGGREGATION", "JOIN", "FILTER", "GROUP_BY", "SORT", "WINDOW", "CONDITIONAL"]


def load_lineage():
    deps = defaultdict(lambda: defaultdict(set))  # (up, down) -> subtype -> {query}
    with (CORPUS / "answer_key" / "lineage.csv").open() as f:
        for row in csv.DictReader(f):
            prefix = row["file"][:3]
            if prefix not in LINEAGE_FILES:
                continue
            if prefix == "016" and row["upstream_column"] in UNQUALIFIED_016:
                continue
            query = (row["file"], row["statement"])
            if row["downstream_table"]:
                down_table = row["downstream_table"]
            else:
                stem = row["file"].removesuffix(".sql")
                if prefix in MULTI_QUERY_FILES:
                    stem += f"#{row['statement']}"
                down_table = f"report.{stem}"
            up = (row["upstream_table"], row["upstream_column"] or None)
            down = (down_table, row["downstream_column"] or None)
            deps[up, down][row["subtype"]].add(query)
    for up, down, subtype in DEMO_DEPS:
        deps[up, down][subtype].add(("demo/unaliased_columns.sql", "2"))
    return deps


def split_table(table):
    """Split `report.a/b#2` and `SALES.ORDERS` into owner and name."""
    owner, _, rest = table.partition(".")
    return owner, rest


def end(table, column):
    owner, rest = split_table(table)
    t = f"{name(owner)}.{name(rest)}"
    return t if column is None else f"{t}.{name(column)}"


def check_end(table, column):
    if table.startswith("report."):
        rep = table.removeprefix("report.")
        assert rep in REPORTS, rep
        assert column is None or column in [c for c, _, _ in REPORTS[rep]], (table, column)
    else:
        assert table in TABLES, table
        assert column is None or column in TABLES[table]["cols"], (table, column)


# --- rendering ------------------------------------------------------------------------------


def evidence(variant, native, counts, facts):
    """Return (settings list, trailing comment) for one element in one variant."""
    counts = {k: v for k, v in counts.items() if v}
    if variant == "A":
        settings = native + [f"{k}: {v}" for k, v in counts.items()] + [f"{k}: {lit(v)}" for k, v in facts.items()]
        return settings, ""
    text = ", ".join(f"{k} {v}" for k, v in counts.items())
    fact_text = "; ".join(f"{k}: {v}" for k, v in facts.items())
    text = "; ".join(t for t in [text, fact_text] if t)
    if variant == "B":
        return native + ([f"note: {lit(text)}"] if text else []), ""
    return native, f" // {text}" if text else ""


def bracket(settings):
    return f" [{', '.join(settings)}]" if settings else ""


def column_line(variant, c, extra_facts=None):
    typ = c["type"] or "unknown"
    typ = name(typ) if "|" not in typ else f'"{typ}"'
    native = ["null"] if c["nullable"] else []
    counts = {"declared": c["declared"], **c["ev"]}
    if c["nullable"]:
        counts["nullable"] = c["nullable"]
    facts = {}
    if c["undeclared"]:
        native.append("undeclared: true")
    if c["observed"]:
        facts["observed"] = ", ".join(c["observed"])
    facts.update(c["facts"])
    facts.update(extra_facts or {})
    settings, comment = evidence(variant, native, counts, facts)
    return f"  {name(c['name'])} {typ}{bracket(settings)}{comment}"


def key_text(cols, pattern, ev):
    parts = ([f"name match {pattern}"] if pattern else []) + [f"{k} {v}" for k, v in ev.items()]
    return ", ".join(parts)


def table_header(variant, t, info):
    native = []
    if info["kind"]:
        native.append(f"kind: {lit(info['kind'])}")
    if info["complete"]:
        native.append("complete: true")
    facts = dict(info["facts"])
    # dbdiagram shows no index note, so A and B put key evidence on the table, where its hover card shows it.
    if info["keys"] and variant != "C":
        facts["keys"] = "; ".join(
            f"{cols[0] if len(cols) == 1 else '(' + ', '.join(cols) + ')'}: {key_text(cols, p, ev)}"
            for cols, p, ev in info["keys"]
        )
    settings, comment = evidence(variant, native, info["ev"], facts)
    return f"Table {tname(t)}{bracket(settings)} {{{comment}"


def key_line(variant, cols, pattern, ev):
    target = name(cols[0]) if len(cols) == 1 else f"({', '.join(name(c) for c in cols)})"
    if variant == "C":
        return f"    {target} [unique] // {key_text(cols, pattern, ev)}"
    return f"    {target} [unique]"


def write_schema(variant):
    out = []
    for t in sorted(TABLES, key=lambda t: (t.startswith("DEMO."), t.count(".") == 0, t)):
        info = TABLES[t]
        out.append(table_header(variant, t, info))
        out.extend(column_line(variant, c) for c in info["cols"].values())
        if info["keys"]:
            out.append("")
            out.append("  indexes {")
            out.extend(key_line(variant, cols, pattern, ev) for cols, pattern, ev in info["keys"])
            out.append("  }")
        out.append("}")
        out.append("")
    for lt, lc, op, rt, rc, joins, fact in RELATIONSHIPS:
        text = f"join {joins}" + (f", {fact}" if fact else "")
        if variant == "C":
            out.append(f"Ref: {cref(lt, lc)} {op} {cref(rt, rc)} // {text}")
        else:
            out.append(f'Ref "{esc(text)}": {cref(lt, lc)} {op} {cref(rt, rc)}')
    return "\n".join(out) + "\n"


def write_lineage(variant, deps):
    out = []
    for rep, cols in REPORTS.items():
        native = ["kind: 'report'"]
        settings, comment = evidence(variant, native, {}, REPORT_FACTS.get(rep, {}))
        out.append(f"Table report.{name(rep)}{bracket(settings)} {{{comment}")
        for c, typ, facts in cols:
            out.append(column_line(variant, col(c, typ), facts))
        out.append("}")
        out.append("")

    selfdeps = {}
    edges = {}
    rollup = defaultdict(set)
    for (up, down), by_sub in deps.items():
        check_end(*up)
        check_end(*down)
        queries = set().union(*by_sub.values())
        rollup[up[0], down[0]] |= queries
        counts = {s.lower(): len(by_sub[s]) for s in SUBTYPE_ORDER if s in by_sub}
        if up == down:
            selfdeps[up] = counts
        else:
            edges[up, down] = counts

    if selfdeps:
        where = "a comment" if variant == "C" else "a column property"
        out.append(f"// DBML raises on a column that depends on itself, so each self-dependency is {where}.")
        for (t, c), counts in sorted(selfdeps.items()):
            text = ", ".join(f"{k.upper()} {v}" for k, v in counts.items())
            if variant == "C":
                out.append(f"// self-dependency: {end(t, c)} {text}")
            else:
                key = "self_dependency" if variant == "A" else "note"
                text = text if variant == "A" else f"self-dependency: {text}"
                out.append(f"Metadata Column {end(t, c)} {{\n  {key}: {lit(text)}\n}}")
        out.append("")

    downstreams = sorted({d for _, d in rollup}, key=lambda d: (d.startswith("report."), d))
    for d in downstreams:
        out.append(f"// {d}")
        for (ut, dt), queries in sorted(rollup.items()):
            if dt != d:
                continue
            settings, comment = evidence(variant, [], {"queries": len(queries)}, {})
            out.append(f"Dep: {end(ut, None)} -> {end(dt, None)}{bracket(settings)}{comment}")
        for (up, down), counts in sorted(edges.items(), key=lambda e: (e[0][1][1] or "", e[0][0])):
            if down[0] != d or (up[1] is None and down[1] is None):
                continue
            if variant == "A":
                settings, comment = list(map(lambda kv: f"{kv[0]}: {kv[1]}", counts.items())), ""
            else:
                text = ", ".join(f"{k.upper()} {v}" for k, v in counts.items())
                settings, comment = ([f"note: {lit(text)}"], "") if variant == "B" else ([], f" // {text}")
            out.append(f"Dep: {end(*up)} -> {end(*down)}{bracket(settings)}{comment}")
        out.append("")
    return "\n".join(out)


PROJECT = """Project ichnos {
  database_type: 'Oracle'
  Note: '''
  Inferred by ichnos from 58 queries, with no database connection.
  Counts are distinct queries. ichnos never claims a primary key: each key is a unique index.
  `unknown` means no type evidence, and `text|number` means two types, an ambiguity.
  `null` claims nullable. A column with no setting has no nullable claim.
  `>?` means the many side refers to a key. `?<>?` means the direction is unknown.
  The schema `report` holds reports. Its tables are queries, not tables.
  '''
}
"""


def main():
    deps = load_lineage()
    for folder, variant in VARIANTS.items():
        out = HERE / "out" / folder
        out.mkdir(parents=True, exist_ok=True)
        schema = PROJECT + "\n" + write_schema(variant)
        lineage = write_lineage(variant, deps)
        (out / "schema.dbml").write_text(schema)
        (out / "lineage.dbml").write_text("use * from './schema.dbml'\n\n" + lineage)
        (out / "combined.dbml").write_text(schema + "\n" + lineage)


if __name__ == "__main__":
    main()
