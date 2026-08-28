"""
The learning loop.

A feedback loop is only real if a later run behaves differently because of it,
and the difference is inspectable. These tests use an in-memory store so they
assert on a known history rather than on whatever has accumulated locally.
"""

from __future__ import annotations

from datetime import date

import duckdb
import numpy as np
import pytest

from feedback.learn import (
    MIN_CALIBRATION_SAMPLES,
    brier,
    calibrate,
    driver_priors,
    known_events,
    suggest_thresholds,
    week_start,
)
from feedback.seed import DRIVER_RELIABILITY, seed
from feedback.store import Annotation, DuckDBStore, Feedback


@pytest.fixture
def store():
    return DuckDBStore(duckdb.connect(":memory:"))


@pytest.fixture
def seeded(store):
    seed(store)
    return store


# ---------------------------------------------------------------- records --

def test_a_bad_verdict_is_refused():
    with pytest.raises(ValueError, match="verdict must be one of"):
        Feedback(kpi="net_revenue", iso_week="2026-W32", persona="cfo", verdict="meh")


def test_feedback_round_trips(store):
    store.record_feedback(Feedback(
        kpi="net_revenue", iso_week="2026-W32", persona="analyst",
        verdict="wrong_driver", driver="marketing_spend",
        correct_driver="fill_rate", confidence_shown=0.7,
    ))
    df = store.feedback("net_revenue")
    assert len(df) == 1
    assert df.iloc[0]["correct_driver"] == "fill_rate"


def test_week_start_resolves_iso_weeks():
    assert week_start("2026-W32") == date(2026, 8, 3)
    with pytest.raises(ValueError):
        week_start("August")


# ------------------------------------------------------------ annotations --

def test_an_annotation_covers_only_its_window():
    ann = Annotation(label="Campaign", starts_on="2026-07-13", ends_on="2026-08-23")
    assert ann.covers(date(2026, 8, 3))
    assert not ann.covers(date(2026, 7, 1))
    assert not ann.covers(date(2026, 9, 1))


def test_an_open_ended_annotation_has_no_end():
    ann = Annotation(label="Ongoing", starts_on="2026-01-01")
    assert ann.covers(date(2030, 1, 1))


def test_an_annotation_respects_its_dimension(store):
    ann = Annotation(label="Beauty push", starts_on="2026-07-13", ends_on="2026-08-23",
                     dimension="category", value="Beauty")
    assert ann.covers(date(2026, 8, 3), {"category": "Beauty"})
    assert not ann.covers(date(2026, 8, 3), {"category": "Electronics"})


def test_known_events_finds_the_seeded_windows(seeded):
    events = known_events(seeded, "2026-W32", kpi="net_revenue")
    labels = {e.label for e in events}
    assert "Beauty entry-price campaign" in labels
    assert "ELEC-002 supplier delay" in labels


def test_known_events_is_empty_outside_the_windows(seeded):
    assert known_events(seeded, "2026-W02", kpi="net_revenue") == []


# ------------------------------------------------------------ calibration --

def test_calibration_refuses_to_fit_on_too_little(store):
    for i in range(MIN_CALIBRATION_SAMPLES - 1):
        store.record_feedback(Feedback(
            kpi="net_revenue", iso_week="2026-W10", persona="analyst",
            verdict="correct", confidence_shown=0.5 + i * 0.01,
        ))
    cal = calibrate(store, "net_revenue")
    assert not cal.fitted
    assert "needed" in cal.note
    assert cal.apply(0.8) == 0.8, "an unfitted calibrator must be the identity"


def test_calibration_recovers_a_planted_overconfidence(seeded):
    """
    The seed plants true_rate = claimed ** 1.6 — the engine is systematically
    overconfident. The loop should find it and the forecast should improve.
    """
    cal = calibrate(seeded, "net_revenue")
    assert cal.fitted
    assert cal.brier_after < cal.brier_before
    assert cal.improvement > 0.02


def test_calibration_pulls_an_overconfident_score_down(seeded):
    cal = calibrate(seeded, "net_revenue")
    assert cal.apply(0.85) < 0.85


def test_brier_rewards_a_better_forecast():
    outcomes = np.array([1.0, 1.0, 0.0, 0.0])
    assert brier(np.array([0.9, 0.9, 0.1, 0.1]), outcomes) < \
           brier(np.array([0.5, 0.5, 0.5, 0.5]), outcomes)


# ---------------------------------------------------------- driver priors --

def test_priors_are_precision_not_popularity(store):
    """
    The bug this guards: a driver credited wrongly more often than rightly was
    scoring 1.33, because the count of times it was named as the MISSED cause
    was being folded into the same ratio.
    """
    for _ in range(7):
        store.record_feedback(Feedback(kpi="k", iso_week="2026-W01", persona="a",
                                       verdict="correct", driver="X"))
    for _ in range(8):
        store.record_feedback(Feedback(kpi="k", iso_week="2026-W01", persona="a",
                                       verdict="wrong_driver", driver="X",
                                       correct_driver="X"))
    priors = driver_priors(store, "k")
    assert priors["X"]["weight"] < 1.0, "more wrong than right must not score above 1"
    assert priors["X"]["missed_by_engine"] == 8, "the signal is kept, just kept separate"


def test_priors_recover_the_planted_reliability_order(seeded):
    priors = driver_priors(seeded, "net_revenue")
    got = [d for d, _ in sorted(priors.items(), key=lambda kv: -kv[1]["weight"])]
    want = [d for d, _ in sorted(DRIVER_RELIABILITY.items(), key=lambda kv: -kv[1])]
    assert got == want


def test_the_uninstrumented_driver_is_the_least_trusted(seeded):
    priors = driver_priors(seeded, "net_revenue")
    assert priors["competitor_price_index"]["weight"] < 1.0
    assert priors["discount_depth"]["weight"] > 1.0


def test_weights_are_clipped_so_the_loop_cannot_overturn_the_arithmetic(seeded):
    for stats in driver_priors(seeded, "net_revenue").values():
        assert 0.5 <= stats["weight"] <= 1.5


# ------------------------------------------------------------ materiality --

def test_threshold_change_needs_evidence(store):
    out = suggest_thresholds(store, current=150_000)
    assert out["proposed"] is None
    assert "needed" in out["note"]


def test_repeated_dismissals_argue_for_a_higher_bar(seeded):
    out = suggest_thresholds(seeded, current=150_000)
    assert out["proposed"] > 150_000
    assert out["n"] >= 5


def test_a_threshold_is_proposed_never_applied(seeded):
    """A governed threshold that moves on its own has stopped being governed."""
    out = suggest_thresholds(seeded, current=150_000)
    assert out["applied"] is False


# ------------------------------------------------------------- persistence --

def test_learned_state_is_stored_as_readable_data(store):
    store.save_param("driver_prior", "net_revenue:fill_rate", {"weight": 1.2}, 13)
    params = store.params("driver_prior")
    assert params["net_revenue:fill_rate"]["weight"] == 1.2
    assert params["net_revenue:fill_rate"]["n"] == 13
