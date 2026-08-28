"""
Rung 3 — that the ranking prefers surprise over size, and stays honest about
what it cannot rank.

The three rules under test are the ones that were wrong on the first attempt:
a slice with no baseline hijacked the ranking, a slice moving the wrong way was
treated as a cause, and the drill descended into a subtree where nothing had a
history so everything looked maximally surprising.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.attribute import (
    EXPLAINS,
    NO_BASELINE,
    OFFSETS,
    drill,
    js_contributions,
    rank_slices,
    slice_state,
)
from engine.contract import load
from engine.warehouse import connect


# ------------------------------------------------------------ divergence --

def test_identical_distributions_have_zero_surprise():
    x = np.array([100.0, 250.0, 50.0])
    assert js_contributions(x, x.copy()) == pytest.approx(np.zeros(3), abs=1e-12)


def test_proportional_movement_has_zero_surprise():
    """Everything falling by the same fraction changes no shares — no news."""
    expected = np.array([100.0, 250.0, 50.0])
    assert js_contributions(expected, expected * 0.7) == pytest.approx(np.zeros(3), abs=1e-12)


def test_surprise_is_non_negative_and_bounded():
    rng = np.random.default_rng(7)
    for _ in range(100):
        n = int(rng.integers(2, 12))
        contributions = js_contributions(rng.uniform(1, 1000, n), rng.uniform(1, 1000, n))
        assert (contributions >= -1e-12).all()
        assert contributions.sum() <= 1.0 + 1e-9      # JS in bits is bounded by 1


def test_a_small_slice_out_of_character_outranks_a_large_one_in_character():
    """The whole reason this module does not rank by size."""
    expected = np.array([1_000_000.0, 10_000.0])
    actual = np.array([700_000.0, 1_000.0])           # -30% vs -90%
    big, small = js_contributions(expected, actual)

    assert abs(actual[0] - expected[0]) > abs(actual[1] - expected[1])   # big moved more
    assert small > big                                                   # small is the story


# ------------------------------------------------------------- the rules --

def _state(rows):
    return pd.DataFrame(rows)


def test_slices_without_a_baseline_are_not_ranked():
    """Rule 1 — a new product is unknown, not surprising."""
    state = _state([
        {"slice": "OLD-1", "expected": 500.0, "actual": 400.0, "has_baseline": True},
        {"slice": "OLD-2", "expected": 500.0, "actual": 480.0, "has_baseline": True},
        {"slice": "NEW-1", "expected": np.nan, "actual": 300.0, "has_baseline": False},
    ])
    ranked = rank_slices(state, min_ep=0.02, gap_sign=1.0)

    new = ranked[ranked["slice"] == "NEW-1"].iloc[0]
    assert new["role"] == NO_BASELINE
    assert new["surprise"] == 0.0
    assert ranked.iloc[0]["slice"] != "NEW-1", "an unknown slice must not top the ranking"


def test_a_slice_moving_against_the_gap_is_an_offset():
    """Rule 2 — when revenue is down, a category that grew is not why."""
    state = _state([
        {"slice": "FELL", "expected": 1000.0, "actual": 600.0, "has_baseline": True},
        {"slice": "GREW", "expected": 1000.0, "actual": 1200.0, "has_baseline": True},
    ])
    ranked = rank_slices(state, min_ep=0.02, gap_sign=1.0)
    roles = dict(zip(ranked["slice"], ranked["role"]))

    assert roles["FELL"] == EXPLAINS
    assert roles["GREW"] == OFFSETS
    assert ranked.iloc[0]["slice"] == "FELL", "explanations rank above offsets"


def test_explanatory_power_below_the_floor_is_immaterial():
    state = _state([
        {"slice": "BIG", "expected": 1000.0, "actual": 500.0, "has_baseline": True},
        {"slice": "TINY", "expected": 100.0, "actual": 99.0, "has_baseline": True},
    ])
    ranked = rank_slices(state, min_ep=0.05, gap_sign=1.0)
    roles = dict(zip(ranked["slice"], ranked["role"]))
    assert roles["TINY"] == "immaterial"


# ------------------------------------------------------- against the data --

@pytest.fixture(scope="module")
def warehouse():
    return connect(), load()


def test_drill_finds_the_planted_stockout(warehouse):
    """
    ground_truth.yaml: STOCKOUT_ELEC_NL — ELEC-002 in NL, fill rate 0.30.

    Nothing tells the engine where to look. It must arrive there by following
    divergence down the dimensions.
    """
    con, contract = warehouse
    levels = drill(con, contract, "net_revenue", "2026-W32")
    path = {lv.dimension: lv.chosen for lv in levels if lv.chosen}

    assert path.get("sku") == "ELEC-002"
    assert path.get("region") == "NL"


def test_the_stockout_region_dominates_surprise_not_size(warehouse):
    """
    Within ELEC-002, DE has the second-largest drop and near-zero surprise —
    it fell in proportion to everything else happening in DE. NL fell out of
    all proportion. Size ranking sends you to DE; surprise sends you to NL.
    """
    con, contract = warehouse
    state = slice_state(con, contract, "net_revenue", "region", "2026-W32", {"sku": "ELEC-002"})
    ranked = rank_slices(state, min_ep=0.02, gap_sign=1.0)

    top = ranked.iloc[0]
    assert top["slice"] == "NL"
    assert top["surprise_share"] > 0.5

    de = ranked[ranked["slice"] == "DE"].iloc[0]
    assert abs(de["delta"]) > 40_000, "DE really did fall a lot"
    assert de["surprise_share"] < 0.05, "...and it is still not the story"


def test_new_sku_is_reported_but_never_chosen(warehouse):
    """HOME-NEW-01 launched seven weeks ago and outranks everything on raw
    divergence. It must appear in the table, and must not be drilled into."""
    con, contract = warehouse
    levels = drill(con, contract, "net_revenue", "2026-W32")
    first = levels[0]

    row = first.table[first.table["slice"] == "HOME-NEW-01"]
    assert len(row) == 1
    assert row.iloc[0]["role"] == NO_BASELINE
    assert first.chosen != "HOME-NEW-01"
