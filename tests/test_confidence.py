"""
Rung 5 — that the score is honest about what is actually known.

The failure this guards against is the tempting one: LMDI accounts for every
pound of the gap, so it is easy to build a system that always reports full
coverage and high confidence while having explained nothing. Coverage here must
fall when causes are unnamed, and the gate must actually close.
"""

from __future__ import annotations

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
