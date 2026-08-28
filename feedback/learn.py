"""
What the loop actually learns.

Four mechanisms, each small and each inspectable. The test of a feedback loop is
not that it stores opinions but that a later run behaves differently because of
them — and that a person can see exactly how.

  1. CALIBRATION   Isotonic regression maps the raw confidence score onto the
     rate at which insights at that score were actually judged correct. This is
     the one place ML touches confidence, and it is the right place: whether
     "0.67" means anything is an empirical question, not a modelling choice.

  2. DRIVER PRIORS  When an analyst says the driver was wrong, the credited
     driver loses weight for that KPI and the named replacement gains it.

  3. MATERIALITY    Movements repeatedly dismissed as immaterial raise the bar
     for that KPI. Proposed, not applied — a threshold that moves on its own is
     how a governed metric quietly stops being governed.

  4. KNOWN EVENTS   A planned campaign is not an anomaly. Annotated windows are
     consulted before anything is called surprising.

    python -m feedback.learn
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd

from feedback.store import Annotation, Store, open_store

# a verdict either speaks to whether the explanation was RIGHT, or to whether it
# was WORTH SENDING. Mixing the two would teach the calibrator the wrong thing.
CORRECTNESS = {"correct": 1.0, "known_cause": 1.0, "wrong_driver": 0.0, "unclear": 0.0}
MATERIALITY_SIGNAL = "not_material"

MIN_CALIBRATION_SAMPLES = 25
MIN_THRESHOLD_SAMPLES = 5
ISO_WEEK = re.compile(r"^(\d{4})-W(\d{1,2})$")


def week_start(iso_week: str) -> date:
    m = ISO_WEEK.match(iso_week)
    if not m:
        raise ValueError(f"not an ISO week: {iso_week!r}")
    return date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)


# ------------------------------------------------------------ calibration --

def brier(probabilities: np.ndarray, outcomes: np.ndarray) -> float:
    """Mean squared error of a probability forecast. Lower is better."""
    return float(np.mean((probabilities - outcomes) ** 2))


@dataclass
class Calibration:
    fitted: bool
    n: int
    brier_before: float | None = None
    brier_after: float | None = None
    note: str = ""
    _model: Any = None

    def apply(self, score: float) -> float:
        if not self.fitted or self._model is None:
            return score
        return float(self._model.predict([score])[0])

    @property
    def improvement(self) -> float | None:
        if self.brier_before is None or self.brier_after is None:
            return None
        return self.brier_before - self.brier_after


def calibrate(store: Store, kpi: str | None = None) -> Calibration:
    """
    Fit the raw score onto observed correctness.

    Below the sample floor this returns the identity and says so. A calibrator
    fitted on nine data points is worse than none, because it looks like
    evidence.
    """
    df = store.feedback(kpi)
    if df.empty:
        return Calibration(False, 0, note="no feedback recorded yet")

    usable = df[df["verdict"].isin(CORRECTNESS) & df["confidence_shown"].notna()]
    n = len(usable)
    if n < MIN_CALIBRATION_SAMPLES:
        return Calibration(
            False, n,
            note=f"{n} usable responses; {MIN_CALIBRATION_SAMPLES} needed before a "
                 f"calibration curve means anything",
        )

    scores = usable["confidence_shown"].to_numpy(dtype=float)
    outcomes = usable["verdict"].map(CORRECTNESS).to_numpy(dtype=float)

    from sklearn.isotonic import IsotonicRegression

    model = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    model.fit(scores, outcomes)

    return Calibration(
        True, n,
        brier_before=brier(scores, outcomes),
        brier_after=brier(model.predict(scores), outcomes),
        note="isotonic regression on analyst verdicts",
        _model=model,
    )


# ---------------------------------------------------------- driver priors --

def driver_priors(store: Store, kpi: str | None = None) -> dict[str, dict[str, float]]:
    """
    Per-driver credibility, as a multiplier around 1.0.

    Two different quantities live in this feedback and must not be added
    together. PRECISION is "when we credit this driver, how often are we right?"
    MISSED is "how often was this driver the real cause while we credited
    something else?" A driver can be frequently correct-but-overlooked and still
    unreliable when we do reach for it — folding the second into the first gave
    marketing_spend a 1.33 boost on a 7-right, 8-wrong record.

    So the weight is precision only. The missed count travels alongside as a
    reason to CONSIDER a driver more often, never as a reason to trust it more
    once credited.

    Laplace-smoothed so one bad week cannot bury a driver, and clipped so the
    loop nudges the ranking without ever overturning the arithmetic beneath it.
    """
    df = store.feedback(kpi)
    if df.empty:
        return {}

    out: dict[str, dict[str, float]] = {}
    credited = df[df["driver"].notna()]

    def entry(right: int, wrong: int, missed: int) -> dict[str, float]:
        precision = (right + 1.0) / (right + wrong + 2.0)
        return {
            "weight": float(np.clip(precision / 0.5, 0.5, 1.5)),
            "precision": round(precision, 4),
            "right": right, "wrong": wrong,
            "missed_by_engine": missed,
            "n": right + wrong,
        }

    for driver, rows in credited.groupby("driver"):
        out[str(driver)] = entry(
            right=int(rows["verdict"].isin(("correct", "known_cause")).sum()),
            wrong=int((rows["verdict"] == "wrong_driver").sum()),
            missed=int((df["correct_driver"] == driver).sum()),
        )

    # a driver only ever named as the missed answer has no precision record yet
    for driver in df["correct_driver"].dropna().unique():
        if str(driver) not in out:
            out[str(driver)] = entry(0, 0, int((df["correct_driver"] == driver).sum()))

    return out


# ------------------------------------------------------------ materiality --

def suggest_thresholds(store: Store, current: float) -> dict[str, Any]:
    """
    Movements repeatedly dismissed as immaterial argue for a higher bar.

    Returned as a proposal with its evidence attached. Applying it silently
    would mean a governed threshold drifting without anyone approving it, which
    is exactly the failure the contract exists to prevent.
    """
    df = store.feedback()
    dismissed = df[df["verdict"] == MATERIALITY_SIGNAL] if not df.empty else pd.DataFrame()
    n = len(dismissed)

    if n < MIN_THRESHOLD_SAMPLES or "impact_shown" not in dismissed:
        return {"proposed": None, "current": current, "n": n,
                "note": f"{n} dismissals; {MIN_THRESHOLD_SAMPLES} needed to argue for a change"}

    impacts = dismissed["impact_shown"].dropna().abs()
    if impacts.empty:
        return {"proposed": None, "current": current, "n": n, "note": "no impacts recorded"}

    proposed = float(np.percentile(impacts, 75))
    return {
        "proposed": max(proposed, current),
        "current": current,
        "n": n,
        "applied": False,
        "note": f"75th percentile of {n} dismissed movements was {proposed:,.0f}; "
                f"raising the bar there would have suppressed three quarters of them",
    }


# ----------------------------------------------------------- known events --

def known_events(
    store: Store, iso_week: str, scope: dict[str, Any] | None = None, kpi: str | None = None
) -> list[Annotation]:
    """Annotations covering this week — what somebody already knew."""
    day = week_start(iso_week)
    return [
        a for a in store.annotations()
        if (a.kpi in (None, "", kpi) or kpi is None) and a.covers(day, scope)
    ]


# ------------------------------------------------------------ the bundle --

@dataclass
class Learning:
    calibration: Calibration
    priors: dict[str, dict[str, float]] = field(default_factory=dict)
    thresholds: dict[str, Any] = field(default_factory=dict)
    events: list[Annotation] = field(default_factory=list)

    def adjust(self, score: float) -> dict[str, Any]:
        calibrated = self.calibration.apply(score)
        return {
            "raw": round(score, 4),
            "calibrated": round(calibrated, 4),
            "shifted_by": round(calibrated - score, 4),
            "basis": self.calibration.note,
            "n": self.calibration.n,
        }

    def summary(self) -> dict[str, Any]:
        return {
            "calibration": {
                "fitted": self.calibration.fitted, "n": self.calibration.n,
                "brier_before": self.calibration.brier_before,
                "brier_after": self.calibration.brier_after,
                "improvement": self.calibration.improvement,
                "note": self.calibration.note,
            },
            "driver_priors": self.priors,
            "materiality": self.thresholds,
            "known_events": [
                {"label": a.label, "window": f"{a.starts_on} to {a.ends_on or 'open'}",
                 "scope": f"{a.dimension}={a.value}" if a.dimension else "all",
                 "expected": a.expected, "cause": a.cause}
                for a in self.events
            ],
        }


def learn(
    store: Store | None = None, kpi: str = "net_revenue", iso_week: str = "2026-W32",
    current_threshold: float = 150_000.0, scope: dict[str, Any] | None = None,
) -> Learning:
    store = store or open_store()
    return Learning(
        calibration=calibrate(store, kpi),
        priors=driver_priors(store, kpi),
        thresholds=suggest_thresholds(store, current_threshold),
        events=known_events(store, iso_week, scope, kpi),
    )


def persist(store: Store, learning: Learning, kpi: str) -> None:
    """Write the learned state back as data, so it can be read and rolled back."""
    for driver, stats in learning.priors.items():
        store.save_param("driver_prior", f"{kpi}:{driver}", stats, int(stats["n"]))
    if learning.calibration.fitted:
        store.save_param("calibration", kpi, {
            "brier_before": learning.calibration.brier_before,
            "brier_after": learning.calibration.brier_after,
        }, learning.calibration.n)
    if learning.thresholds.get("proposed"):
        store.save_param("materiality", f"{kpi}:min_impact_gbp",
                         learning.thresholds, int(learning.thresholds["n"]))


def main() -> None:
    import json

    store = open_store()
    print(f"store backend: {store.backend}\n")
    state = learn(store)
    print(json.dumps(state.summary(), indent=2, default=str))


if __name__ == "__main__":
    main()
