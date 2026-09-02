"""
Synthetic retail data with planted causes.

Three source systems at different grains, plus a ground-truth file recording
exactly what was injected. The engine is judged on whether it recovers these
effects — without the ground truth, every downstream number is unfalsifiable.

Generation is top-down:

    sessions -> conversion -> orders -> units -> revenue

so the KPI tree (Net Revenue = Orders x AOV - Returns) reconciles by
construction rather than by coincidence.

    python data/generate.py
"""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd
import yaml

from engine.paths import writable_root

SEED = 20260828
RNG = np.random.default_rng(SEED)

# Writes go through writable_root(), not a path relative to this file --
# engine/warehouse.py resolves `data/raw/<name>.parquet` from the same root
# when it decides this needs (re)generating, and the two have to agree on
# where that lands. Locally that's just the repo root, unchanged from before.
ROOT = writable_root() / "data"
RAW = ROOT / "raw"

# ---------------------------------------------------------------- calendar --

START = pd.Timestamp("2023-09-04")   # a Monday — 3 seasonal cycles, so STL(period=52) is valid
END = pd.Timestamp("2026-08-23")     # a Sunday
FOCAL_WEEK = "2026-W32"              # the week the demo interrogates

# ---------------------------------------------------------------- universe --

REGIONS = {"DE": 1.00, "UK": 1.10, "FR": 0.80, "ES": 0.60, "NL": 0.45}
CHANNELS = {"web": 1.00, "mobile_app": 0.85, "marketplace": 0.50}

# sku -> (category, list_price, unit_cost, base mix weight)
SKUS: dict[str, tuple[str, float, float, float]] = {
    "HOME-001": ("Home & Garden", 42.00, 24.40, 0.070),
    "HOME-002": ("Home & Garden", 28.50, 16.90, 0.085),
    "HOME-003": ("Home & Garden", 65.00, 39.00, 0.040),
    "HOME-004": ("Home & Garden", 19.90, 11.20, 0.075),
    "HOME-005": ("Home & Garden", 34.00, 20.10, 0.055),
    "ELEC-001": ("Electronics", 89.00, 61.00, 0.045),
    "ELEC-002": ("Electronics", 129.00, 88.00, 0.050),
    "ELEC-003": ("Electronics", 54.00, 36.50, 0.055),
    "ELEC-004": ("Electronics", 199.00, 141.00, 0.025),
    "ELEC-005": ("Electronics", 39.00, 25.80, 0.060),
    "APPL-001": ("Apparel", 24.00, 10.60, 0.090),
    "APPL-002": ("Apparel", 45.00, 19.80, 0.060),
    "APPL-003": ("Apparel", 15.50, 6.70, 0.085),
    "APPL-004": ("Apparel", 59.00, 26.10, 0.040),
    "APPL-005": ("Apparel", 32.00, 14.10, 0.065),
    "BEAU-001": ("Beauty", 18.00, 7.20, 0.070),
    "BEAU-002": ("Beauty", 12.50, 4.90, 0.075),
    "BEAU-003": ("Beauty", 26.00, 10.80, 0.045),
    "BEAU-004": ("Beauty", 9.90, 3.80, 0.055),
    "BEAU-005": ("Beauty", 33.00, 13.90, 0.030),
    "HOME-NEW-01": ("Home & Garden", 47.00, 27.90, 0.025),  # launches mid-2026
}

BASE_SESSIONS = 40_000
BASE_CONV = 0.0280
BASE_UNITS_PER_ORDER = 2.30
BASE_DISCOUNT = 0.075
RETURN_RATE = {"Home & Garden": 0.055, "Electronics": 0.085, "Apparel": 0.140, "Beauty": 0.040}

# ------------------------------------------------------- the planted causes --
#
# Every window below is inclusive. These definitions are the single source of
# truth: the generator applies them and ground_truth.yaml is written from the
# same dict, so the two can never drift apart.

EFFECTS = {
    "DISCOUNT_HG_DE_FR": {
        "window": ("2026-07-20", "2026-08-23"),
        "scope": {"region": ["DE", "FR"], "category": ["Home & Garden"]},
        "mechanism": "Discount depth stepped from ~7.5% to ~26% to clear summer stock.",
        "expect": "Large negative PRICE effect in the price/volume/mix bridge, "
                  "partly offset by a positive volume effect (elasticity -0.6).",
        "detect_at": "Rung 2 (exact)",
        "params": {"discount_to": 0.26, "unit_elasticity": -0.6},
    },
    "STOCKOUT_ELEC_NL": {
        "window": ("2026-07-27", "2026-08-16"),
        "scope": {"region": ["NL"], "sku": ["ELEC-002"]},
        "mechanism": "Supplier delay; fill rate collapsed to ~0.30.",
        "expect": "Negative VOLUME effect concentrated in one small slice — should "
                  "surface via surprise ranking, not size ranking.",
        "detect_at": "Rung 3 (exact)",
        "params": {"units_multiplier": 0.30, "fill_rate": 0.30},
    },
    "COMPETITOR_DE": {
        "window": ("2026-07-20", "2026-08-23"),
        "scope": {"region": ["DE"]},
        "mechanism": "Competitor price cut in DE depressed conversion by ~12%.",
        "expect": "Conversion-rate driver. Not derivable from the KPI tree — needs "
                  "a control group (FR/ES/NL) to estimate.",
        "detect_at": "Rung 4 (assumption-bearing)",
        "params": {"conversion_multiplier": 0.88},
    },
    "MIX_SHIFT_BEAUTY": {
        "window": ("2026-07-13", "2026-08-23"),
        "scope": {"category": ["Beauty"]},
        "mechanism": "Paid campaign pushed entry-price Beauty lines; basket mix "
                     "tilted toward cheaper SKUs.",
        "expect": "Negative MIX effect on AOV while unit volume holds — the case "
                  "that is invisible without a PVM bridge.",
        "detect_at": "Rung 2 (exact)",
        "params": {"category_mix_boost": 1.35, "cheap_sku_boost": 1.60},
    },
    "NEW_LAUNCH_HOME": {
        "window": ("2026-07-06", "2026-08-23"),
        "scope": {"sku": ["HOME-NEW-01"]},
        "mechanism": "New SKU launched with no prior history.",
        "expect": "Too few periods for an STL baseline — must fall back to peer "
                  "benchmarking and cap confidence.",
        "detect_at": "Rung 0 fallback (sparse history)",
        "params": {"launch_date": "2026-07-06"},
    },
}


def _w(key: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    a, b = EFFECTS[key]["window"]
    return pd.Timestamp(a), pd.Timestamp(b)


# ------------------------------------------------------------- base shapes --

def _annual(doy: np.ndarray) -> np.ndarray:
    """Summer dip, Q4 peak."""
    base = 1.0 + 0.16 * np.sin(2 * np.pi * (doy - 100) / 365.25)
    q4 = np.where((doy >= 315) & (doy <= 358), 0.34, 0.0)
    return base + q4


def _weekday(dow: np.ndarray) -> np.ndarray:
    return np.array([1.04, 1.02, 1.01, 1.05, 1.00, 0.88, 0.84])[dow]


def _trend(t: np.ndarray, n: int) -> np.ndarray:
    return 1.0 + 0.11 * (t / n)


# ----------------------------------------------------------------- traffic --

def build_traffic(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Sessions, conversion and orders at day x region x channel."""
    idx = pd.MultiIndex.from_product(
        [dates, REGIONS, CHANNELS], names=["date", "region", "channel"]
    )
    df = idx.to_frame(index=False)

    doy = df["date"].dt.dayofyear.to_numpy()
    dow = df["date"].dt.dayofweek.to_numpy()
    t = (df["date"] - START).dt.days.to_numpy()
    n = (END - START).days

    seasonal = _annual(doy) * _weekday(dow) * _trend(t, n)
    region_w = df["region"].map(REGIONS).to_numpy()
    channel_w = df["channel"].map(CHANNELS).to_numpy()

    sessions = BASE_SESSIONS * region_w * channel_w * seasonal
    sessions *= RNG.normal(1.0, 0.045, len(df))

    conv = BASE_CONV * (1.0 + 0.10 * np.sin(2 * np.pi * (doy - 40) / 365.25))
    conv *= RNG.normal(1.0, 0.038, len(df))

    # planted: competitor price cut suppresses DE conversion
    lo, hi = _w("COMPETITOR_DE")
    hit = (df["region"] == "DE") & df["date"].between(lo, hi)
    conv = np.where(hit, conv * EFFECTS["COMPETITOR_DE"]["params"]["conversion_multiplier"], conv)

    df["sessions"] = np.round(sessions).astype(int)
    df["conversion_rate"] = conv
    df["orders"] = np.round(df["sessions"] * conv).astype(int)
    df["units_per_order"] = BASE_UNITS_PER_ORDER * RNG.normal(1.0, 0.03, len(df))
    df["total_units"] = df["orders"] * df["units_per_order"]
    return df


# --------------------------------------------------------------- basket mix --

def build_mix(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Share of units per SKU at day x region. Normalised to 1.0 per day/region."""
    skus = list(SKUS)
    idx = pd.MultiIndex.from_product([dates, REGIONS, skus], names=["date", "region", "sku"])
    df = idx.to_frame(index=False)
    df["category"] = df["sku"].map(lambda s: SKUS[s][0])

    weight = df["sku"].map(lambda s: SKUS[s][3]).to_numpy().astype(float)
    weight *= RNG.normal(1.0, 0.05, len(df))

    # the new SKU does not exist before launch
    launch = pd.Timestamp(EFFECTS["NEW_LAUNCH_HOME"]["params"]["launch_date"])
    weight = np.where(
        (df["sku"] == "HOME-NEW-01") & (df["date"] < launch), 0.0, weight
    )
    # and ramps once it does
    ramp_days = (df["date"] - launch).dt.days.clip(lower=0, upper=42) / 42
    weight = np.where(
        df["sku"] == "HOME-NEW-01", weight * (0.25 + 0.75 * ramp_days), weight
    )

    # planted: campaign tilts the basket toward cheap Beauty lines
    p = EFFECTS["MIX_SHIFT_BEAUTY"]["params"]
    lo, hi = _w("MIX_SHIFT_BEAUTY")
    active = df["date"].between(lo, hi)
    weight = np.where(active & (df["category"] == "Beauty"), weight * p["category_mix_boost"], weight)
    weight = np.where(
        active & df["sku"].isin(["BEAU-002", "BEAU-004"]), weight * p["cheap_sku_boost"], weight
    )

    # planted: NL stockout removes most of one SKU's availability
    p = EFFECTS["STOCKOUT_ELEC_NL"]["params"]
    lo, hi = _w("STOCKOUT_ELEC_NL")
    hit = (df["region"] == "NL") & (df["sku"] == "ELEC-002") & df["date"].between(lo, hi)
    weight = np.where(hit, weight * p["units_multiplier"], weight)

    df["weight"] = weight
    df["mix_share"] = df["weight"] / df.groupby(["date", "region"])["weight"].transform("sum")
    return df[["date", "region", "sku", "category", "mix_share"]]


# ---------------------------------------------------------------- discounts --

def build_prices(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Discount depth at day x region x sku."""
    skus = list(SKUS)
    idx = pd.MultiIndex.from_product([dates, REGIONS, skus], names=["date", "region", "sku"])
    df = idx.to_frame(index=False)
    df["category"] = df["sku"].map(lambda s: SKUS[s][0])
    df["list_price"] = df["sku"].map(lambda s: SKUS[s][1])
    df["unit_cost"] = df["sku"].map(lambda s: SKUS[s][2])

    disc = np.clip(RNG.normal(BASE_DISCOUNT, 0.022, len(df)), 0.0, 0.35)

    # planted: deep clearance on Home & Garden in DE and FR
    p = EFFECTS["DISCOUNT_HG_DE_FR"]["params"]
    lo, hi = _w("DISCOUNT_HG_DE_FR")
    hit = (
        df["region"].isin(EFFECTS["DISCOUNT_HG_DE_FR"]["scope"]["region"])
        & (df["category"] == "Home & Garden")
        & df["date"].between(lo, hi)
    )
    disc = np.where(hit, np.clip(RNG.normal(p["discount_to"], 0.02, len(df)), 0.0, 0.45), disc)

    df["discount_pct"] = disc
    df["unit_price"] = df["list_price"] * (1 - disc)
    df["_promo_lift"] = np.where(hit, 1 + p["unit_elasticity"] * (BASE_DISCOUNT - disc), 1.0)
    return df


# ------------------------------------------------------------------ sources --

def build_sales(traffic: pd.DataFrame, mix: pd.DataFrame, prices: pd.DataFrame) -> pd.DataFrame:
    """Source 1 — order-line grain, daily, full history."""
    df = traffic.merge(mix, on=["date", "region"], how="left")
    df = df.merge(
        prices[["date", "region", "sku", "list_price", "unit_cost",
                "discount_pct", "unit_price", "_promo_lift"]],
        on=["date", "region", "sku"], how="left",
    )

    df["units"] = df["total_units"] * df["mix_share"] * df["_promo_lift"]
    df = df[df["units"] > 0.01].copy()
    df["units"] = np.round(df["units"], 2)

    df["gross_revenue"] = df["units"] * df["unit_price"]
    df["cogs"] = df["units"] * df["unit_cost"]
    rr = df["category"].map(RETURN_RATE).to_numpy()
    df["returns_value"] = df["gross_revenue"] * rr * RNG.normal(1.0, 0.10, len(df)).clip(0.5, 1.5)
    df["net_revenue"] = df["gross_revenue"] - df["returns_value"]

    cols = ["date", "region", "channel", "category", "sku", "units", "list_price",
            "discount_pct", "unit_price", "unit_cost", "gross_revenue",
            "returns_value", "net_revenue", "cogs"]
    return df[cols].reset_index(drop=True)


def build_traffic_source(traffic: pd.DataFrame) -> pd.DataFrame:
    """Source 1b — sessions and orders, needed for the conversion KPI."""
    return traffic[["date", "region", "channel", "sessions", "orders"]].copy()


def build_marketing(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Source 2 — WEEKLY grain. Must be allocated to days before use."""
    weeks = pd.date_range(START, END, freq="W-MON")
    campaigns = {
        "always_on_search": 1.00,
        "social_prospecting": 0.55,
        "retargeting": 0.35,
        "beauty_summer_push": 0.00,   # switched on by the planted effect
    }
    idx = pd.MultiIndex.from_product(
        [weeks, REGIONS, CHANNELS, campaigns], names=["week_start", "region", "channel", "campaign"]
    )
    df = idx.to_frame(index=False)

    base = 9_500 * df["region"].map(REGIONS) * df["channel"].map(CHANNELS)
    base = base * df["campaign"].map(campaigns) * RNG.normal(1.0, 0.09, len(df))

    lo, _ = _w("MIX_SHIFT_BEAUTY")
    push = (df["campaign"] == "beauty_summer_push") & (df["week_start"] >= lo)
    base = np.where(push, 14_000 * df["region"].map(REGIONS) * RNG.normal(1.0, 0.08, len(df)), base)

    df["spend"] = np.round(np.maximum(base, 0.0), 2)
    df["iso_week"] = (
        df["week_start"].dt.isocalendar().year.astype(str)
        + "-W" + df["week_start"].dt.isocalendar().week.astype(str).str.zfill(2)
    )
    return df[df["spend"] > 0][["iso_week", "week_start", "region", "channel", "campaign", "spend"]]


def build_inventory(dates: pd.DatetimeIndex, sales: pd.DataFrame) -> pd.DataFrame:
    """Source 3 — daily, but always two days behind (the freshness problem)."""
    cutoff = END - pd.Timedelta(days=2)
    daily = (
        sales[sales["date"] <= cutoff]
        .groupby(["date", "region", "sku"], as_index=False)["units"].sum()
    )
    daily["fill_rate"] = np.clip(RNG.normal(0.985, 0.012, len(daily)), 0.80, 1.0)

    p = EFFECTS["STOCKOUT_ELEC_NL"]["params"]
    lo, hi = _w("STOCKOUT_ELEC_NL")
    hit = (
        (daily["region"] == "NL")
        & (daily["sku"] == "ELEC-002")
        & daily["date"].between(lo, hi)
    )
    daily["fill_rate"] = np.where(hit, p["fill_rate"], daily["fill_rate"])
    daily["stock_on_hand"] = np.round(
        daily["units"] * RNG.uniform(6, 14, len(daily)) * daily["fill_rate"]
    ).astype(int)
    daily["days_of_cover"] = (daily["stock_on_hand"] / daily["units"].clip(lower=0.1)).round(1)
    return daily[["date", "region", "sku", "stock_on_hand", "fill_rate", "days_of_cover"]]


# -------------------------------------------------------------------- main --

def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range(START, END, freq="D")

    print(f"generating {len(dates)} days, {START.date()} -> {END.date()}")

    traffic = build_traffic(dates)
    mix = build_mix(dates)
    prices = build_prices(dates)

    sales = build_sales(traffic, mix, prices)
    traffic_src = build_traffic_source(traffic)
    marketing = build_marketing(dates)
    inventory = build_inventory(dates, sales)

    outputs = {
        "sales.parquet": sales,
        "traffic.parquet": traffic_src,
        "marketing_weekly.parquet": marketing,
        "inventory_daily.parquet": inventory,
    }
    for name, frame in outputs.items():
        duckdb.sql("SELECT * FROM frame").write_parquet(str(RAW / name))
        print(f"  {name:26} {len(frame):>8,} rows")

    ground_truth = {
        "seed": SEED,
        "focal_week": FOCAL_WEEK,
        "date_range": {"start": str(START.date()), "end": str(END.date())},
        "note": "Effects the engine is expected to recover. Written from the same "
                "definitions the generator applies, so it cannot drift.",
        "effects": EFFECTS,
    }
    with open(ROOT / "ground_truth.yaml", "w") as fh:
        yaml.safe_dump(ground_truth, fh, sort_keys=False, default_flow_style=False, width=88)

    print(f"\nground truth  -> data/ground_truth.yaml ({len(EFFECTS)} planted effects)")
    print(f"raw extracts  -> data/raw/")
    print(f"focal week    -> {FOCAL_WEEK}")


if __name__ == "__main__":
    main()
