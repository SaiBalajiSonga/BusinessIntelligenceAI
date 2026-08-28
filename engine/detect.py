"""
Rung 0 — what should have happened, and did it materially not happen?

Delta is measured against a seasonal expectation, not against last week. The
baseline is fitted only on weeks BEFORE the target, so an anomaly can never be
absorbed into the trend that is supposed to reveal it.

The scale that turns delta into a z-score comes from a rolling one-step-ahead
backtest, not from in-sample residuals. With three seasonal cycles STL can fit
each phase almost exactly, so its in-sample error is near zero and every z
becomes astronomical. Asking "how wrong has this baseline been on weeks it had
not seen?" is the ruler that survives scrutiny.

A movement is reported only if it clears two bars at once:
  - statistical: |z| over the contract threshold, MAD-scaled
  - business:    currency impact over the contract's floor

    python -m engine.detect                     # focal week, all KPIs
    python -m engine.detect 2026-W33
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

from engine.contract import Contract, load
from engine.warehouse import connect, series, view_for

FOCAL_WEEK = "2026-W32"


# ------------------------------------------------------------------ series --

def supports(contract: Contract, kpi_id: str, filters: dict[str, Any] | None) -> bool:
    """
    Can this KPI be sliced this way at all?

    Conversion rate has no SKU because sessions have no SKU. The contract says
    so, and asking anyway is refused rather than silently joined into nonsense.
    """
    if not filters:
        return True
    allowed = set(contract.kpi(kpi_id).get("sliceable_by") or [])
    return set(filters).issubset(allowed)


def weekly_series(
    con, contract: Contract, kpi_id: str, filters: dict[str, Any] | None = None
) -> pd.DataFrame:
    """One row per ISO week: the KPI evaluated over whatever slice is asked for."""
    return series(con, view_for(contract, kpi_id), contract.kpi(kpi_id)["expr"], filters)


# ---------------------------------------------------------------- baseline --

@dataclass
class Baseline:
    expected: float | None
    scale: float | None
    method: str
    history_weeks: int
    backtest_n: int = 0
    confidence_cap: float = 1.0
    note: str = ""


def _expectation(values: np.ndarray, idx: int, period: int, min_history: int) -> float | None:
    """Seasonal expectation for values[idx], using only values[:idx]."""
    train = np.asarray(values[:idx], dtype=float)
    if len(train) < min_history or idx < period:
        return None

    stl = STL(train, period=period, robust=True).fit()

    # project the trend one step past the training window
    k = min(12, len(stl.trend))
    slope, intercept = np.polyfit(np.arange(k), stl.trend[-k:], 1)
    trend_projected = float(intercept + slope * k)

    # seasonal shape for this week-of-year, taken one full cycle back
    return trend_projected + float(stl.seasonal[idx - period])


def _mad_scale(errors: np.ndarray) -> float:
    med = float(np.median(errors))
    return 1.4826 * float(np.median(np.abs(errors - med)))


def estimate_baseline(
    values: np.ndarray, target_idx: int, spec: dict[str, Any], calibration: dict[str, Any]
) -> Baseline:
    """
    Expectation for the target week, plus an honestly-calibrated error scale.

    Falls back rather than guessing when there is too little history — a new SKU
    has no seasonal shape to learn, and pretending otherwise is how a confident
    wrong answer gets produced.
    """
    period = int(spec["period_weeks"])
    min_history = int(spec["min_history_weeks"])
    history = len(values[:target_idx])

    if history < min_history:
        return Baseline(
            None, None, "insufficient_history", history, confidence_cap=0.40,
            note=f"{spec['fallback']} required: {history} weeks of history, "
                 f"{min_history} needed for a period-{period} baseline",
        )

    expected = _expectation(values, target_idx, period, min_history)
    if expected is None:
        return Baseline(None, None, "insufficient_history", history, confidence_cap=0.40,
                        note="expectation could not be fitted")

    # rolling-origin backtest: refit at each earlier week and record how far off
    # the baseline was on data it had not seen
    window = int(calibration.get("window_weeks", 26))
    errors = []
    for i in range(max(min_history, target_idx - window), target_idx):
        got = _expectation(values, i, period, min_history)
        if got is not None:
            errors.append(values[i] - got)

    if len(errors) < 8:
        return Baseline(expected, None, "stl_uncalibrated", history, len(errors),
                        confidence_cap=0.50,
                        note=f"only {len(errors)} backtest points; scale unreliable")

    scale = _mad_scale(np.asarray(errors, dtype=float))
    return Baseline(expected, scale, "stl_backtested", history, len(errors))


# ------------------------------------------------------------------ impact --

def week_context(con, contract: Contract, week: str) -> dict[str, float]:
    """Actuals used to translate a ratio movement into currency."""
    ctx: dict[str, float] = {}
    for kpi_id in ("sessions", "orders", "net_revenue", "aov", "conversion_rate"):
        s = weekly_series(con, contract, kpi_id)
        row = s.loc[s["iso_week"] == week, "value"]
        if len(row):
            ctx[kpi_id] = float(row.iloc[0])
    return ctx


def to_currency(delta: float, multipliers: list[str] | None, ctx: dict[str, float]) -> float | None:
    """delta * the contract's declared multipliers -> GBP, or None if not monetisable."""
    if multipliers is None:
        return None
    out = delta
    for m in multipliers:
        if m not in ctx:
            return None
        out *= ctx[m]
    return out


# --------------------------------------------------------------- detection --

@dataclass
class Movement:
    kpi: str
    label: str
    unit: str
    iso_week: str
    actual: float
    expected: float | None
    delta: float | None
    delta_pct: float | None
    z: float | None
    impact_gbp: float | None
    material: bool
    baseline_method: str
    history_weeks: int
    backtest_n: int
    confidence_cap: float
    reasons: list[str] = field(default_factory=list)


def detect(
    con, contract: Contract, target_week: str = FOCAL_WEEK,
    filters: dict[str, Any] | None = None,
) -> list[Movement]:
    ctx = week_context(con, contract, target_week)
    calibration = contract.raw.get("baseline_calibration", {})
    min_impact = float(contract.raw["materiality"]["min_impact_gbp"])
    out: list[Movement] = []

    for kpi_id in contract.kpi_ids:
        spec = contract.kpi(kpi_id)
        if not supports(contract, kpi_id, filters):
            continue

        series = weekly_series(con, contract, kpi_id, filters)
        weeks = series["iso_week"].tolist()
        if target_week not in weeks:
            continue

        ti = weeks.index(target_week)
        values = series["value"].to_numpy(dtype=float)
        actual = float(values[ti])
        bl = estimate_baseline(values, ti, contract.baseline_spec(kpi_id), calibration)

        if bl.expected is None:
            out.append(Movement(
                kpi=kpi_id, label=spec["label"], unit=spec["unit"], iso_week=target_week,
                actual=actual, expected=None, delta=None, delta_pct=None, z=None,
                impact_gbp=None, material=False, baseline_method=bl.method,
                history_weeks=bl.history_weeks, backtest_n=bl.backtest_n,
                confidence_cap=bl.confidence_cap, reasons=[bl.note],
            ))
            continue

        delta = actual - bl.expected
        z = delta / bl.scale if bl.scale and bl.scale > 0 else None
        impact = to_currency(delta, spec.get("impact_multipliers"), ctx)
        min_abs, min_z = contract.materiality(kpi_id)

        stat_ok = z is not None and abs(z) >= min_z
        # currency bar where the KPI can be translated, native units where it cannot
        biz_ok = abs(impact) >= min_impact if impact is not None else abs(delta) >= min_abs

        reasons = []
        if not stat_ok:
            reasons.append(f"|z| {abs(z):.1f} below {min_z}" if z is not None else "no error scale")
        if not biz_ok:
            reasons.append(
                f"impact {abs(impact):,.0f} below the {min_impact:,.0f} floor"
                if impact is not None else f"|delta| below the {min_abs:g} floor"
            )

        out.append(Movement(
            kpi=kpi_id, label=spec["label"], unit=spec["unit"], iso_week=target_week,
            actual=actual, expected=bl.expected, delta=delta,
            delta_pct=delta / bl.expected if bl.expected else None,
            z=z, impact_gbp=impact, material=stat_ok and biz_ok,
            baseline_method=bl.method, history_weeks=bl.history_weeks,
            backtest_n=bl.backtest_n, confidence_cap=bl.confidence_cap, reasons=reasons,
        ))

    # both bars are the filter; business impact is the ordering
    out.sort(key=lambda m: (m.material, abs(m.impact_gbp or 0)), reverse=True)
    return out


# ------------------------------------------------------------------ output --

def _fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "ratio":
        return f"{value:.4f}"
    return f"{value:,.0f}"


def render(movements: list[Movement], contract: Contract) -> str:
    rows = []
    for m in movements:
        rows.append({
            "KPI": m.label,
            "actual": _fmt(m.actual, m.unit),
            "expected": _fmt(m.expected, m.unit),
            "delta": _fmt(m.delta, m.unit),
            "delta %": f"{m.delta_pct:+.1%}" if m.delta_pct is not None else "—",
            "z": f"{m.z:+.1f}" if m.z is not None else "—",
            f"impact {contract.currency}": f"{m.impact_gbp:,.0f}" if m.impact_gbp is not None else "—",
            "material": "YES" if m.material else "no",
        })
    return pd.DataFrame(rows).to_string(index=False)


def main() -> None:
    week = sys.argv[1] if len(sys.argv) > 1 else FOCAL_WEEK
    contract = load()
    con = connect(contract=contract)
    cal = contract.raw.get("baseline_calibration", {})

    print(f"Rung 0 — detection for {week}")
    print(f"baseline: STL(period=52) trained on prior weeks only")
    print(f"scale:    {cal.get('method')} over {cal.get('window_weeks')} weeks\n")

    movements = detect(con, contract, week)
    print(render(movements, contract))

    flagged = [m for m in movements if m.material]
    print(f"\n{len(flagged)} of {len(movements)} KPIs cleared both bars.")
    for m in movements:
        if not m.material and m.reasons:
            print(f"  {m.label:22} not flagged — {'; '.join(m.reasons)}")

    if flagged:
        print(f"\nbaseline calibrated on {flagged[0].backtest_n} out-of-sample weeks "
              f"({flagged[0].history_weeks} weeks of history)")

    # the contract refuses slices it cannot honour
    print("\n" + "-" * 74)
    print("Entitlement of a different kind — slicing conversion rate by SKU\n")
    for kpi_id in ("net_revenue", "conversion_rate"):
        ok = supports(contract, kpi_id, {"sku": "HOME-NEW-01"})
        note = "sliceable" if ok else "refused — sessions have no SKU grain"
        print(f"  {contract.kpi(kpi_id)['label']:22} {note}")

    # the sparse-history path: a SKU that launched seven weeks ago
    print("\n" + "-" * 74)
    print("Sparse history — same detector, new SKU (HOME-NEW-01)\n")
    for m in detect(con, contract, week, filters={"sku": "HOME-NEW-01"}):
        if m.baseline_method == "insufficient_history":
            print(f"  {m.label:22} ABSTAINS — {m.reasons[0]}")
            print(f"  {'':22} confidence capped at {m.confidence_cap:.2f}")


if __name__ == "__main__":
    main()
