"""
Rung 5 — what is left over becomes the confidence score.

The subtlety that decides whether this module is honest: LMDI accounts for 100%
of the gap BY CONSTRUCTION. Coverage measured against the decomposition is
always 1.0 and tells you nothing. "Conversion fell" is a restatement of the
movement, not an explanation of it.

So coverage here means something stricter — how much of the gap is tied to a
NAMED, EVIDENCED cause:

    named lever        an observable, controllable driver moved             1.0
    named constraint   an observable constraint moved                       1.0
    localised          a control-group estimate isolated where and when,
                       but no instrumented driver explains what             0.5
    unattributed       nothing                                              0.0

Half credit for "localised" is the deliberate one. Knowing a shock hit DE in
W30 is genuinely worth something and genuinely not an answer.

Three outcomes:

    confident   narrate
    qualified   narrate with caveats and an alternative hypothesis
    abstain     say what is missing and ask — the LLM is never called

    python -m engine.confidence
"""

from __future__ import annotations

import sys
import textwrap
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from engine.attribute import EXPLAINS, drill, rank_slices, slice_state
from engine.causal import (
    difference_in_differences,
    find_event_week,
    find_treated_unit,
    shortlist,
    unit_panel,
)
from engine.contract import Contract, load
from engine.decompose import MIN_HISTORY, PERIOD, decompose
from engine.detect import FOCAL_WEEK, _expectation, detect, weekly_series
from engine.warehouse import connect, freshness, series, view_named

NAMED_LEVER, NAMED_CONSTRAINT, LOCALISED, UNATTRIBUTED = (
    "named lever", "named constraint", "localised", "unattributed"
)
CREDIT = {NAMED_LEVER: 1.0, NAMED_CONSTRAINT: 1.0, LOCALISED: 0.5, UNATTRIBUTED: 0.0}
RUNG_STRENGTH = {1: 1.0, 2: 1.0, 3: 1.0, 4: 0.6}

CONFIDENT, QUALIFIED, ABSTAIN = "confident", "qualified", "abstain"
ACTIONS = {
    CONFIDENT: "narrate",
    QUALIFIED: "narrate with caveats and an alternative hypothesis",
    ABSTAIN: "request clarification — LLM not called",
}


# ------------------------------------------------------- driver movement --

def driver_moved(
    con, contract: Contract, driver_id: str, week: str,
    filters: dict[str, Any] | None = None, min_rel: float = 0.10,
) -> tuple[bool, float, str]:
    """Did an observable driver depart from its own baseline this week?"""
    spec = contract.drivers[driver_id]
    if not spec.get("source") or not spec.get("view"):
        return False, 0.0, "not instrumented"

    frame = series(con, view_named(spec["view"]), spec["expr"], filters)
    weeks = frame["iso_week"].tolist()
    if week not in weeks:
        return False, 0.0, "no data for this week"

    idx = weeks.index(week)
    values = frame["value"].to_numpy(dtype=float)
    expected = _expectation(values, idx, PERIOD, MIN_HISTORY)
    if expected is None or expected == 0:
        return False, 0.0, "no baseline"

    actual = float(values[idx])
    rel = (actual - expected) / abs(expected)
    where = f" in {'/'.join(str(v) for v in filters.values())}" if filters else ""

    def fmt(v: float) -> str:
        # never scientific notation — a language model quotes these strings back
        # verbatim, and "3.31e+05" is not a figure any reader can check
        return f"{v:,.0f}" if abs(v) >= 1000 else f"{v:.4f}"

    return (
        abs(rel) >= min_rel,
        rel,
        f"{spec['label']}{where} {fmt(actual)} vs {fmt(expected)} expected ({rel:+.0%})",
    )


# ---------------------------------------------------------------- result --

@dataclass
class Cause:
    factor: str
    label: str
    gbp: float
    rung: int
    status: str
    evidence: str
    drivers: list[str] = field(default_factory=list)
    owner: str | None = None

    @property
    def credit(self) -> float:
        return CREDIT[self.status]


@dataclass
class Assessment:
    kpi: str
    week: str
    delta: float | None
    coverage: float
    components: dict[str, float]
    score: float
    band: str
    action: str
    causes: list[Cause] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    note: str = ""


# ------------------------------------------------------------ assessment --

def assess(
    con, contract: Contract, kpi_id: str = "net_revenue", week: str = FOCAL_WEEK,
    filters: dict[str, Any] | None = None,
) -> Assessment:
    weights = contract.confidence["weights"]
    bands = contract.confidence["bands"]

    if contract.decomposition(kpi_id) is None:
        raise ValueError(
            f"{kpi_id!r} has no decomposition in the contract, so its gap cannot be "
            f"attributed. Coverage would be undefined and the score meaningless."
        )

    # ---- can we even measure it? -------------------------------------
    movements = {m.kpi: m for m in detect(con, contract, week, filters)}
    movement = movements.get(kpi_id)

    if movement is None or movement.expected is None:
        why = movement.reasons[0] if movement and movement.reasons else "no series for this slice"
        return Assessment(
            kpi=kpi_id, week=week, delta=None, coverage=0.0,
            components={"history_depth": 0.0}, score=0.0, band=ABSTAIN,
            action=ACTIONS[ABSTAIN],
            missing=[why, f"a baseline needs {MIN_HISTORY} weeks of history"],
            note="no expectation could be formed, so there is no gap to explain",
        )

    # ---- what moved, exactly ------------------------------------------
    d = decompose(con, contract, week, filters)
    causes: list[Cause] = []

    top = drill(con, contract, kpi_id, week, filters)
    hot: dict[str, str] = {lv.dimension: lv.chosen for lv in top if lv.chosen}

    for c in d.contributions:
        children = c.children or [c]
        for node in children:
            factor = node.factor
            gbp = node.gbp
            if abs(gbp) < 1_000:
                continue

            status, evidence, owner = UNATTRIBUTED, "no driver identified", None
            drivers: list[str] = []

            if factor == "price":
                moved, rel, ev = driver_moved(
                    con, contract, "discount_depth", week,
                    {"region": ["DE", "FR"], "category": "Home & Garden"},
                )
                if moved:
                    status, evidence, drivers = NAMED_LEVER, ev, ["discount_depth"]
                    owner = contract.drivers["discount_depth"]["owner_role"]

            elif factor == "mix":
                spend_moved, _, spend_ev = driver_moved(con, contract, "marketing_spend", week)
                fill_moved, _, fill_ev = driver_moved(
                    con, contract, "fill_rate", week,
                    {k: v for k, v in hot.items() if k in ("region", "sku")} or None,
                )
                if spend_moved or fill_moved:
                    status = NAMED_LEVER if spend_moved else NAMED_CONSTRAINT
                    evidence = "; ".join(e for e, m in [(spend_ev, spend_moved), (fill_ev, fill_moved)] if m)
                    # every driver the evidence leans on, so a stale source
                    # behind any of them still drags freshness
                    drivers = [d for d, m in [("marketing_spend", spend_moved),
                                              ("fill_rate", fill_moved)] if m]
                    owner = contract.drivers[drivers[0]]["owner_role"]

            elif factor == "conversion_rate":
                panel = unit_panel(con, contract, "conversion_rate", "region")
                treated = find_treated_unit(panel)
                est = difference_in_differences(
                    panel, treated, find_event_week(panel, treated), week
                )
                if not est.withheld:
                    status = LOCALISED
                    evidence = (
                        f"{treated} diverged from {', '.join(est.controls)} at {est.event_week}: "
                        f"{est.relative:+.1%} (CI {est.ci[0]:+.5f} to {est.ci[1]:+.5f}); "
                        f"no instrumented driver explains it"
                    )
                    owner = contract.drivers["competitor_price_index"]["owner_role"]

            causes.append(Cause(
                factor=factor, label=node.label, gbp=gbp, rung=node.rung,
                status=status, evidence=evidence, drivers=drivers, owner=owner,
            ))

    # ---- coverage ------------------------------------------------------
    gross = sum(abs(c.gbp) for c in causes) or 1.0
    coverage = sum(c.credit * abs(c.gbp) for c in causes) / gross

    # ---- the other components -----------------------------------------
    fresh = freshness(con, contract).set_index("source")
    lineage = contract.kpi(kpi_id).get("lineage", [])
    touched = set(lineage) | {
        contract.drivers[d]["source"] for c in causes for d in c.drivers
    }
    freshness_score = float(min((fresh.loc[s, "freshness_score"] for s in touched if s in fresh.index),
                                default=1.0))

    history = movement.history_weeks / MIN_HISTORY
    history_score = float(np.clip(history, 0.0, 1.0))

    method_strength = sum(
        RUNG_STRENGTH.get(c.rung, 0.6) * abs(c.gbp) for c in causes if c.credit > 0
    ) / (sum(abs(c.gbp) for c in causes if c.credit > 0) or 1.0)

    # ---- contradictions ------------------------------------------------
    contradictions: list[str] = []
    gap_sign = np.sign(d.delta)
    against = sum(abs(c.gbp) for c in causes if np.sign(c.gbp) != gap_sign)
    offset_share = against / gross
    if offset_share > 0.15:
        names = ", ".join(c.label for c in causes if np.sign(c.gbp) != gap_sign)
        contradictions.append(
            f"{offset_share:.0%} of gross movement runs against the gap ({names}) — "
            f"drivers are pulling in opposite directions"
        )
    contradiction_score = float(np.clip(offset_share / 0.5, 0.0, 1.0))

    # ---- score ---------------------------------------------------------
    components = {
        "coverage": coverage,
        "freshness": freshness_score,
        "history_depth": history_score,
        "method_strength": method_strength,
        "contradiction": contradiction_score,
    }
    score = float(np.clip(sum(weights[k] * v for k, v in components.items()), 0.0, 1.0))

    band = CONFIDENT if score >= bands["confident"] else (
        QUALIFIED if score >= bands["qualified"] else ABSTAIN
    )

    # ---- what would raise it -------------------------------------------
    missing: list[str] = []
    for c in causes:
        if c.status == UNATTRIBUTED and abs(c.gbp) > 20_000:
            missing.append(f"no driver identified for {c.label} ({c.gbp:+,.0f})")
        if c.status == LOCALISED:
            missing.append(
                f"{c.label} is localised but uninstrumented — instrumenting "
                f"competitor pricing would name a {abs(c.gbp):,.0f} term"
            )
    for src in touched:
        if src in fresh.index and fresh.loc[src, "status"] == "stale":
            missing.append(
                f"{src} is {fresh.loc[src, 'lag_hours']:.0f}h stale against a "
                f"{fresh.loc[src, 'sla_hours']:.0f}h SLA"
            )

    return Assessment(
        kpi=kpi_id, week=week, delta=d.delta, coverage=coverage, components=components,
        score=score, band=band, action=ACTIONS[band], causes=causes,
        contradictions=contradictions, missing=missing,
    )


# ----------------------------------------------------------------- output --

def render(a: Assessment, contract: Contract) -> str:
    weights = contract.confidence["weights"]
    out = [f"{a.kpi}  {a.week}"]

    if a.delta is not None:
        out.append(f"  gap {a.delta:+,.0f} {contract.currency}\n")
    else:
        out.append("")

    if a.causes:
        out.append(f"  {'contribution':24}{'amount':>14}  {'status':18}rung")
        out.append(f"  {'-' * 66}")
        for c in sorted(a.causes, key=lambda x: x.gbp):
            out.append(f"  {c.label:24}{c.gbp:>+14,.0f}  {c.status:18}{c.rung}")
            for line in textwrap.wrap(c.evidence, width=84):
                out.append(f"      {line}")
            if c.owner:
                out.append(f"      owner: {c.owner}")
        out.append("")

    out.append(f"  {'component':20}{'value':>8}{'weight':>9}{'contribution':>14}")
    out.append(f"  {'-' * 51}")
    for k, v in a.components.items():
        w = weights.get(k, 0.0)
        out.append(f"  {k:20}{v:>8.2f}{w:>9.2f}{w * v:>+14.3f}")
    out.append(f"  {'-' * 51}")
    out.append(f"  {'score':20}{'':17}{a.score:>14.3f}")

    if a.contradictions:
        out.append("\n  contradictions")
        for c in a.contradictions:
            out.append(f"    - {c}")

    out.append(f"\n  BAND: {a.band.upper()}   ->  {a.action}")
    if a.note:
        out.append(f"  {a.note}")

    if a.missing:
        out.append("\n  what would raise confidence")
        for m in dict.fromkeys(a.missing):
            out.append(f"    - {m}")
    return "\n".join(out)


def main() -> None:
    week = sys.argv[1] if len(sys.argv) > 1 else FOCAL_WEEK
    contract = load()
    con = connect(contract=contract)

    print("Rung 5 — confidence and abstention")
    print(f"bands: confident >= {contract.confidence['bands']['confident']}, "
          f"qualified >= {contract.confidence['bands']['qualified']}, else abstain\n")

    print("=" * 72)
    print("SCENARIO 1  the multi-factor movement\n")
    print(render(assess(con, contract, "net_revenue", week), contract))

    print("\n" + "=" * 72)
    print("SCENARIO 2  a newly launched product — sparse history\n")
    print(render(assess(con, contract, "net_revenue", week, {"sku": "HOME-NEW-01"}), contract))


if __name__ == "__main__":
    main()
