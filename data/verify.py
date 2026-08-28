"""
Smoke test for the generated data.

Two questions, both of which must be yes before any analytics is worth writing:

  1. Does the KPI tree reconcile?  (if not, every decomposition downstream is wrong)
  2. Is each planted effect actually visible in the data?
     (if not, "the engine found it" proves nothing)

    python data/verify.py
"""

from __future__ import annotations

import pathlib

import duckdb
import yaml

ROOT = pathlib.Path(__file__).resolve().parent
RAW = ROOT / "raw"

SALES = f"read_parquet('{RAW / 'sales.parquet'}')"
TRAFFIC = f"read_parquet('{RAW / 'traffic.parquet'}')"
INVENTORY = f"read_parquet('{RAW / 'inventory_daily.parquet'}')"
MARKETING = f"read_parquet('{RAW / 'marketing_weekly.parquet'}')"

con = duckdb.connect()
ok = True


def check(label: str, passed: bool, detail: str = "") -> None:
    global ok
    ok &= passed
    print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    if detail:
        print(f"         {detail}")


def rule(title: str) -> None:
    print(f"\n{title}\n{'-' * len(title)}")


# ------------------------------------------------------------ reconciliation --

rule("1. Does the KPI tree reconcile?")

row = con.sql(f"""
    SELECT
        sum(gross_revenue)                        AS gross,
        sum(returns_value)                        AS returns,
        sum(net_revenue)                          AS net,
        sum(gross_revenue - returns_value)        AS net_recomputed
    FROM {SALES}
""").fetchone()
gross, returns, net, net_recomputed = row
check(
    "net revenue = gross - returns",
    abs(net - net_recomputed) < 1.0,
    f"net {net:,.0f}  vs recomputed {net_recomputed:,.0f}",
)

row = con.sql(f"""
    WITH s AS (SELECT date, region, channel, sum(net_revenue) rev FROM {SALES}
               GROUP BY 1,2,3),
         t AS (SELECT date, region, channel, orders FROM {TRAFFIC})
    SELECT sum(s.rev) / sum(t.orders) AS aov, sum(t.orders) AS orders
    FROM s JOIN t USING (date, region, channel)
""").fetchone()
aov, orders = row
check(
    "orders join cleanly to revenue, AOV plausible",
    15 < aov < 90,
    f"AOV {aov:,.2f} over {orders:,} orders",
)

n_orphan = con.sql(f"""
    SELECT count(*) FROM (SELECT DISTINCT date, region, channel FROM {SALES}) s
    ANTI JOIN {TRAFFIC} t USING (date, region, channel)
""").fetchone()[0]
check("no sales rows without a traffic row", n_orphan == 0, f"{n_orphan} orphans")


# ------------------------------------------------------------ focal movement --

rule("2. Is there a visible movement in the focal week?")

print(con.sql(f"""
    SELECT
        strftime(date_trunc('week', date), '%Y-W%V')  AS iso_week,
        round(sum(net_revenue) / 1000, 1)             AS net_rev_k,
        round(avg(discount_pct) * 100, 1)             AS disc_pct
    FROM {SALES}
    WHERE date >= DATE '2026-06-22' AND date < DATE '2026-08-17'
    GROUP BY 1 ORDER BY 1
""").to_df().to_string(index=False))

row = con.sql(f"""
    WITH wk AS (
        SELECT date_trunc('week', date) w, sum(net_revenue) rev
        FROM {SALES} WHERE date < DATE '2026-08-17' GROUP BY 1
    ),
    base AS (SELECT avg(rev) b FROM wk WHERE w BETWEEN DATE '2026-06-01' AND DATE '2026-07-13')
    SELECT (SELECT rev FROM wk WHERE w = DATE '2026-08-03') AS focal, b FROM base
""").fetchone()
focal, base = row
delta_pct = (focal - base) / base * 100
check(
    "focal week is materially below the pre-period",
    delta_pct < -4,
    f"W32 {focal:,.0f} vs baseline {base:,.0f}  ->  {delta_pct:+.1f}%",
)


# ---------------------------------------------------------- planted effects --

rule("3. Is each planted effect visible?")

# DISCOUNT_HG_DE_FR
before, during = con.sql(f"""
    SELECT
        avg(CASE WHEN date < DATE '2026-07-20' THEN discount_pct END) * 100,
        avg(CASE WHEN date >= DATE '2026-07-20' THEN discount_pct END) * 100
    FROM {SALES}
    WHERE region IN ('DE','FR') AND category = 'Home & Garden'
      AND date >= DATE '2026-06-01'
""").fetchone()
check(
    "DISCOUNT_HG_DE_FR — discount depth stepped up",
    during - before > 12,
    f"{before:.1f}% -> {during:.1f}% on Home & Garden in DE/FR",
)

# STOCKOUT_ELEC_NL
before, during = con.sql(f"""
    SELECT
        avg(CASE WHEN date <  DATE '2026-07-27' THEN units END),
        avg(CASE WHEN date >= DATE '2026-07-27' AND date <= DATE '2026-08-16' THEN units END)
    FROM {SALES}
    WHERE region = 'NL' AND sku = 'ELEC-002' AND date >= DATE '2026-06-01'
""").fetchone()
check(
    "STOCKOUT_ELEC_NL — units collapsed",
    during < before * 0.55,
    f"{before:.1f} -> {during:.1f} units/day  ({during/before-1:+.0%})",
)

fill = con.sql(f"""
    SELECT avg(fill_rate) FROM {INVENTORY}
    WHERE region = 'NL' AND sku = 'ELEC-002'
      AND date BETWEEN DATE '2026-07-27' AND DATE '2026-08-16'
""").fetchone()[0]
check("  ...and the ops source records it", fill < 0.45, f"fill rate {fill:.2f}")

# COMPETITOR_DE
de, others = con.sql(f"""
    SELECT
        avg(CASE WHEN region = 'DE' THEN orders::DOUBLE / sessions END),
        avg(CASE WHEN region <> 'DE' THEN orders::DOUBLE / sessions END)
    FROM {TRAFFIC} WHERE date >= DATE '2026-07-20'
""").fetchone()
check(
    "COMPETITOR_DE — DE conversion diverges from the control regions",
    de < others * 0.95,
    f"DE {de:.4f} vs rest {others:.4f}  ({de/others-1:+.1%})",
)

# MIX_SHIFT_BEAUTY
before, during = con.sql(f"""
    WITH u AS (
        SELECT date, category, sum(units) units FROM {SALES}
        WHERE date >= DATE '2026-06-01' GROUP BY 1,2
    ), s AS (
        SELECT date, sum(units) tot FROM u GROUP BY 1
    )
    SELECT
        avg(CASE WHEN u.date <  DATE '2026-07-13' THEN u.units / s.tot END) * 100,
        avg(CASE WHEN u.date >= DATE '2026-07-13' THEN u.units / s.tot END) * 100
    FROM u JOIN s USING (date) WHERE u.category = 'Beauty'
""").fetchone()
check(
    "MIX_SHIFT_BEAUTY — basket tilted toward Beauty",
    during - before > 2,
    f"Beauty unit share {before:.1f}% -> {during:.1f}%",
)

spend = con.sql(f"""
    SELECT sum(spend) FROM {MARKETING} WHERE campaign = 'beauty_summer_push'
""").fetchone()[0]
check("  ...and the campaign appears in marketing spend", spend > 0, f"{spend:,.0f} total spend")

# NEW_LAUNCH_HOME
first_sale, weeks = con.sql(f"""
    SELECT min(date), count(DISTINCT date_trunc('week', date))
    FROM {SALES} WHERE sku = 'HOME-NEW-01'
""").fetchone()
check(
    "NEW_LAUNCH_HOME — sparse history, too short for a seasonal baseline",
    weeks < 12,
    f"first sale {first_sale.date()}, only {weeks} weeks of history",
)


# ------------------------------------------------------------------ grains --

rule("4. Do the sources actually disagree on grain and freshness?")

sales_max, inv_max = con.sql(f"""
    SELECT (SELECT max(date) FROM {SALES}), (SELECT max(date) FROM {INVENTORY})
""").fetchone()
lag = (sales_max - inv_max).days
check("inventory lags sales", lag == 2, f"sales to {sales_max.date()}, inventory to {inv_max.date()} ({lag}d)")

mk_grain = con.sql(f"SELECT count(DISTINCT week_start) FROM {MARKETING}").fetchone()[0]
sl_grain = con.sql(f"SELECT count(DISTINCT date) FROM {SALES}").fetchone()[0]
check(
    "marketing is weekly, sales is daily",
    sl_grain > mk_grain * 6,
    f"{sl_grain} sales days vs {mk_grain} marketing weeks",
)


# ------------------------------------------------------------------ verdict --

gt = yaml.safe_load((ROOT / "ground_truth.yaml").read_text())
print(f"\n{'=' * 60}")
print("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED")
print(f"{len(gt['effects'])} planted effects on record  |  focal week {gt['focal_week']}")
raise SystemExit(0 if ok else 1)
