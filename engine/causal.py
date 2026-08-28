"""
Rung 4 — outside causes. Exact arithmetic runs out here; estimation begins.

Marketing spend, discounting and stock availability are not terms in the KPI
identity, so they cannot be decomposed into it. They have to be estimated, and
every number this module produces carries a range and a stated assumption.

Two steps, deliberately unequal in strength:

  A. SHORTLIST — lagged correlation between the deseasonalised KPI and each
     driver the contract declares. Labelled ASSOCIATIVE. This ranks suspects;
     it does not convict. Drivers with no instrumented source are listed too,
     as candidates the engine cannot see — which is how the honest residual
     survives instead of being quietly attributed to whatever did correlate.

  B. TEST ONE — difference-in-differences for the top candidate, against a
     control group that was not affected. Reported with a confidence interval,
     and WITHHELD if the pre-period parallel-trends test fails, because the
     estimator is meaningless without it.

The treated unit and the event week are discovered from the data, not passed in.

    python -m engine.causal
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.seasonal import STL

from engine.contract import Contract, load
from engine.decompose import MIN_HISTORY, PERIOD
from engine.detect import FOCAL_WEEK, weekly_series
from engine.warehouse import connect, series, view_named

MIN_PRE_WEEKS = 12
MIN_POST_WEEKS = 2


# ---------------------------------------------------- A. correlation scan --

@dataclass
class DriverSignal:
    driver: str
    label: str
    type: str
    observable: bool
    correlation: float | None = None
    best_lag: int | None = None
    method: str = "lagged_pearson_on_stl_residual"
    note: str = ""


def _deseasonalised(values: np.ndarray) -> np.ndarray | None:
    """STL residual — strips trend and seasonality so a correlation is not just
    two things sharing a Christmas."""
    if len(values) < 2 * PERIOD:
        return None
    fit = STL(np.asarray(values, dtype=float), period=PERIOD, robust=True).fit()
    return np.asarray(fit.resid, dtype=float)


def shortlist(con, contract: Contract, kpi_id: str = "net_revenue") -> list[DriverSignal]:
    """Rank the contract's declared drivers by lagged association. Associative only."""
    kpi = weekly_series(con, contract, kpi_id)
    kpi_resid = _deseasonalised(kpi["value"].to_numpy(dtype=float))
    kpi_weeks = kpi["iso_week"].tolist()

    out: list[DriverSignal] = []
    for name, spec in contract.drivers.items():
        if not spec.get("source") or not spec.get("view"):
            out.append(DriverSignal(
                driver=name, label=spec["label"], type=spec["type"], observable=False,
                method="none",
                note="no instrumented source — cannot be observed, only inferred",
            ))
            continue

        frame = series(con, view_named(spec["view"]), spec["expr"])
        aligned = pd.DataFrame({"iso_week": kpi_weeks, "kpi": kpi_resid}).merge(
            frame.rename(columns={"value": "driver"})[["iso_week", "driver"]],
            on="iso_week", how="inner",
        )
        driver_resid = _deseasonalised(aligned["driver"].to_numpy(dtype=float))
        if driver_resid is None or len(aligned) < 2 * PERIOD:
            out.append(DriverSignal(name, spec["label"], spec["type"], True,
                                    note="too little overlapping history to correlate"))
            continue

        lo, hi = spec.get("lag_weeks", [0, 0])
        best_r, best_lag = 0.0, 0
        for lag in range(int(lo), int(hi) + 1):
            a = aligned["kpi"].to_numpy(dtype=float)[lag:] if lag else aligned["kpi"].to_numpy(dtype=float)
            b = driver_resid[: len(driver_resid) - lag] if lag else driver_resid
            n = min(len(a), len(b))
            if n < 30:
                continue
            r = float(np.corrcoef(a[:n], b[:n])[0, 1])
            if abs(r) > abs(best_r):
                best_r, best_lag = r, lag

        out.append(DriverSignal(
            driver=name, label=spec["label"], type=spec["type"], observable=True,
            correlation=best_r, best_lag=best_lag,
            note="association only — not evidence of cause",
        ))

    out.sort(key=lambda d: (d.observable, abs(d.correlation or 0.0)), reverse=True)
    return out


# ------------------------------------------------ B. difference-in-differences --

@dataclass
class CausalEstimate:
    outcome: str
    treated: str
    controls: list[str]
    event_week: str
    effect: float
    ci: tuple[float, float]
    p_value: float
    n_obs: int
    parallel_trends_p: float
    parallel_trends_ok: bool
    withheld: bool
    pre_trend_per_week: float = 0.0
    projected_bias: float = 0.0
    contamination: float = 0.0
    impact_gbp: float | None = None
    relative: float | None = None
    method: str = "difference_in_differences"
    assumptions: list[str] = field(default_factory=lambda: [
        "parallel trends: treated and control move together absent the event",
        "no other shock hit only the treated unit at the same time",
        "control units are themselves unaffected (no spillover)",
    ])


def unit_panel(con, contract: Contract, kpi_id: str, dimension: str = "region") -> pd.DataFrame:
    """Long panel: one row per unit per week."""
    view = view_named(contract.kpi(kpi_id)["view"])
    expr = contract.kpi(kpi_id)["expr"]
    return con.sql(f"""
        SELECT iso_week, {dimension} AS unit, {expr} AS value
        FROM {view}
        GROUP BY iso_week, {dimension}
        HAVING {expr} IS NOT NULL
        ORDER BY iso_week
    """).to_df()


def find_treated_unit(panel: pd.DataFrame, window: int = 6) -> str:
    """
    The unit that most recently departed from the others.

    Each unit is normalised against its own long-run level first, so this picks
    the unit that changed relative to itself — not simply the smallest one.
    """
    wide = panel.pivot(index="iso_week", columns="unit", values="value").sort_index()
    relative = wide.div(wide.mean(axis=1), axis=0)          # share of the cross-unit mean
    baseline = relative.iloc[:-window].mean()
    recent = relative.iloc[-window:].mean()
    return str((recent - baseline).idxmin())


def find_event_week(panel: pd.DataFrame, treated: str, search: int = 16) -> str:
    """
    Changepoint in the treated-minus-control gap: the split that maximises the
    shift in mean between before and after.
    """
    wide = panel.pivot(index="iso_week", columns="unit", values="value").sort_index()
    controls = [c for c in wide.columns if c != treated]
    gap = (wide[treated] / wide[controls].mean(axis=1)).to_numpy(dtype=float)
    weeks = wide.index.tolist()

    best_week, best_shift = weeks[-search], 0.0
    for i in range(len(weeks) - search, len(weeks) - MIN_POST_WEEKS):
        if i < MIN_PRE_WEEKS:
            continue
        shift = abs(float(gap[i:].mean() - gap[max(0, i - 26):i].mean()))
        if shift > best_shift:
            best_shift, best_week = shift, weeks[i]
    return str(best_week)


def difference_in_differences(
    panel: pd.DataFrame, treated: str, event_week: str,
    end_week: str, pre_weeks: int = 26, max_contamination: float = 0.20,
) -> CausalEstimate:
    """
    Two-way fixed effects:

        Y_it = alpha_i + lambda_t + tau*(treated_i x post_t) + e_it

    The unit fixed effects matter more than they look. Without them every
    difference in level between units lands in the error term — with five units
    spanning a wide range that inflated the residual spread by an order of
    magnitude and buried a pre-trend the test was supposed to catch. Time fixed
    effects absorb whatever moved all units together that week.

    Heteroskedasticity-robust standard errors; five units are too few to cluster
    on, which is a stated limitation rather than a hidden one.
    """
    weeks = sorted(panel["iso_week"].unique().tolist())
    ev, end = weeks.index(event_week), weeks.index(end_week)
    window = weeks[max(0, ev - pre_weeks): end + 1]

    df = panel[panel["iso_week"].isin(window)].reset_index(drop=True).copy()
    df["treated"] = (df["unit"] == treated).astype(float)
    df["post"] = (df["iso_week"] >= event_week).astype(float)
    df["did"] = df["treated"] * df["post"]

    def with_fixed_effects(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
        unit_fe = pd.get_dummies(frame["unit"], prefix="u", drop_first=True, dtype=float)
        time_fe = pd.get_dummies(frame["iso_week"], prefix="w", drop_first=True, dtype=float)
        return sm.add_constant(pd.concat(
            [frame[cols].reset_index(drop=True),
             unit_fe.reset_index(drop=True),
             time_fe.reset_index(drop=True)], axis=1,
        ))

    model = sm.OLS(df["value"].to_numpy(dtype=float),
                   with_fixed_effects(df, ["did"])).fit(cov_type="HC1")
    tau = float(model.params["did"])
    lo, hi = (float(x) for x in model.conf_int().loc["did"])

    # --- parallel trends, on the PRE period only -------------------------
    pre = df[df["post"] == 0].reset_index(drop=True).copy()
    pre["t"] = pre["iso_week"].map({w: i for i, w in enumerate(window)}).astype(float)
    pre["trend_x_treated"] = pre["t"] * pre["treated"]
    pt = sm.OLS(pre["value"].to_numpy(dtype=float),
                with_fixed_effects(pre, ["trend_x_treated"])).fit(cov_type="HC1")
    pt_p = float(pt.pvalues["trend_x_treated"])

    # Judge the pre-trend by what it could account for, not by its p-value.
    # Extrapolate it across the post window and ask how much of the estimated
    # effect it could explain away.
    pre_slope = float(pt.params["trend_x_treated"])
    post_weeks = int(df.loc[df["post"] == 1, "iso_week"].nunique())
    projected_bias = pre_slope * post_weeks
    contamination = abs(projected_bias) / abs(tau) if tau else float("inf")
    pt_ok = contamination <= max_contamination

    control_mean = float(df[(df["unit"] != treated) & (df["post"] == 0)]["value"].mean())
    treated_pre = float(df[(df["unit"] == treated) & (df["post"] == 0)]["value"].mean())

    return CausalEstimate(
        outcome="", treated=treated,
        controls=sorted(u for u in panel["unit"].unique() if u != treated),
        event_week=event_week, effect=tau, ci=(lo, hi),
        p_value=float(model.pvalues["did"]), n_obs=int(model.nobs),
        parallel_trends_p=pt_p, parallel_trends_ok=pt_ok,
        withheld=not pt_ok,
        pre_trend_per_week=pre_slope,
        projected_bias=projected_bias,
        contamination=contamination,
        relative=tau / treated_pre if treated_pre else None,
    )


# ------------------------------------------------------------------ output --

def main() -> None:
    week = sys.argv[1] if len(sys.argv) > 1 else FOCAL_WEEK
    contract = load()
    con = connect(contract=contract)

    print("Rung 4 — outside causes\n")

    # ---- A ----
    print("A. Driver shortlist — ASSOCIATIVE, ranks suspects only")
    print("-" * 74)
    rows = []
    for d in shortlist(con, contract, "net_revenue"):
        rows.append({
            "driver": d.label,
            "type": d.type,
            "observable": "yes" if d.observable else "NO",
            "corr": f"{d.correlation:+.3f}" if d.correlation is not None else "—",
            "lag": f"{d.best_lag}w" if d.best_lag is not None else "—",
            "note": d.note,
        })
    print(pd.DataFrame(rows).to_string(index=False))

    # ---- B ----
    print("\n\nB. Difference-in-differences on the unexplained conversion gap")
    print("-" * 74)

    cfg = contract.raw.get("causal", {})
    max_contam = float(cfg.get("parallel_trends", {}).get("max_contamination", 0.20))

    panel = unit_panel(con, contract, "conversion_rate", "region")
    treated = find_treated_unit(panel)
    event = find_event_week(panel, treated)
    est = difference_in_differences(
        panel, treated, event, week,
        pre_weeks=int(cfg.get("pre_window_weeks", 26)), max_contamination=max_contam,
    )

    print(f"  specification:            {cfg.get('specification')}")
    print(f"  treated unit discovered:  {treated}   (largest recent divergence from peers)")
    print(f"  event week discovered:    {event}   (changepoint in the treated/control gap)")
    print(f"  controls:                 {', '.join(est.controls)}")
    print(f"  observations:             {est.n_obs}\n")

    print("  parallel trends check")
    print(f"    pre-trend on treated:   {est.pre_trend_per_week:+.6f} per week  "
          f"(p = {est.parallel_trends_p:.3f})")
    print(f"    projected across post:  {est.projected_bias:+.5f}")
    print(f"    could account for:      {est.contamination:.1%} of the estimate  "
          f"(limit {max_contam:.0%})")
    print(f"    verdict:                "
          f"{'estimate reportable' if est.parallel_trends_ok else 'CONTAMINATED, estimate withheld'}")

    if est.withheld:
        print("\n  Estimate withheld. The pre-existing trend could account for too much")
        print("  of the apparent effect for a causal reading to survive.")
        return

    ctx_sessions = con.sql(f"""
        SELECT sum(sessions) FROM {view_named('week_rc')}
        WHERE iso_week = '{week}' AND region = '{treated}'
    """).fetchone()[0]
    aov = weekly_series(con, contract, "aov")
    aov_now = float(aov.loc[aov["iso_week"] == week, "value"].iloc[0])
    impact = est.effect * float(ctx_sessions) * aov_now

    print(f"\n  effect on conversion:     {est.effect:+.5f}  "
          f"({est.relative:+.1%} relative to {treated}'s pre-period)")
    print(f"  95% CI:                   [{est.ci[0]:+.5f}, {est.ci[1]:+.5f}]   p = {est.p_value:.4f}")
    print(f"  revenue impact in {week}: {impact:+,.0f} {contract.currency}")

    print("\n  assumptions carried:")
    for a in est.assumptions:
        print(f"    - {a}")
    print("    - five units is too few to cluster standard errors on; HC1 used instead")

    uninstrumented = [d for d in shortlist(con, contract) if not d.observable]
    if uninstrumented:
        print("\n  This effect has no instrumented driver behind it. The contract lists")
        print("  the following as candidates the engine cannot observe:")
        for d in uninstrumented:
            print(f"    - {d.label} ({d.type}) — owner: "
                  f"{contract.drivers[d.driver].get('owner_role', 'unassigned')}")
        print("  It therefore stays an attributed effect without a named cause.")


if __name__ == "__main__":
    main()
