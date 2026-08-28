"""
From explanation to action.

    driver -> controllable lever -> action -> expected impact -> owner ->
    confidence -> monitoring plan

Expected impact is COMPUTED, never written by a model. It is the measured
contribution of that driver, scaled by the fraction of the driver's deviation
that the action actually reverses:

    impact = contribution x (deviation_now - deviation_after) / deviation_now

So a recommendation cannot claim more than the analytics attributed to it, and
it inherits the confidence of the evidence behind it. What it does assume is
that the relationship reverses as readily as it moved — stated on every
recommendation rather than left implicit.

An uninstrumented driver gets no lever, because there is nothing to pull. It
gets an instrumentation action instead, and its payoff is measured in
confidence rather than currency.

    python -m engine.levers
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

from engine.confidence import (
    LOCALISED,
    NAMED_CONSTRAINT,
    NAMED_LEVER,
    Assessment,
    assess,
    driver_state,
)
from engine.contract import Contract, load
from engine.decompose import asp_split_by_sku
from engine.detect import FOCAL_WEEK
from engine.warehouse import connect, narrow_scope

INSTRUMENTATION = "instrumentation"
CORRECTIVE = "corrective"


# ---------------------------------------------------------------- results --

@dataclass
class Monitoring:
    metrics: list[str]
    cadence: str
    horizon_days: int
    guardrail: str

    def __str__(self) -> str:
        return (f"{', '.join(self.metrics)} — {self.cadence}, {self.horizon_days} days; "
                f"{self.guardrail}")


@dataclass
class Recommendation:
    kind: str
    driver: str
    lever: str
    action: str
    owner: str
    decision_rights: str
    horizon_weeks: int
    confidence: float
    monitoring: Monitoring
    contribution: float
    expected_impact: float | None = None
    reversal_fraction: float | None = None
    basis: str = ""
    assumptions: list[str] = field(default_factory=list)

    @property
    def is_measurable(self) -> bool:
        return self.expected_impact is not None


def _fmt(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f}" if abs(value) >= 1000 else f"{value:.4g}"


def _scope(scope: dict[str, Any] | None) -> str:
    if not scope:
        return "the portfolio"
    parts = []
    for key, val in scope.items():
        vals = val if isinstance(val, (list, tuple)) else [val]
        parts.append("/".join(str(v) for v in vals))
    return " ".join(parts)


# ------------------------------------------------------------ the mapping --

def allocate(cause, splits: dict[str, dict[str, float]]) -> dict[str, float]:
    """
    Divide a cause's contribution between the drivers behind it.

    Two drivers moved the basket mix — a campaign and a stockout — and letting
    each claim the whole term would double-count the recovery. Where a driver's
    scope names a SKU, its share is that SKU's own Bennet term, which is a
    measurement rather than an apportionment. Drivers with no such scope split
    what is left.
    """
    drivers = list(cause.drivers)
    if len(drivers) <= 1:
        return {d: cause.gbp for d in drivers}

    measured: dict[str, float] = {}
    sku = (cause.scope or {}).get("sku")
    if sku:
        for d in drivers:
            if d == "fill_rate":            # the constraint acts at that SKU
                measured[d] = splits.get(str(sku), {}).get(cause.factor, 0.0)

    remainder = cause.gbp - sum(measured.values())
    rest = [d for d in drivers if d not in measured]
    for d in rest:
        measured[d] = remainder / len(rest)
    return measured


def recommend(
    con, contract: Contract, assessment: Assessment, week: str = FOCAL_WEEK,
    filters: dict[str, Any] | None = None,
) -> list[Recommendation]:
    levers = contract.raw.get("levers", {})
    floor = float(contract.raw["materiality"].get("min_action_impact_gbp", 25_000))
    splits = asp_split_by_sku(con, contract, week, filters)
    out: list[Recommendation] = []
    seen: set[str] = set()

    for cause in sorted(assessment.causes, key=lambda c: c.gbp):
        shares = allocate(cause, splits)
        # a cause may rest on several drivers; each gets its own lever
        driver_ids = list(cause.drivers)

        # localised-but-unnamed points at the uninstrumented candidate instead
        if cause.status == LOCALISED and not driver_ids:
            driver_ids = [
                d for d, spec in contract.drivers.items()
                if not spec.get("source") and d in levers
            ]

        for driver_id in driver_ids:
            spec = levers.get(driver_id)
            if spec is None or driver_id in seen:
                continue
            seen.add(driver_id)

            # a lever is pulled where the contract says, not wherever the
            # drill happened to stop
            wanted = cause.scope if spec.get("scope") == "inherit" else None
            scope = narrow_scope(contract.drivers[driver_id].get("view", ""), wanted)
            state = driver_state(con, contract, driver_id, week, scope)
            monitoring = Monitoring(**spec["monitoring"])
            confidence = min(assessment.score, 1.0) * (
                1.0 if cause.status in (NAMED_LEVER, NAMED_CONSTRAINT) else 0.5
            )

            if spec.get("kind") == INSTRUMENTATION:
                out.append(Recommendation(
                    kind=INSTRUMENTATION, driver=driver_id, lever=spec["label"],
                    action=spec["action"].format(scope=_scope(state.scope)),
                    owner=spec["owner_role"], decision_rights=spec["decision_rights"],
                    horizon_weeks=int(spec["horizon_weeks"]), confidence=confidence,
                    monitoring=monitoring, contribution=shares.get(driver_id, cause.gbp),
                    expected_impact=None,
                    basis=f"{_fmt(abs(cause.gbp))} {contract.currency} is currently located "
                          f"but not attributed; instrumenting this driver would name it",
                    assumptions=["payoff is measured in confidence, not recovered revenue"],
                ))
                continue

            if state.actual is None or state.expected is None:
                continue

            deviation_now = state.actual - state.expected
            if abs(deviation_now) < 1e-12:
                continue

            # rates carry an absolute target; sums only make sense against
            # their own baseline, or the target is wrong at every other scope
            target = (
                float(state.expected) * float(spec["target_relative_to_baseline"])
                if "target_relative_to_baseline" in spec
                else float(spec["target"])
            )
            deviation_after = target - state.expected
            reversal = (abs(deviation_now) - abs(deviation_after)) / abs(deviation_now)
            reversal = max(0.0, min(reversal, 1.0))

            share = shares.get(driver_id, cause.gbp)
            impact = -share * reversal
            if abs(impact) < floor:
                continue        # a recommendation nobody would act on is noise

            out.append(Recommendation(
                kind=CORRECTIVE, driver=driver_id, lever=spec["label"],
                action=spec["action"].format(
                    scope=_scope(state.scope), current=_fmt(state.actual),
                    target=_fmt(target), weeks=spec["horizon_weeks"],
                ),
                owner=spec["owner_role"], decision_rights=spec["decision_rights"],
                horizon_weeks=int(spec["horizon_weeks"]), confidence=confidence,
                monitoring=monitoring, contribution=share,
                expected_impact=impact,
                reversal_fraction=reversal,
                basis=f"{cause.label} attributable to this driver: {_fmt(share)}; reverses "
                      f"{reversal:.0%} of the driver's deviation "
                      f"({_fmt(state.actual)} -> {_fmt(target)}, baseline {_fmt(state.expected)})",
                assumptions=[
                    "the relationship reverses as readily as it moved",
                    f"no offsetting response from the {reversal:.0%} of demand that "
                    f"the discount attracted" if driver_id == "discount_depth"
                    else "no offsetting movement in the other drivers",
                ],
            ))

    out.sort(key=lambda r: (r.expected_impact is None, -abs(r.expected_impact or 0)))
    return out


# ----------------------------------------------------------------- output --

def render(recs: list[Recommendation], contract: Contract) -> str:
    cur = contract.currency
    out: list[str] = []
    for i, r in enumerate(recs, 1):
        head = f"{i}. {r.lever}  [{r.kind}]"
        out.append(head)
        out.append(f"   {'action':<18}{r.action}")
        impact = (f"{r.expected_impact:+,.0f} {cur}" if r.is_measurable
                  else "not revenue — resolves an unattributed term")
        out.append(f"   {'expected impact':<18}{impact}")
        out.append(f"   {'basis':<18}{r.basis}")
        out.append(f"   {'owner':<18}{r.owner}")
        out.append(f"   {'decision rights':<18}{r.decision_rights}")
        out.append(f"   {'confidence':<18}{r.confidence:.2f}")
        out.append(f"   {'horizon':<18}{r.horizon_weeks} weeks")
        out.append(f"   {'monitoring':<18}{r.monitoring}")
        for a in r.assumptions:
            out.append(f"   {'assumes':<18}{a}")
        out.append("")
    return "\n".join(out)


def main() -> None:
    week = sys.argv[1] if len(sys.argv) > 1 else FOCAL_WEEK
    contract = load()
    con = connect(contract=contract)

    a = assess(con, contract, "net_revenue", week)
    recs = recommend(con, contract, a, week)

    print(f"Recommended actions — {week}")
    print(f"gap {a.delta:+,.0f} {contract.currency}   confidence {a.score:.3f} ({a.band})\n")
    print(render(recs, contract))

    recoverable = sum(r.expected_impact or 0 for r in recs)
    print(f"total modelled recovery  {recoverable:+,.0f} {contract.currency} "
          f"of a {a.delta:+,.0f} gap ({recoverable / abs(a.delta):.0%})")
    print("the remainder is not actionable from the drivers we can currently observe")


if __name__ == "__main__":
    main()
