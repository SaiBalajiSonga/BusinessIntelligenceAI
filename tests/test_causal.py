"""
Rung 4 — the first rung that can be wrong.

Rungs 1-3 are arithmetic; if the data is right, the answer is right. This one
estimates, so the tests have to cover not just "does it find the effect" but
"does it refuse when its assumption fails" — an estimator that always returns a
number is worse than one that sometimes declines.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.causal import (
    difference_in_differences,
    find_event_week,
    find_treated_unit,
    shortlist,
    unit_panel,
)
from engine.contract import load
from engine.warehouse import connect

UNITS = ["A", "B", "C", "D", "E"]
N_WEEKS = 48
EVENT_IDX = 34


def synthetic_panel(
    effect: float = 0.0, treated: str = "A", pre_trend: float = 0.0, seed: int = 0
) -> pd.DataFrame:
    """
    A clean panel with a known effect planted, so the estimator can be checked
    against a number we chose rather than one we hope for.
    """
    rng = np.random.default_rng(seed)
    weeks = [f"2026-W{i:02d}" for i in range(1, N_WEEKS + 1)]
    level = {u: 0.028 + 0.004 * i for i, u in enumerate(UNITS)}

    rows = []
    for t, week in enumerate(weeks):
        shared = 0.0015 * np.sin(2 * np.pi * t / 26)          # a common seasonal wobble
        for u in UNITS:
            value = level[u] + shared + rng.normal(0, 0.0004)
            if u == treated:
                value += pre_trend * t                         # breaks parallel trends
                if t >= EVENT_IDX:
                    value += effect
            rows.append({"iso_week": week, "unit": u, "value": value})
    return pd.DataFrame(rows)


# ------------------------------------------------------------- estimation --

def test_did_recovers_a_planted_effect():
    panel = synthetic_panel(effect=-0.0035, treated="C", seed=1)
    est = difference_in_differences(
        panel, "C", f"2026-W{EVENT_IDX + 1:02d}", f"2026-W{N_WEEKS:02d}"
    )

    assert est.effect == pytest.approx(-0.0035, abs=3e-4)
    assert est.ci[0] < -0.0035 < est.ci[1], "the truth should sit inside the interval"
    assert est.parallel_trends_ok
    assert not est.withheld


def test_did_finds_no_effect_when_none_was_planted():
    panel = synthetic_panel(effect=0.0, treated="C", seed=2)
    est = difference_in_differences(
        panel, "C", f"2026-W{EVENT_IDX + 1:02d}", f"2026-W{N_WEEKS:02d}"
    )

    assert est.p_value > 0.05
    assert est.ci[0] < 0.0 < est.ci[1]


def test_estimate_is_withheld_when_the_pre_trend_could_explain_it():
    """
    The treated unit was already drifting before the event, by enough that the
    drift extrapolated across the post window accounts for a large share of the
    apparent effect. The right output is no number at all.
    """
    panel = synthetic_panel(effect=-0.0035, treated="C", pre_trend=-0.00008, seed=3)
    est = difference_in_differences(
        panel, "C", f"2026-W{EVENT_IDX + 1:02d}", f"2026-W{N_WEEKS:02d}"
    )

    assert est.pre_trend_per_week == pytest.approx(-0.00008, abs=3e-5)
    assert est.contamination > 0.20
    assert not est.parallel_trends_ok
    assert est.withheld


def test_a_tiny_pre_trend_does_not_block_a_large_effect():
    """
    The counterpart. A pre-trend that is statistically detectable but far too
    small to account for the effect must not veto the estimate — that is the
    whole reason the gate is contamination and not a p-value.
    """
    panel = synthetic_panel(effect=-0.0060, treated="C", pre_trend=-0.000004, seed=11)
    est = difference_in_differences(
        panel, "C", f"2026-W{EVENT_IDX + 1:02d}", f"2026-W{N_WEEKS:02d}"
    )

    assert est.contamination < 0.20
    assert not est.withheld
    assert est.effect == pytest.approx(-0.0060, abs=5e-4)


def test_a_pre_existing_trend_is_not_reported_as_an_effect():
    """Drift with no event at all must not be sold as a causal finding."""
    panel = synthetic_panel(effect=0.0, treated="C", pre_trend=-0.00008, seed=4)
    est = difference_in_differences(
        panel, "C", f"2026-W{EVENT_IDX + 1:02d}", f"2026-W{N_WEEKS:02d}"
    )
    assert est.withheld


# --------------------------------------------------------------- discovery --

def test_treated_unit_is_discovered_not_assumed():
    panel = synthetic_panel(effect=-0.006, treated="D", seed=5)
    assert find_treated_unit(panel) == "D"


def test_discovery_is_not_fooled_by_the_smallest_unit():
    """
    Unit A has the lowest level throughout and never moves; unit E is largest
    and is the one that breaks. Normalising against each unit's own history is
    what stops 'smallest' being mistaken for 'changed'.
    """
    panel = synthetic_panel(effect=-0.008, treated="E", seed=6)
    assert find_treated_unit(panel) == "E"


def test_event_week_is_located_near_the_true_changepoint():
    panel = synthetic_panel(effect=-0.006, treated="C", seed=7)
    found = find_event_week(panel, "C")
    found_idx = int(found.split("W")[1])
    assert abs(found_idx - (EVENT_IDX + 1)) <= 2


# -------------------------------------------------------- against the data --

@pytest.fixture(scope="module")
def warehouse():
    return connect(), load()


def test_uninstrumented_driver_is_named_not_dropped(warehouse):
    """
    The contract declares competitor pricing with no source. It must still be
    listed — otherwise the effect it causes gets silently attributed to
    whichever observable driver happened to correlate.
    """
    con, contract = warehouse
    signals = {s.driver: s for s in shortlist(con, contract, "net_revenue")}

    assert "competitor_price_index" in signals
    assert signals["competitor_price_index"].observable is False
    assert signals["competitor_price_index"].correlation is None


def test_recovers_the_planted_competitor_effect(warehouse):
    """
    ground_truth.yaml: COMPETITOR_DE — conversion x0.88 in DE from 2026-07-20,
    which is 2026-W30. Region, week and magnitude are all discovered.
    """
    con, contract = warehouse
    panel = unit_panel(con, contract, "conversion_rate", "region")

    treated = find_treated_unit(panel)
    assert treated == "DE"

    event = find_event_week(panel, treated)
    assert event == "2026-W30"

    est = difference_in_differences(panel, treated, event, "2026-W32")
    assert est.parallel_trends_ok
    assert not est.withheld
    assert est.relative == pytest.approx(-0.12, abs=0.02)   # planted: -12%
    assert est.ci[0] < est.effect < est.ci[1]


def test_the_real_pre_trend_is_detectable_but_immaterial(warehouse):
    """
    DE does carry a faint upward drift before the event — real enough to reach
    p<0.05 on a 26-week window, and pointing the OPPOSITE way to the effect.
    Judged on contamination it is irrelevant, which is the correct reading.
    """
    con, contract = warehouse
    panel = unit_panel(con, contract, "conversion_rate", "region")
    est = difference_in_differences(panel, "DE", "2026-W30", "2026-W32")

    assert est.pre_trend_per_week > 0, "drift is upward"
    assert est.effect < 0, "the effect is downward"
    assert est.contamination < 0.05, "it cannot account for the effect"
