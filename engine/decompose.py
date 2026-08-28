"""
Rungs 1 and 2 — exact attribution. No model, so it cannot be wrong.

Rung 1 (LMDI) splits the revenue gap across the four factors of the identity

    sessions x conversion_rate x units_per_order x asp = net_revenue

The counterfactual is each factor at its own seasonal expectation, and expected
revenue is defined as the product of those expectations. That makes the identity
hold exactly, so the contributions sum to the gap with nothing left over — no
interaction term to hand-wave away.

Rung 2 (Bennet indicator) then splits the ASP contribution into the part caused
by changing prices and the part caused by the basket shifting between SKUs at
different prices. Mix is the effect that is invisible without this step: revenue
can fall while every price rose and unit counts held flat.

Both decompositions are exact. tests/test_exactness.py asserts it.

    python -m engine.decompose                 # focal week
    python -m engine.decompose 2026-W33
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from engine.contract import Contract, load
from engine.detect import FOCAL_WEEK, _expectation
from engine.warehouse import connect, series, view_named, where_clause

PERIOD = 52
MIN_HISTORY = 104


# -------------------------------------------------------------- index maths --

def log_mean(a: float, b: float) -> float:
    """L(a,b) = (a-b)/(ln a - ln b). The weight that makes LMDI exact."""
    if a <= 0 or b <= 0:
        return 0.0
    if abs(a - b) < 1e-12:
        return a
    return (a - b) / (math.log(a) - math.log(b))


def lmdi(expected: dict[str, float], actual: dict[str, float]) -> dict[str, float]:
    """
    Additive LMDI over a multiplicative chain.

        dV = sum_i  L(V1,V0) * ln(x_i1 / x_i0)

    Sums exactly to V1 - V0 because the logs telescope to ln(V1/V0).
    """
    v0 = math.prod(expected.values())
    v1 = math.prod(actual.values())
    weight = log_mean(v1, v0)
    return {
        k: weight * math.log(actual[k] / expected[k]) if expected[k] > 0 and actual[k] > 0 else 0.0
        for k in expected
    }


def bennet_asp(
    exp_q: pd.Series, exp_p: pd.Series, act_q: pd.Series, act_p: pd.Series
) -> tuple[float, float]:
    """
    Split the change in average selling price into price and mix.

        ASP = sum_s w_s * p_s          w_s = q_s / Q

        price = sum_s  wbar_s * (p1_s - p0_s)     we changed prices
        mix   = sum_s  pbar_s * (w1_s - w0_s)     the basket moved

    Using midpoint weights makes this exact: price + mix = ASP1 - ASP0, with no
    residual and no arbitrary choice of base period.
    """
    q0_total, q1_total = exp_q.sum(), act_q.sum()
    w0 = exp_q / q0_total if q0_total else exp_q * 0.0
    w1 = act_q / q1_total if q1_total else act_q * 0.0

    w_bar = (w0 + w1) / 2.0
    p_bar = (exp_p + act_p) / 2.0

    price = float((w_bar * (act_p - exp_p)).sum())
    mix = float((p_bar * (w1 - w0)).sum())
    return price, mix


# ----------------------------------------------------------------- plumbing --

def _at_week(frame: pd.DataFrame, week: str) -> tuple[float | None, float | None]:
    """(expected, actual) for a weekly series at the target week."""
    weeks = frame["iso_week"].tolist()
    if week not in weeks:
        return None, None
    idx = weeks.index(week)
    values = frame["value"].to_numpy(dtype=float)
    return _expectation(values, idx, PERIOD, MIN_HISTORY), float(values[idx])


def _sku_state(
    con, week: str, filters: dict[str, Any] | None
) -> tuple[pd.DataFrame, list[str]]:
    """
    Expected and actual units/ASP per SKU.

    A SKU with too little history has no counterfactual. Rather than invent one,
    it enters with expected units of zero at its own price — which is exactly
    what a new product is: pure mix. It is still named in the output so the
    reader can see the engine treated it differently.
    """
    view = view_named("week_rcs")
    sql = f"""
        SELECT iso_week, sku,
               sum(units)                               AS units,
               sum(net_revenue) / nullif(sum(units), 0) AS asp
        FROM {view}
        {where_clause(filters)}
        GROUP BY iso_week, sku
        ORDER BY iso_week
    """
    raw = con.sql(sql).to_df()

    rows, no_counterfactual = [], []
    for sku, grp in raw.groupby("sku"):
        grp = grp.sort_values("iso_week")
        weeks = grp["iso_week"].tolist()
        if week not in weeks:
            continue
        idx = weeks.index(week)
        units = grp["units"].to_numpy(dtype=float)
        asp = grp["asp"].to_numpy(dtype=float)

        exp_units = _expectation(units, idx, PERIOD, MIN_HISTORY)
        exp_asp = _expectation(asp, idx, PERIOD, MIN_HISTORY)

        if exp_units is None or exp_asp is None:
            no_counterfactual.append(sku)
            exp_units, exp_asp = 0.0, float(asp[idx])   # enters as pure mix

        rows.append({
            "sku": sku,
            "exp_units": max(exp_units, 0.0), "exp_asp": exp_asp,
            "act_units": float(units[idx]),   "act_asp": float(asp[idx]),
        })

    return pd.DataFrame(rows).set_index("sku"), no_counterfactual


# ------------------------------------------------------------------ result --

@dataclass
class Contribution:
    factor: str
    label: str
    expected: float
    actual: float
    gbp: float
    rung: int
    method: str
    children: list["Contribution"] = field(default_factory=list)

    @property
    def pct_of_gap(self) -> float:
        return self._share

    _share: float = 0.0


@dataclass
class Decomposition:
    week: str
    actual_revenue: float
    expected_revenue: float
    delta: float
    contributions: list[Contribution]
    no_counterfactual: list[str]
    asp_reconciliation: float
    direct_expected_revenue: float | None = None

    @property
    def explained(self) -> float:
        return sum(c.gbp for c in self.contributions)


# ------------------------------------------------------------- the cascade --

def decompose(
    con, contract: Contract, week: str = FOCAL_WEEK, filters: dict[str, Any] | None = None
) -> Decomposition:
    spec = contract.decomposition("net_revenue")
    view = view_named(spec["view"])

    # --- Rung 1: each factor at its own expectation ----------------------
    expected: dict[str, float] = {}
    actual: dict[str, float] = {}
    labels: dict[str, str] = {}

    for link in spec["chain"]:
        factor = link["factor"]
        labels[factor] = link["label"]
        exp, act = _at_week(series(con, view, link["expr"], filters), week)
        if exp is None or act is None:
            raise ValueError(f"no baseline for factor {factor!r} at {week}")
        expected[factor], actual[factor] = exp, act

    expected_revenue = math.prod(expected.values())
    actual_revenue = math.prod(actual.values())
    delta = actual_revenue - expected_revenue

    parts = lmdi(expected, actual)

    contributions = [
        Contribution(
            factor=f, label=labels[f], expected=expected[f], actual=actual[f],
            gbp=parts[f], rung=1, method="lmdi",
            _share=parts[f] / delta if delta else 0.0,
        )
        for f in expected
    ]

    # --- Rung 2: split the ASP contribution into price and mix -----------
    state, no_counterfactual = _sku_state(con, week, filters)
    price_effect, mix_effect = bennet_asp(
        state["exp_units"], state["exp_asp"], state["act_units"], state["act_asp"]
    )
    delta_asp_sku = price_effect + mix_effect
    delta_asp_top = actual["asp"] - expected["asp"]

    asp_node = next(c for c in contributions if c.factor == "asp")
    if abs(delta_asp_sku) > 1e-9:
        for name, label, value in [
            ("price", "Price changes", price_effect),
            ("mix", "Basket mix", mix_effect),
        ]:
            gbp = asp_node.gbp * (value / delta_asp_sku)
            asp_node.children.append(Contribution(
                factor=name, label=label, expected=float("nan"), actual=float("nan"),
                gbp=gbp, rung=2, method="bennet_indicator",
                _share=gbp / delta if delta else 0.0,
            ))

    return Decomposition(
        week=week,
        actual_revenue=actual_revenue,
        expected_revenue=expected_revenue,
        delta=delta,
        contributions=contributions,
        no_counterfactual=no_counterfactual,
        # the two routes to an ASP expectation differ slightly; surfaced, not hidden
        asp_reconciliation=delta_asp_top - delta_asp_sku,
    )


# ------------------------------------------------------------------ output --

def _num(value: float) -> str:
    """Factors span sessions (millions) to conversion (0.0273) — scale the precision."""
    a = abs(value)
    if a >= 10_000:
        return f"{value:,.0f}"
    if a >= 10:
        return f"{value:,.2f}"
    return f"{value:,.4f}"


def render(d: Decomposition, contract: Contract) -> str:
    cur = contract.currency
    out = [
        f"Net Revenue, {d.week}",
        f"  actual        {d.actual_revenue:>14,.0f} {cur}",
        f"  expected      {d.expected_revenue:>14,.0f} {cur}   (product of factor expectations)",
        f"  gap           {d.delta:>+14,.0f} {cur}",
        "",
        f"{'':2}{'factor':22}{'expected':>14}{'actual':>14}{'contribution':>16}{'share':>9}  method",
        f"{'':2}{'-' * 77}",
    ]

    for c in sorted(d.contributions, key=lambda x: x.gbp):
        out.append(
            f"{'':2}{c.label:22}{_num(c.expected):>14}{_num(c.actual):>14}"
            f"{c.gbp:>+16,.0f}{c.pct_of_gap:>8.0%}  {c.method}"
        )
        for ch in sorted(c.children, key=lambda x: x.gbp):
            out.append(
                f"{'':4}└─ {ch.label:17}{'':14}{'':14}"
                f"{ch.gbp:>+16,.0f}{ch.pct_of_gap:>8.0%}  {ch.method}"
            )

    out += [
        f"{'':2}{'-' * 77}",
        f"{'':2}{'sum of contributions':22}{'':28}{d.explained:>+16,.0f}",
        f"{'':2}{'gap':22}{'':28}{d.delta:>+16,.0f}",
        f"{'':2}{'residual':22}{'':28}{d.explained - d.delta:>+16,.2f}   <- exact, by construction",
    ]

    if d.no_counterfactual:
        out += [
            "",
            f"  no counterfactual ({len(d.no_counterfactual)}): {', '.join(d.no_counterfactual)}",
            "    too little history for a baseline — entered as pure mix at its own price",
        ]

    out += [
        "",
        f"  ASP reconciliation: {d.asp_reconciliation:+.4f} {cur}/unit between the top-level",
        "    ASP baseline and the SKU-level reconstruction. Reported, not absorbed.",
    ]
    return "\n".join(out)


def main() -> None:
    week = sys.argv[1] if len(sys.argv) > 1 else FOCAL_WEEK
    contract = load()
    con = connect(contract=contract)

    print("Rungs 1-2 — exact decomposition\n")
    d = decompose(con, contract, week)
    print(render(d, contract))


if __name__ == "__main__":
    main()
