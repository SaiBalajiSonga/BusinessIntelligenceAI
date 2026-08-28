"""
The claim Rungs 1-2 rest on: the parts add up to the whole, exactly.

If these fail, every number the narrative layer quotes is suspect — so this is
the test that guards the "we compute it exactly, so it cannot be wrong" line in
the pitch. Property tests over random inputs, then the same assertion against
the real warehouse.

    .venv/bin/pytest tests/ -q
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from engine.contract import load
from engine.decompose import bennet_asp, decompose, lmdi, log_mean
from engine.warehouse import connect, view_named

TOL = 1e-6


# ------------------------------------------------------------------- LMDI --

def test_log_mean_handles_equal_values():
    """L(a,a) = a — the limit, not a division by zero."""
    assert log_mean(5.0, 5.0) == pytest.approx(5.0)


@pytest.mark.parametrize("trial", range(200))
def test_lmdi_contributions_sum_to_delta(trial: int):
    """
    The whole point of LMDI over hold-one-constant attribution: no residual.
    """
    rng = np.random.default_rng(trial)
    n = int(rng.integers(2, 6))

    expected = {f"x{i}": float(rng.uniform(0.05, 5_000)) for i in range(n)}
    actual = {k: v * float(rng.uniform(0.4, 2.5)) for k, v in expected.items()}

    parts = lmdi(expected, actual)
    delta = math.prod(actual.values()) - math.prod(expected.values())

    assert sum(parts.values()) == pytest.approx(delta, rel=TOL, abs=TOL)


def test_lmdi_attributes_a_single_moving_factor_entirely_to_it():
    expected = {"a": 100.0, "b": 4.0, "c": 0.5}
    actual = dict(expected, b=6.0)
    parts = lmdi(expected, actual)

    assert parts["a"] == pytest.approx(0.0, abs=TOL)
    assert parts["c"] == pytest.approx(0.0, abs=TOL)
    assert parts["b"] == pytest.approx(200.0 * 6 / 4 - 200.0, rel=1e-3)


# ----------------------------------------------------------------- Bennet --

@pytest.mark.parametrize("trial", range(200))
def test_bennet_price_plus_mix_equals_delta_asp(trial: int):
    rng = np.random.default_rng(1000 + trial)
    n = int(rng.integers(2, 25))

    exp_q = pd.Series(rng.uniform(1, 5_000, n))
    exp_p = pd.Series(rng.uniform(5, 250, n))
    act_q = exp_q * rng.uniform(0.3, 3.0, n)
    act_p = exp_p * rng.uniform(0.6, 1.6, n)

    price, mix = bennet_asp(exp_q, exp_p, act_q, act_p)

    asp0 = float((exp_q * exp_p).sum() / exp_q.sum())
    asp1 = float((act_q * act_p).sum() / act_q.sum())

    assert price + mix == pytest.approx(asp1 - asp0, rel=TOL, abs=TOL)


def test_pure_mix_shift_registers_as_mix_not_price():
    """Every price identical and unchanged; only the basket moves."""
    exp_q = pd.Series([100.0, 100.0])
    act_q = pd.Series([10.0, 190.0])
    prices = pd.Series([10.0, 50.0])

    price, mix = bennet_asp(exp_q, prices, act_q, prices)

    # asp0 = (100*10 + 100*50)/200 = 30
    # asp1 = ( 10*10 + 190*50)/200 = 48
    assert price == pytest.approx(0.0, abs=TOL)
    assert mix == pytest.approx(48.0 - 30.0, rel=1e-9)


def test_pure_price_change_registers_as_price_not_mix():
    """Basket frozen; only prices move."""
    q = pd.Series([100.0, 100.0])
    exp_p = pd.Series([10.0, 50.0])
    act_p = pd.Series([12.0, 55.0])

    price, mix = bennet_asp(q, exp_p, q, act_p)

    assert mix == pytest.approx(0.0, abs=TOL)
    assert price == pytest.approx(33.5 - 30.0, rel=1e-9)


# ------------------------------------------------------- against real data --

@pytest.fixture(scope="module")
def warehouse():
    return connect(), load()


def test_kpi_identity_holds_in_the_warehouse(warehouse):
    """
    sessions * conversion * units_per_order * asp == net_revenue, every week.

    The generator builds top-down so this holds by construction. If it ever
    breaks, the data is wrong — not the maths.
    """
    con, _ = warehouse
    worst = con.sql(f"""
        WITH w AS (
            SELECT iso_week,
                   sum(sessions)    AS s,
                   sum(orders)      AS o,
                   sum(units)       AS u,
                   sum(net_revenue) AS r
            FROM {view_named('week_rc')}
            GROUP BY iso_week
        )
        SELECT max(abs(
            s * (o::DOUBLE / s) * (u / o) * (r / u) - r
        )) FROM w
    """).fetchone()[0]
    assert worst < 0.01


def test_real_decomposition_leaves_no_residual(warehouse):
    con, contract = warehouse
    d = decompose(con, contract, "2026-W32")
    assert d.explained == pytest.approx(d.delta, abs=0.01)


def test_asp_children_sum_to_their_parent(warehouse):
    """Rung 2 refines Rung 1's ASP term — it must not change its total."""
    con, contract = warehouse
    d = decompose(con, contract, "2026-W32")
    asp = next(c for c in d.contributions if c.factor == "asp")

    assert asp.children, "expected a price/mix split under ASP"
    assert sum(c.gbp for c in asp.children) == pytest.approx(asp.gbp, abs=0.01)


def test_decomposition_recovers_the_planted_effects(warehouse):
    """
    Ground truth says a Beauty mix shift and a Home & Garden discount were
    injected. Both must land in the right term with the right sign.
    """
    con, contract = warehouse
    d = decompose(con, contract, "2026-W32")
    asp = next(c for c in d.contributions if c.factor == "asp")
    by_name = {c.factor: c.gbp for c in asp.children}

    assert by_name["mix"] < -100_000, "MIX_SHIFT_BEAUTY should dominate the ASP gap"
    assert by_name["price"] < -20_000, "DISCOUNT_HG_DE_FR should show as a price effect"

    conversion = next(c for c in d.contributions if c.factor == "conversion_rate")
    assert conversion.gbp < -50_000, "COMPETITOR_DE should suppress conversion"
