"""
Recommendations.

The failure mode here is arithmetic optimism: two drivers behind one cause each
claiming the whole thing, so the deck promises to recover more than was ever
lost. The first run did exactly that — 81% recoverable, of which a third was the
same money counted twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from engine.confidence import NAMED_LEVER, assess
from engine.contract import load
from engine.decompose import asp_split_by_sku, decompose
from engine.levers import CORRECTIVE, INSTRUMENTATION, allocate, recommend
from engine.warehouse import connect, narrow_scope

WEEK = "2026-W32"


@dataclass
class FakeCause:
    factor: str = "mix"
    label: str = "Basket mix"
    gbp: float = -600_000.0
    rung: int = 2
    status: str = NAMED_LEVER
    evidence: str = ""
    drivers: list[str] = field(default_factory=list)
    owner: str | None = None
    scope: dict[str, Any] | None = None


@pytest.fixture(scope="module")
def warehouse():
    return connect(), load()


@pytest.fixture(scope="module")
def recommendations(warehouse):
    con, contract = warehouse
    a = assess(con, contract, "net_revenue", WEEK)
    return recommend(con, contract, a, WEEK), a


# --------------------------------------------------------------- allocation --

def test_a_single_driver_takes_the_whole_contribution():
    cause = FakeCause(drivers=["marketing_spend"])
    assert allocate(cause, {}) == {"marketing_spend": -600_000.0}


def test_two_drivers_never_sum_to_more_than_the_cause():
    """The double-count that made the first version claim 81% recovery."""
    cause = FakeCause(drivers=["marketing_spend", "fill_rate"],
                      scope={"sku": "ELEC-002", "region": "NL"})
    splits = {"ELEC-002": {"mix": -200_000.0, "price": 0.0}}
    shares = allocate(cause, splits)

    assert sum(shares.values()) == pytest.approx(cause.gbp)
    assert shares["fill_rate"] == pytest.approx(-200_000.0)
    assert shares["marketing_spend"] == pytest.approx(-400_000.0)


def test_the_constraint_share_is_measured_not_apportioned():
    """fill_rate gets ELEC-002's own Bennet term, not a fraction of the total."""
    cause = FakeCause(drivers=["marketing_spend", "fill_rate"],
                      scope={"sku": "ELEC-002", "region": "NL"})
    shares = allocate(cause, {"ELEC-002": {"mix": -12_345.0}})
    assert shares["fill_rate"] == pytest.approx(-12_345.0)


def test_without_a_sku_scope_the_split_is_even_and_still_conserves():
    cause = FakeCause(drivers=["marketing_spend", "fill_rate"], scope=None)
    shares = allocate(cause, {})
    assert sum(shares.values()) == pytest.approx(cause.gbp)


# ------------------------------------------------------------ scope policy --

def test_a_scope_is_narrowed_to_what_a_view_can_honour():
    """Marketing spend has no SKU; asking for one is a binder error, not a filter."""
    scope = {"sku": "ELEC-002", "region": "NL"}
    assert narrow_scope("week_marketing", scope) == {"region": "NL"}
    assert narrow_scope("week_inventory", scope) == scope
    assert narrow_scope("week_rc", {"sku": "X"}) is None


# ----------------------------------------------------- the per-SKU split --

def test_per_sku_terms_sum_to_the_asp_contribution(warehouse):
    con, contract = warehouse
    splits = asp_split_by_sku(con, contract, WEEK)
    d = decompose(con, contract, WEEK)
    asp = next(c for c in d.contributions if c.factor == "asp")

    total = sum(v["price"] + v["mix"] for v in splits.values())
    assert total == pytest.approx(asp.gbp, rel=1e-6)


# ------------------------------------------------------ against the data --

def test_the_stockout_action_is_aimed_at_the_stockout(recommendations):
    recs, _ = recommendations
    fill = next(r for r in recs if r.driver == "fill_rate")
    assert "ELEC-002" in fill.action and "NL" in fill.action
    assert fill.expected_impact > 0


def test_the_campaign_action_is_not_narrowed_to_the_stockout(recommendations):
    """
    The drill located the constraint at one SKU. The campaign ran everywhere, so
    inheriting that scope pointed the lever at the wrong place — and, because
    spend is a sum with an absolute target, silently zeroed its impact.
    """
    recs, _ = recommendations
    spend = next(r for r in recs if r.driver == "marketing_spend")
    assert "ELEC-002" not in spend.action
    assert spend.expected_impact > 0


def test_recovery_never_exceeds_the_gap(recommendations):
    recs, a = recommendations
    recoverable = sum(r.expected_impact or 0 for r in recs)
    assert 0 < recoverable <= abs(a.delta)


def test_every_recommendation_carries_the_full_chain(recommendations):
    recs, _ = recommendations
    for r in recs:
        assert r.lever and r.action and r.owner and r.decision_rights
        assert 0.0 <= r.confidence <= 1.0
        assert r.monitoring.metrics and r.monitoring.horizon_days > 0
        assert r.assumptions, "an estimate with no stated assumption is a claim"


def test_the_uninstrumented_driver_gets_instrumentation_not_a_lever(recommendations):
    recs, _ = recommendations
    feed = next(r for r in recs if r.kind == INSTRUMENTATION)
    assert feed.expected_impact is None, "it recovers confidence, not revenue"
    assert feed.owner == "pricing_council"


def test_corrective_actions_all_quantify_their_impact(recommendations):
    recs, _ = recommendations
    for r in recs:
        if r.kind == CORRECTIVE:
            assert r.expected_impact is not None and r.reversal_fraction is not None
