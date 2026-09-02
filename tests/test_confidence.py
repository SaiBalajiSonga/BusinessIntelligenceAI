"""
Rung 5 — that the score is honest about what is actually known.

The failure this guards against is the tempting one: LMDI accounts for every
pound of the gap, so it is easy to build a system that always reports full
coverage and high confidence while having explained nothing. Coverage here must
fall when causes are unnamed, and the gate must actually close.
"""

from __future__ import annotations

import duckdb
import pytest

from engine.confidence import (
    ABSTAIN,
    CREDIT,
    LOCALISED,
    NAMED_CONSTRAINT,
    NAMED_LEVER,
    QUALIFIED,
    UNATTRIBUTED,
    Cause,
    assess,
    driver_moved,
)
from engine.contract import load
from engine.warehouse import connect
from feedback.learn import learn, persist
from feedback.store import DuckDBStore, Feedback

WEEK = "2026-W32"


@pytest.fixture(scope="module")
def warehouse():
    return connect(), load()


@pytest.fixture(scope="module")
def headline(warehouse):
    con, contract = warehouse
    return assess(con, contract, "net_revenue", WEEK)


# ------------------------------------------------------------ the credits --

def test_a_localised_cause_earns_only_half_credit():
    """Knowing a shock hit DE in W30 is worth something, and is not an answer."""
    assert CREDIT[LOCALISED] == 0.5
    assert CREDIT[NAMED_LEVER] == 1.0
    assert CREDIT[NAMED_CONSTRAINT] == 1.0
    assert CREDIT[UNATTRIBUTED] == 0.0


def test_cause_exposes_its_credit():
    c = Cause("conversion_rate", "Conversion", -200_000, 1, LOCALISED, "…")
    assert c.credit == 0.5


# ------------------------------------------------------- driver detection --

def test_driver_moved_finds_the_planted_discount(warehouse):
    """ground_truth: DISCOUNT_HG_DE_FR pushed depth from ~7.5% to ~26%."""
    con, contract = warehouse
    moved, rel, evidence = driver_moved(
        con, contract, "discount_depth", WEEK,
        {"region": ["DE", "FR"], "category": "Home & Garden"},
    )
    assert moved
    assert rel > 1.0                      # more than doubled versus expectation
    assert "Discount depth" in evidence


def test_driver_moved_reports_an_uninstrumented_driver_as_such(warehouse):
    con, contract = warehouse
    moved, rel, evidence = driver_moved(con, contract, "competitor_price_index", WEEK)
    assert not moved
    assert evidence == "not instrumented"


def test_a_quiet_driver_does_not_register(warehouse):
    """Marketing spend at the total level, in a week with no campaign change,
    should not be offered as a cause."""
    con, contract = warehouse
    moved, _, _ = driver_moved(con, contract, "marketing_spend", "2026-W20")
    assert not moved


# ------------------------------------------------------------- the gate --

def test_sparse_history_abstains_and_says_why(warehouse):
    con, contract = warehouse
    a = assess(con, contract, "net_revenue", WEEK, {"sku": "HOME-NEW-01"})

    assert a.band == ABSTAIN
    assert "LLM not called" in a.action
    assert a.delta is None
    assert any("104" in m for m in a.missing), "must name what is missing"


def test_a_kpi_without_a_decomposition_is_refused(warehouse):
    con, contract = warehouse
    with pytest.raises(ValueError, match="no decomposition"):
        assess(con, contract, "fill_rate", WEEK)


def test_coverage_is_not_one_despite_lmdi_being_exact(headline):
    """
    The whole point. The decomposition accounts for 100% of the gap, so a naive
    coverage measure would read 1.0 and the engine would always be confident.
    """
    assert headline.coverage < 0.95
    assert headline.coverage > 0.5


def test_unattributed_terms_drag_coverage_down(headline):
    unattributed = [c for c in headline.causes if c.status == UNATTRIBUTED]
    assert unattributed, "W32 has terms with no identified driver"

    gross = sum(abs(c.gbp) for c in headline.causes)
    lost = sum(abs(c.gbp) for c in unattributed) / gross
    assert headline.coverage <= 1.0 - lost + 1e-9


def test_score_is_the_weighted_sum_of_its_components(headline, warehouse):
    _, contract = warehouse
    weights = contract.confidence["weights"]
    expected = sum(weights[k] * v for k, v in headline.components.items())
    assert headline.score == pytest.approx(expected, abs=1e-9)


def test_the_multi_factor_week_is_qualified_not_confident(headline):
    """
    Nineteen percent of the gap has no named cause and the ops source is stale.
    Confident would be overclaiming.
    """
    assert headline.band == QUALIFIED
    assert headline.action.startswith("narrate with caveats")


def test_the_uninstrumented_driver_is_named_in_what_would_help(headline):
    assert any("competitor pricing" in m.lower() for m in headline.missing)


def test_stale_source_is_named_in_what_would_help(headline):
    assert any("stale" in m for m in headline.missing)


# --------------------------------------------------- the feedback loop closes --

def test_repeated_wrong_driver_feedback_lowers_a_later_assessment(warehouse, headline):
    """
    The claim Fix 1 rests on: a driver an analyst has repeatedly marked wrong
    must score measurably lower on a LATER run, not just get recorded. Without
    `assess(..., store=...)` reading back the persisted priors, this is the
    exact scenario that silently does nothing.
    """
    con, contract = warehouse

    # W32's "price" factor is credited to discount_depth as a NAMED_LEVER —
    # confirmed by test_driver_moved_finds_the_planted_discount above.
    before = next(c for c in headline.causes if "discount_depth" in c.drivers)
    assert before.status == NAMED_LEVER
    assert before.learned_weight == 1.0
    assert before.effective_credit == before.credit == 1.0

    store = DuckDBStore(duckdb.connect(":memory:"))
    for _ in range(20):
        store.record_feedback(Feedback(
            kpi="net_revenue", iso_week=WEEK, persona="analyst",
            verdict="wrong_driver", driver="discount_depth",
            correct_driver="fill_rate", confidence_shown=headline.score,
        ))

    state = learn(store, kpi="net_revenue", iso_week=WEEK)
    assert state.priors["discount_depth"]["weight"] < 1.0, \
        "20 wrong_driver verdicts and no correct ones must not leave the prior at 1.0"
    persist(store, state, "net_revenue")

    adjusted = assess(con, contract, "net_revenue", WEEK, store=store)
    after = next(c for c in adjusted.causes if "discount_depth" in c.drivers)

    assert after.learned_weight < 1.0
    assert after.effective_credit < before.credit
    assert adjusted.coverage < headline.coverage
    assert adjusted.score < headline.score, \
        "a driver with a history of being wrong must measurably lower a later assessment"


def test_a_store_with_no_feedback_changes_nothing(warehouse, headline):
    """The identity path: an empty store must reproduce the unlearned score."""
    con, contract = warehouse
    store = DuckDBStore(duckdb.connect(":memory:"))
    same = assess(con, contract, "net_revenue", WEEK, store=store)
    assert same.score == pytest.approx(headline.score)
    assert same.calibration_applied is False


def test_calibration_curve_is_persisted_and_reapplied_without_the_model(warehouse):
    """
    `persist()` must save enough of the fitted isotonic curve that a fresh
    process — which never sees the sklearn model object — can still apply it
    by reading the store, the way `engine.confidence.assess` does in production.
    """
    from feedback.seed import seed

    con, contract = warehouse
    store = DuckDBStore(duckdb.connect(":memory:"))
    seed(store)  # plants a known overconfidence and enough rows to fit

    state = learn(store, kpi="net_revenue", iso_week=WEEK)
    assert state.calibration.fitted
    persist(store, state, "net_revenue")

    calib_param = store.params("calibration")["net_revenue"]
    assert calib_param["x_thresholds"] and calib_param["y_thresholds"]

    a = assess(con, contract, "net_revenue", WEEK, store=store)
    assert a.calibration_applied is True
    assert a.score < a.raw_score, "the planted overconfidence must pull the calibrated score down"
