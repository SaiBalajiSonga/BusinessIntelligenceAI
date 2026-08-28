"""
DuckDB warehouse — loading, grain reconciliation, freshness.

This layer does the SQL work only: filter, join, aggregate, slice. None of the
five analytical rungs run here. It produces the aggregates that the analytics
layer does the maths on.

    python -m engine.warehouse          # rebuild and print the freshness manifest
"""

from __future__ import annotations

import pathlib

import duckdb
import pandas as pd

from engine.contract import Contract, load

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "warehouse" / "bi.duckdb"

# ISO year-week, e.g. 2026-W32. Built explicitly rather than via strftime so
# the year is the ISO year, which diverges from the calendar year in late Dec.
ISO_WEEK = (
    "(date_part('isoyear', date)::VARCHAR || '-W' || "
    "lpad(date_part('week', date)::VARCHAR, 2, '0'))"
)

# contract `view:` name -> physical view
VIEWS = {
    "week_rcs": "v_week_rcs",
    "week_rc": "v_week_rc",
    "week_inventory": "v_week_inventory",
    "week_marketing": "v_week_marketing",
}


def connect(rebuild: bool = False, contract: Contract | None = None) -> duckdb.DuckDBPyConnection:
    """
    Open the warehouse read-only once it is built.

    DuckDB allows one writer and no concurrent readers alongside it. Holding a
    read-write handle meant a running API server locked the file and the test
    suite could not open it at all. The warehouse is immutable analytical data
    after the build, so read-only is both the honest mode and the one that lets
    a server, a notebook and the tests share it. Only building takes the write
    lock, and feedback lives in its own file precisely so nothing else needs one.
    """
    contract = contract or load()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if rebuild and DB_PATH.exists():
        DB_PATH.unlink()

    if DB_PATH.exists():
        try:
            handle = duckdb.connect(str(DB_PATH), read_only=True)
            if _is_built(handle):
                return handle
            handle.close()
        except duckdb.Error:
            pass        # not built yet, or a writer holds it — fall through

    con = duckdb.connect(str(DB_PATH))
    if not _is_built(con):
        _build(con, contract)
    return con


def _is_built(con: duckdb.DuckDBPyConnection) -> bool:
    got = {r[0] for r in con.sql("SHOW TABLES").fetchall()}
    return {"fct_sales", "v_week_rc", "v_week_rcs"} <= got


# ------------------------------------------------------------------ build --

def _build(con: duckdb.DuckDBPyConnection, contract: Contract) -> None:
    src = contract.sources

    for name, table in [
        ("sales", "fct_sales"),
        ("traffic", "fct_traffic"),
        ("marketing", "fct_marketing_weekly"),
        ("inventory", "fct_inventory"),
    ]:
        path = ROOT / src[name]["path"]
        if not path.exists():
            raise FileNotFoundError(f"{path} missing — run `python data/generate.py` first")
        con.execute(f"CREATE OR REPLACE TABLE {table} AS SELECT * FROM read_parquet('{path}')")

    # --- weekly sales at full grain: region x channel x category x sku -----
    con.execute(f"""
        CREATE OR REPLACE VIEW v_week_rcs AS
        SELECT
            {ISO_WEEK}                  AS iso_week,
            date_trunc('week', date)    AS week_start,
            region, channel, category, sku,
            sum(units)                  AS units,
            sum(gross_revenue)          AS gross_revenue,
            sum(returns_value)          AS returns_value,
            sum(net_revenue)            AS net_revenue,
            sum(cogs)                   AS cogs,
            sum(units * discount_pct) / nullif(sum(units), 0) AS discount_pct,
            sum(net_revenue) / nullif(sum(units), 0)          AS asp
        FROM fct_sales
        GROUP BY ALL
    """)

    # --- weekly sales + traffic at region x channel -----------------------
    # Sessions have no SKU, so anything conversion-shaped lives at this grain.
    # Joining here rather than fanning traffic out to SKU is what stops
    # sessions being counted 21 times.
    con.execute(f"""
        CREATE OR REPLACE VIEW v_week_rc AS
        WITH s AS (
            SELECT
                {ISO_WEEK} AS iso_week, date_trunc('week', date) AS week_start,
                region, channel,
                sum(units) units, sum(net_revenue) net_revenue, sum(cogs) cogs,
                sum(gross_revenue) gross_revenue, sum(returns_value) returns_value
            FROM fct_sales GROUP BY ALL
        ), t AS (
            SELECT
                {ISO_WEEK} AS iso_week, date_trunc('week', date) AS week_start,
                region, channel,
                sum(sessions) sessions, sum(orders) orders
            FROM fct_traffic GROUP BY ALL
        )
        SELECT s.*, t.sessions, t.orders
        FROM s JOIN t USING (iso_week, week_start, region, channel)
    """)

    con.execute(f"""
        CREATE OR REPLACE VIEW v_week_inventory AS
        SELECT
            {ISO_WEEK} AS iso_week, date_trunc('week', date) AS week_start,
            region, sku,
            avg(fill_rate) AS fill_rate,
            sum(stock_on_hand) AS stock_on_hand,
            avg(days_of_cover) AS days_of_cover
        FROM fct_inventory GROUP BY ALL
    """)

    # --- marketing: already weekly, so no allocation needed at this grain --
    con.execute("""
        CREATE OR REPLACE VIEW v_week_marketing AS
        SELECT iso_week, week_start, region, channel, campaign, sum(spend) AS spend
        FROM fct_marketing_weekly GROUP BY ALL
    """)

    # --- marketing allocated to days -------------------------------------
    # The reconciliation the contract declares: weekly spend spread evenly over
    # its 7 days. A stated rule, not a measurement — anything derived from this
    # view is tagged `allocated` in the evidence.
    con.execute("""
        CREATE OR REPLACE VIEW v_marketing_daily AS
        SELECT
            (week_start + INTERVAL (n) DAY)::DATE AS date,
            region, channel, campaign,
            spend / 7.0 AS spend_allocated,
            TRUE        AS is_allocated
        FROM fct_marketing_weekly
        CROSS JOIN range(0, 7) AS r(n)
    """)


# -------------------------------------------------------------- freshness --

def freshness(con: duckdb.DuckDBPyConnection, contract: Contract | None = None) -> pd.DataFrame:
    """Per-source staleness against the contract's as_of. Feeds the confidence score."""
    contract = contract or load()
    as_of = pd.Timestamp(contract.as_of)

    probes = {
        "sales": ("fct_sales", "date"),
        "traffic": ("fct_traffic", "date"),
        "marketing": ("fct_marketing_weekly", "week_start"),
        "inventory": ("fct_inventory", "date"),
    }

    rows = []
    for source_id, (table, col) in probes.items():
        spec = contract.source(source_id)
        max_dt = con.sql(f"SELECT max({col}) FROM {table}").fetchone()[0]
        max_dt = pd.Timestamp(max_dt)
        lag_h = (as_of - max_dt).total_seconds() / 3600
        sla_h = float(spec["sla_hours"])

        # a weekly source is only 'late' once the week it covers has closed
        if spec.get("coarser_than_analysis"):
            lag_h = max(0.0, lag_h - 7 * 24)

        rows.append({
            "source": source_id,
            "governance": spec.get("governance", "unknown"),
            "latest_data": max_dt.date(),
            "lag_hours": round(lag_h, 1),
            "sla_hours": sla_h,
            "status": "fresh" if lag_h <= sla_h else "stale",
            "note": spec.get("reconciliation", ""),
        })

    df = pd.DataFrame(rows)
    df["freshness_score"] = (1.0 - (df["lag_hours"] / (df["sla_hours"] * 4))).clip(0.0, 1.0)
    return df


def view_for(contract: Contract, kpi_id: str) -> str:
    return VIEWS[contract.kpi(kpi_id)["view"]]


def view_named(name: str) -> str:
    return VIEWS[name]


# Which dimensions each view can actually be sliced by. A scope discovered on
# one view (the drill works at SKU grain) is not automatically valid on another
# — marketing spend has no SKU, and asking for one is a binder error rather
# than an empty result.
VIEW_DIMENSIONS = {
    "week_rcs": {"region", "channel", "category", "sku"},
    "week_rc": {"region", "channel"},
    "week_inventory": {"region", "sku"},
    "week_marketing": {"region", "channel", "campaign"},
}


def narrow_scope(view_name: str, scope: dict | None) -> dict | None:
    """Keep only the parts of a scope this view can honour."""
    if not scope:
        return None
    allowed = VIEW_DIMENSIONS.get(view_name, set())
    kept = {k: v for k, v in scope.items() if k in allowed}
    return kept or None


# ------------------------------------------------------------- series SQL --

def where_clause(filters: dict | None) -> str:
    """Entitlement and slice filters. Applied in SQL, so they shape what is
    computed rather than what is displayed."""
    if not filters:
        return ""
    parts = []
    for col, val in filters.items():
        if isinstance(val, (list, tuple, set)):
            vals = ", ".join(f"'{v}'" for v in val)
            parts.append(f"{col} IN ({vals})")
        else:
            parts.append(f"{col} = '{val}'")
    return "WHERE " + " AND ".join(parts)


def series(con, view: str, expr: str, filters: dict | None = None) -> pd.DataFrame:
    """Weekly series for an arbitrary contract expression over a view."""
    sql = f"""
        SELECT iso_week, min(week_start) AS week_start, {expr} AS value
        FROM {view}
        {where_clause(filters)}
        GROUP BY iso_week
        HAVING {expr} IS NOT NULL
        ORDER BY min(week_start)
    """
    return con.sql(sql).to_df()


if __name__ == "__main__":
    contract = load()
    con = connect(rebuild=True, contract=contract)

    print("tables and views")
    print("----------------")
    for (name,) in con.sql("SHOW TABLES").fetchall():
        n = con.sql(f"SELECT count(*) FROM {name}").fetchone()[0]
        print(f"  {name:24} {n:>9,} rows")

    print(f"\nfreshness manifest  (as_of {contract.as_of})")
    print("-------------------------------------------")
    print(freshness(con, contract).to_string(index=False))
