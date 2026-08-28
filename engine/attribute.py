"""
Rung 3 — where did it happen? Still exact, still no model.

Ranking slices by the size of their movement returns your biggest markets every
single week. It is not wrong, it is just never news. This module ranks by
SURPRISE instead: how far a slice departed from its own expected share of the
whole, measured as its contribution to the Jensen-Shannon divergence between the
expected and actual distributions.

    explanatory power  EP(s) = delta_s / delta_total       how much of the move is here
    surprise           S(s)  = JS contribution of s        how far out of character it is

Three rules keep the ranking honest, each learned the hard way:

  1. A slice with no baseline is not "surprising", it is unknown. A product
     launched six weeks ago has an expected value of zero, which scores maximum
     divergence and hijacks the ranking — while explaining nothing. Those slices
     are reported separately, never ranked.

  2. A slice moving OPPOSITE to the gap is an offset, not a cause. When revenue
     is down, a category that grew is not why. It is listed, but as an offset.

  3. Descending into a subtree with no baselines is pointless — every child
     looks maximally surprising because nothing has a history. The drill stops.

    python -m engine.attribute                 # focal week
    python -m engine.attribute 2026-W33
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from engine.contract import Contract, load
from engine.decompose import MIN_HISTORY, PERIOD
from engine.detect import FOCAL_WEEK, _expectation
from engine.warehouse import connect, view_for, where_clause

EXPLAINS, OFFSETS, IMMATERIAL, NO_BASELINE = "explains", "offsets", "immaterial", "no baseline"


# ------------------------------------------------------------- divergence --

def js_contributions(expected: np.ndarray, actual: np.ndarray) -> np.ndarray:
    """
    Per-element contribution to the Jensen-Shannon divergence between two
    distributions. Symmetric and bounded, unlike KL, so one slice going to zero
    does not send the whole measure to infinity.
    """
    p = expected / expected.sum() if expected.sum() > 0 else np.zeros_like(expected, dtype=float)
    q = actual / actual.sum() if actual.sum() > 0 else np.zeros_like(actual, dtype=float)
    m = (p + q) / 2.0

    def term(x: np.ndarray) -> np.ndarray:
        out = np.zeros_like(x, dtype=float)
        ok = (x > 0) & (m > 0)
        out[ok] = x[ok] * np.log2(x[ok] / m[ok])
        return out

    return 0.5 * (term(p) + term(q))


# ------------------------------------------------------------ slice state --

def slice_state(
    con, contract: Contract, kpi_id: str, dimension: str, week: str,
    filters: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Expected and actual value of the KPI for every value of one dimension."""
    view = view_for(contract, kpi_id)
    expr = contract.kpi(kpi_id)["expr"]
    sql = f"""
        SELECT iso_week, {dimension} AS slice, {expr} AS value
        FROM {view}
        {where_clause(filters)}
        GROUP BY iso_week, {dimension}
        HAVING {expr} IS NOT NULL
        ORDER BY iso_week
    """
    raw = con.sql(sql).to_df()

    rows = []
    for name, grp in raw.groupby("slice"):
        grp = grp.sort_values("iso_week")
        weeks = grp["iso_week"].tolist()
        if week not in weeks:
            continue
        idx = weeks.index(week)
        values = grp["value"].to_numpy(dtype=float)

        expected = _expectation(values, idx, PERIOD, MIN_HISTORY)
        rows.append({
            "slice": name,
            "expected": float(expected) if expected is not None else np.nan,
            "actual": float(values[idx]),
            "has_baseline": expected is not None,
        })

    return pd.DataFrame(rows)


def rank_slices(state: pd.DataFrame, min_ep: float, gap_sign: float) -> pd.DataFrame:
    """
    Attach explanatory power, surprise and a role, then order by surprise.

    Surprise is computed only across slices that have a baseline, and the shares
    are renormalised over those — otherwise a single unknown slice distorts the
    distribution every other slice is being measured against.
    """
    df = state.copy()
    df["delta"] = np.where(df["has_baseline"], df["actual"] - df["expected"], np.nan)

    known = df["has_baseline"].to_numpy()
    total_delta = float(np.nansum(df["delta"].to_numpy()))

    df["surprise"] = 0.0
    if known.sum() >= 2:
        df.loc[known, "surprise"] = js_contributions(
            df.loc[known, "expected"].to_numpy(dtype=float),
            df.loc[known, "actual"].to_numpy(dtype=float),
        )

    total_surprise = float(df.loc[known, "surprise"].sum())
    df["surprise_share"] = df["surprise"] / total_surprise if total_surprise > 0 else 0.0
    df["ep"] = df["delta"] / total_delta if total_delta else 0.0

    def role(r) -> str:
        if not r["has_baseline"]:
            return NO_BASELINE
        # EP is positive when the slice moves the same way as the total gap
        if r["ep"] >= min_ep:
            return EXPLAINS
        if r["ep"] <= -min_ep:
            return OFFSETS
        return IMMATERIAL

    df["role"] = df.apply(role, axis=1)
    order = {EXPLAINS: 0, OFFSETS: 1, IMMATERIAL: 2, NO_BASELINE: 3}
    df["_o"] = df["role"].map(order)
    return df.sort_values(["_o", "surprise"], ascending=[True, False]).drop(columns="_o").reset_index(drop=True)


# ------------------------------------------------------------------ drill --

@dataclass
class Level:
    depth: int
    dimension: str
    divergence: float
    table: pd.DataFrame
    chosen: str | None = None
    considered: dict[str, float] = field(default_factory=dict)
    stopped: str = ""


def drill(
    con, contract: Contract, kpi_id: str, week: str,
    filters: dict[str, Any] | None = None,
) -> list[Level]:
    """
    Greedy descent. At each level, score every remaining dimension by the total
    divergence across slices that HAVE a baseline, and follow the one that
    concentrates the most.
    """
    cfg = contract.raw.get("attribution", {})
    min_ep = float(cfg.get("min_explanatory_power", 0.02))
    max_depth = int(cfg.get("max_depth", 3))

    active = dict(filters or {})
    remaining = [d for d in contract.kpi(kpi_id).get("sliceable_by", []) if d not in active]
    levels: list[Level] = []

    for depth in range(max_depth):
        if not remaining:
            break

        scored: list[tuple[float, str, pd.DataFrame]] = []
        for dim in remaining:
            state = slice_state(con, contract, kpi_id, dim, week, active or None)
            if state["has_baseline"].sum() < 2:
                continue                      # rule 3: nothing to compare against
            table = rank_slices(state, min_ep, 1.0)
            scored.append((float(table["surprise"].sum()), dim, table))

        if not scored:
            levels.append(Level(depth, "—", 0.0, pd.DataFrame(),
                                stopped="no dimension left with enough history to compare"))
            break

        scored.sort(key=lambda t: t[0], reverse=True)
        divergence, dimension, table = scored[0]

        candidates = table[table["role"] == EXPLAINS]
        chosen = str(candidates.iloc[0]["slice"]) if len(candidates) else None

        levels.append(Level(
            depth=depth, dimension=dimension, divergence=divergence, table=table,
            chosen=chosen, considered={d: s for s, d, _ in scored},
            stopped="" if chosen else "no slice moved with the gap by more than the EP floor",
        ))

        if chosen is None:
            break
        active[dimension] = chosen
        remaining.remove(dimension)

    return levels


# ----------------------------------------------------------------- output --

def render_table(table: pd.DataFrame, top_n: int = 6) -> str:
    if table.empty:
        return "  (nothing to rank)"
    rows = []
    for _, r in table.head(top_n).iterrows():
        known = bool(r["has_baseline"])
        rows.append({
            "slice": str(r["slice"])[:24],
            "expected": f"{r['expected']:,.0f}" if known else "—",
            "actual": f"{r['actual']:,.0f}",
            "delta": f"{r['delta']:+,.0f}" if known else "—",
            "share of gap": f"{r['ep']:+.0%}" if known else "—",
            "surprise": f"{r['surprise_share']:.1%}" if known else "—",
            "role": r["role"],
        })
    return pd.DataFrame(rows).to_string(index=False)


def main() -> None:
    week = sys.argv[1] if len(sys.argv) > 1 else FOCAL_WEEK
    contract = load()
    con = connect(contract=contract)
    cfg = contract.raw.get("attribution", {})
    top_n = int(cfg.get("top_n", 5)) + 1

    print("Rung 3 — dimensional attribution")
    print(f"ranked by {cfg.get('rank_by')} ({cfg.get('divergence')} divergence), "
          f"EP floor {cfg.get('min_explanatory_power')}\n")

    for lv in drill(con, contract, "net_revenue", week):
        if lv.considered:
            order = ", ".join(f"{d} {s:.4f}" for d, s in
                              sorted(lv.considered.items(), key=lambda t: -t[1]))
            print(f"depth {lv.depth}  ->  split on {lv.dimension.upper()}   ({order})")
            print(render_table(lv.table, top_n))

            # what was kept out of the ranking, and why
            for role, why in [
                (OFFSETS, "moved against the gap — an offset, not a cause"),
                (NO_BASELINE, "no history to be surprising against"),
            ]:
                held = lv.table[lv.table["role"] == role]
                if len(held):
                    names = ", ".join(str(s) for s in held["slice"].head(4))
                    more = f" +{len(held) - 4} more" if len(held) > 4 else ""
                    print(f"    excluded ({role}): {names}{more} — {why}")
        if lv.chosen:
            print(f"  descend into: {lv.chosen}\n")
        else:
            print(f"  stop: {lv.stopped}\n")

    # the point of surprise-ranking, stated plainly
    print("-" * 78)
    print("Why surprise and not size — Electronics SKU ELEC-002 by region\n")
    state = slice_state(con, contract, "net_revenue", "region", week, {"sku": "ELEC-002"})
    table = rank_slices(state, float(cfg.get("min_explanatory_power", 0.02)), 1.0)

    by_size = table.reindex(table["delta"].abs().sort_values(ascending=False).index)
    print(f"  {'ranked by size':<30}{'ranked by surprise':<30}")
    print(f"  {'-' * 26}    {'-' * 30}")
    for i in range(len(table)):
        a, b = by_size.iloc[i], table.iloc[i]
        print(f"  {a['slice']:<6}{a['delta']:>+12,.0f}          "
              f"{b['slice']:<6}{b['surprise_share']:>7.1%}  ({b['delta']:+,.0f})")


if __name__ == "__main__":
    main()
