"""
The numeric guard.

Two ways this component can fail, and both are tested here. If it misses an
invented figure it is decoration. If it flags legitimate rounding it will be
switched off within a day, which is the same outcome by a slower route.
"""

from __future__ import annotations

import pytest

from narrative.validator import (
    evidence_values,
    extract_figures,
    renderings,
    validate,
)

EVIDENCE = {
    "kpi": "net_revenue",
    "week": "2026-W32",
    "gap": -881627.0,
    "confidence": {"score": 0.672, "band": "qualified"},
    "drivers": [
        {"label": "Basket mix", "gbp": -610954.0},
        {"label": "Price changes", "gbp": -124018.0},
        {"label": "Conversion", "gbp": -201694.0},
    ],
}


# ----------------------------------------------------------- extraction --

@pytest.mark.parametrize("text,expected", [
    ("a gap of -881,627 GBP", -881627.0),
    ("£610,954 lower", 610954.0),
    ("confidence 0.672", 0.672),
    ("down 12.5%", 12.5),
    ("roughly 881.6K", 881600.0),
    ("about 0.88 million", 880000.0),
])
def test_figures_are_extracted_with_scale(text, expected):
    figures = extract_figures(text)
    assert figures, f"nothing extracted from {text!r}"
    assert figures[0].value == pytest.approx(expected)


def test_percent_is_flagged():
    assert extract_figures("down 12.5%")[0].is_percent
    assert not extract_figures("down 12.5 points")[0].is_percent


def test_evidence_values_walks_nested_structures():
    """Values keep their sign here; matching compares on magnitude."""
    values = evidence_values(EVIDENCE)
    magnitudes = {abs(v) for v in values}
    for v in (881627.0, 610954.0, 124018.0, 201694.0, 0.672):
        assert v in magnitudes
    assert 2026.0 in values and 32.0 in values, "ISO week parts must be allowed"


def test_renderings_cover_scaled_forms():
    r = renderings(-881627.0)
    assert 881627.0 in r
    assert any(x == pytest.approx(881.627) for x in r)      # thousands
    assert any(x == pytest.approx(0.881627) for x in r)     # millions


# ------------------------------------------------------------- it passes --

def test_faithful_prose_passes():
    text = ("Net revenue fell 881,627 GBP in 2026-W32, driven by basket mix at "
            "-610,954 and price changes at -124,018. Confidence is 0.672.")
    assert validate(text, EVIDENCE).ok


def test_rounding_is_allowed():
    text = "Revenue fell about 881.6K, with basket mix contributing -0.61 million."
    v = validate(text, EVIDENCE)
    assert v.ok, v.report()


def test_a_ratio_may_be_rendered_as_a_percentage():
    """0.672 in the evidence, '67.2%' in the prose — the same fact."""
    assert validate("Confidence stands at 67.2%.", EVIDENCE).ok


def test_small_integers_and_dates_do_not_trip_it():
    text = "Three drivers explain the 2026-W32 gap of 881,627; 2 are controllable."
    assert validate(text, EVIDENCE).ok


# ------------------------------------------------------------- it catches --

def test_an_invented_figure_is_caught():
    text = "Net revenue fell 881,627 GBP, and margin compressed by 4.2 points."
    v = validate(text, EVIDENCE)
    assert not v.ok
    assert any("4.2" in f.raw for f in v.violations)


def test_a_transposed_digit_is_caught():
    """818,627 instead of 881,627 — the failure a human reader would miss."""
    v = validate("Net revenue fell 818,627 GBP.", EVIDENCE)
    assert not v.ok
    assert len(v.violations) == 1


def test_a_plausible_but_uncomputed_total_is_caught():
    """
    -610,954 + -124,018 = -734,972, which is a real number from the analytics —
    but it is NOT in this evidence object, so the model must not produce it.
    """
    v = validate("Mix and price together account for 734,972.", EVIDENCE)
    assert not v.ok


def test_a_wrong_percentage_is_caught():
    v = validate("Confidence stands at 82.0%.", EVIDENCE)
    assert not v.ok


def test_report_names_the_offending_figures():
    v = validate("Revenue fell 881,627 but churn rose 14.7%.", EVIDENCE)
    assert not v.ok
    assert "14.7%" in v.report()


def test_tolerance_is_tight_enough_to_matter():
    """A 1% error is invention, not rounding."""
    assert not validate("Revenue fell 890,000 GBP.", EVIDENCE).ok


# ------------------------------------------- regression: prose-borne figures --

PROSE_EVIDENCE = {
    "week": "2026-W32",
    "gap": -881627.0,
    "drivers": [{
        "label": "Price changes",
        "gbp": -124018.0,
        # the analytics supplies its justification as a sentence, and every
        # figure inside it is evidence the narrative is entitled to quote
        "evidence": "Discount depth in DE/FR Home & Garden 0.2585 vs 0.0924 "
                    "expected (+180%)",
    }],
    "would_raise_confidence": ["inventory is 72h stale against a 24h SLA"],
}


def test_figures_inside_evidence_prose_are_allowed():
    """
    The false positive that pushed two of three personas to the template
    fallback: the model quoted numbers we handed it inside a justification
    string, and the guard called them inventions.
    """
    text = ("Price changes cost 124,018, with discount depth at 0.2585 against "
            "0.0924 expected, 180% deeper than planned.")
    v = validate(text, PROSE_EVIDENCE)
    assert v.ok, v.report()


def test_a_percentage_in_prose_also_licenses_its_ratio():
    assert validate("Discounts ran 1.80 times expected depth.", PROSE_EVIDENCE).ok


def test_staleness_hours_quoted_from_prose_are_allowed():
    assert validate("Inventory was 72h stale against a 24h SLA.", PROSE_EVIDENCE).ok


def test_widening_to_prose_does_not_admit_inventions():
    """The guard must still catch a figure that appears nowhere at all."""
    v = validate("Price changes cost 124,018 and margin fell 6.3 points.", PROSE_EVIDENCE)
    assert not v.ok
    assert any("6.3" in f.raw for f in v.violations)
