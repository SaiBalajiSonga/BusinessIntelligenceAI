"""
Evidence object in, prose out.

The LLM's entire job is rendering. It receives numbers it may use and is told
it may use no others; what comes back is checked figure by figure before anyone
sees it. If the check fails it is asked again with its own mistake quoted at it;
if it fails twice the deterministic template ships instead. The narrative can
therefore be wrong about tone, emphasis or grammar — it cannot be wrong about
a number.

Entitlements are applied BEFORE the analysis, not after. A regional manager's
insight is computed from their regions only, so their drivers and their ranking
genuinely differ from the CFO's. Masking output would produce the same analysis
with bits hidden, which is a different and much weaker claim.

    python -m narrative.synthesize
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

from engine.confidence import ABSTAIN, Assessment, assess
from engine.contract import Contract, load
from engine.detect import FOCAL_WEEK, detect
from engine.warehouse import connect
from feedback.store import open_store
from narrative.provider import LLM, TELEMETRY, Completion
from narrative.validator import Validation, validate

LLM_SOURCE, RETRY_SOURCE, TEMPLATE_SOURCE, ABSTENTION = (
    "llm", "llm (retry)", "template fallback", "abstention (no LLM call)"
)


# ----------------------------------------------------------------- prompts --

BASE_RULES = """You render a supplied evidence object into prose for a business reader.

ABSOLUTE RULES
1. Use ONLY numbers that appear in the evidence below. Never compute, sum,
   subtract, average, or estimate any figure — not even one that seems obvious.
2. If you want to state a number that is not in the evidence, omit the claim.
3. Do not invent causes. Only causes marked in the evidence exist.
4. Where the evidence marks something uncertain, say so plainly.
5. No preamble, no headings, no bullet points. Prose only."""

PERSONA_PROMPTS = {
    "cfo": BASE_RULES + """

AUDIENCE: Chief Financial Officer.
Two or three sentences. Lead with the money. Frame at portfolio level — no SKU
names, no channel detail. Say what is known versus estimated. End with the
single decision that matters this quarter.""",

    "eu_category_manager": BASE_RULES + """

AUDIENCE: EU Category Manager, accountable for their own regions only.
Three or four sentences. Be operational and specific: which category, which
lever, who owns it. Only discuss levers this person can actually pull. Margin
and cost figures are not available to this reader — if none are in the evidence,
do not remark on their absence.""",

    "analyst": BASE_RULES + """

AUDIENCE: Data Analyst who will check your work.
Four or five sentences. For each figure, name the method that produced it and
the rung it came from. Distinguish exact arithmetic from estimates carrying
assumptions. State what remains unexplained and what would resolve it.""",
}


# ---------------------------------------------------------------- evidence --

def build_evidence(
    assessment: Assessment, contract: Contract, persona_id: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    persona = contract.persona(persona_id)
    masked = set(persona.get("masked_columns", []))

    drivers = []
    for c in sorted(assessment.causes, key=lambda x: x.gbp):
        if abs(c.gbp) < 1_000:
            continue
        drivers.append({
            "label": c.label,
            "amount": round(c.gbp),
            "status": c.status,
            "rung": c.rung,
            "evidence": c.evidence,
            "owner": c.owner,
        })

    evidence: dict[str, Any] = {
        "kpi": contract.kpi(assessment.kpi)["label"],
        "week": assessment.week,
        "currency": contract.currency,
        "gap": round(assessment.delta) if assessment.delta is not None else None,
        "confidence": {
            "score": round(assessment.score, 3),
            "band": assessment.band,
            "coverage": round(assessment.coverage, 3),
        },
        "drivers": drivers,
        "unexplained": [d["label"] for d in drivers if d["status"] == "unattributed"],
        "contradictions": assessment.contradictions,
        "would_raise_confidence": list(dict.fromkeys(assessment.missing)),
        "entitlement": {
            "persona": persona["label"],
            "regions": persona.get("regions", []),
            "masked_columns": sorted(masked),
        },
    }

    for key, value in (extra or {}).items():
        if key not in masked:
            evidence[key] = value

    return evidence


def render_evidence(evidence: dict[str, Any]) -> str:
    """Compact text form. Tokens are a cost line, so this stays terse."""
    e = evidence
    lines = [
        f"KPI: {e['kpi']}   period: {e['week']}   currency: {e['currency']}",
        f"gap vs expectation: {e['gap']:+,}" if e["gap"] is not None else "gap: not measurable",
        f"confidence: {e['confidence']['score']} ({e['confidence']['band']}), "
        f"coverage {e['confidence']['coverage']}",
        "",
        "drivers (amount, how it was established):",
    ]
    for d in e["drivers"]:
        owner = f", owner {d['owner']}" if d["owner"] else ""
        lines.append(f"  - {d['label']}: {d['amount']:+,} [{d['status']}, rung {d['rung']}{owner}]")
        if d["status"] != "unattributed":
            lines.append(f"      basis: {d['evidence']}")

    if e.get("margin") is not None:
        lines += ["", f"gross margin movement: {e['margin']}"]
    if e["contradictions"]:
        lines += ["", "tensions: " + "; ".join(e["contradictions"])]
    if e["would_raise_confidence"]:
        lines += ["", "not established: " + "; ".join(e["would_raise_confidence"])]

    ent = e["entitlement"]
    lines += ["", f"reader: {ent['persona']}; regions in scope: {', '.join(ent['regions'])}"]
    if ent["masked_columns"]:
        lines.append(f"withheld from this reader: {', '.join(ent['masked_columns'])}")
    return "\n".join(lines)


# ----------------------------------------------------------------- result --

@dataclass
class Narrative:
    persona: str
    band: str
    text: str
    source: str
    evidence: dict[str, Any]
    validation: Validation | None = None
    completions: list[Completion] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)

    @property
    def llm_called(self) -> bool:
        return bool(self.completions)


# ------------------------------------------------------------- fallbacks --

_CURRENCY_SYMBOLS = {"GBP": "£", "USD": "$", "EUR": "€"}


def _money(amount: int, currency: str) -> str:
    sym = _CURRENCY_SYMBOLS.get(currency, currency + " ")
    sign = "-" if amount < 0 else ""
    return f"{sign}{sym}{abs(amount):,}"


def template_narrative(evidence: dict[str, Any]) -> str:
    """Deterministic prose. Never wrong, never good. The floor, not the goal —
    used whenever no real LLM is configured, so it has to read as sentences,
    not as the evidence dump it is built from."""
    e = evidence
    cur = e["currency"]
    named = [d for d in e["drivers"] if d["status"] != "unattributed"]
    top, rest = (named[0], named[1:3]) if named else (None, [])

    parts = [
        f"{e['kpi']} in {e['week']} came in {_money(e['gap'], cur)} against expectation."
        if e["gap"] is not None else f"{e['kpi']} in {e['week']} could not be measured against expectation."
    ]

    if top:
        clause = f"The largest identified contribution is {top['label']}, at {_money(top['amount'], cur)}"
        clause += f", owned by {top['owner'].replace('_', ' ')}" if top.get("owner") else ""
        clause += "."
        parts.append(clause)
        if rest:
            others = "; ".join(f"{d['label']} ({_money(d['amount'], cur)})" for d in rest)
            parts.append(f"Also contributing: {others}.")
    else:
        parts.append("No individual driver has been named for this movement yet.")

    if e["contradictions"]:
        parts.append("This comes with a caveat: " + "; ".join(e["contradictions"]) + ".")

    parts.append(
        f"Confidence in this account is {e['confidence']['score']:.2f} ({e['confidence']['band']}), "
        f"reflecting {e['confidence']['coverage']:.0%} coverage of the total movement by named causes."
    )
    return " ".join(parts)


def clarification_request(assessment: Assessment, contract: Contract) -> str:
    """What the engine says instead of guessing. Built without the model."""
    label = contract.kpi(assessment.kpi)["label"]
    lines = [
        f"No reliable explanation can be produced for {label} in {assessment.week}.",
        assessment.note or "The evidence is insufficient to support a conclusion.",
        "",
        "To proceed, one of the following is needed:",
    ]
    lines += [f"  - {m}" for m in dict.fromkeys(assessment.missing)] or ["  - more history"]
    return "\n".join(lines)


# ------------------------------------------------------------- the driver --

def narrate(
    llm: LLM, contract: Contract, assessment: Assessment, persona_id: str,
    extra: dict[str, Any] | None = None,
) -> Narrative:
    evidence = build_evidence(assessment, contract, persona_id, extra)

    # The gate. Below the qualified band the model is never invoked, so it has
    # no opportunity to produce a confident-sounding answer we cannot stand behind.
    if assessment.band == ABSTAIN:
        return Narrative(
            persona=persona_id, band=assessment.band,
            text=clarification_request(assessment, contract),
            source=ABSTENTION, evidence=evidence,
        )

    # No real provider configured (no API key). Rather than dress an offline
    # echo up as an "LLM call" — which would misreport the LLM-vs-deterministic
    # split the product exists to be honest about — go straight to the
    # deterministic template and say so.
    if llm.is_mock:
        return Narrative(
            persona=persona_id, band=assessment.band,
            text=template_narrative(evidence), source=TEMPLATE_SOURCE,
            evidence=evidence, validation=None,
        )

    system = PERSONA_PROMPTS[persona_id]
    user = render_evidence(evidence)
    vcfg = contract.raw["llm"]["validator"]
    kwargs = dict(
        relative_tolerance=float(vcfg["relative_tolerance"]),
        allow_small_integers_up_to=int(vcfg["allow_small_integers_up_to"]),
        allow_years=tuple(vcfg["allow_years"]),
    )

    completions, rejected = [], []
    prompt = user

    for attempt in range(1, llm.retries + 2):
        c = llm.complete(system, prompt, attempt=attempt)
        completions.append(c)
        v = validate(c.text, evidence, **kwargs)

        if v.ok:
            return Narrative(
                persona=persona_id, band=assessment.band, text=c.text,
                source=LLM_SOURCE if attempt == 1 else RETRY_SOURCE,
                evidence=evidence, validation=v, completions=completions,
                rejected=rejected,
            )

        rejected.append(c.text)
        offenders = ", ".join(f.raw for f in v.violations)
        prompt = (
            f"{user}\n\n"
            f"Your previous answer contained figures that are NOT in the evidence: "
            f"{offenders}. Rewrite it using only the figures listed above. "
            f"Drop any claim you cannot support with those numbers."
        )

    return Narrative(
        persona=persona_id, band=assessment.band,
        text=template_narrative(evidence), source=TEMPLATE_SOURCE,
        evidence=evidence, validation=None, completions=completions, rejected=rejected,
    )


# ----------------------------------------------------------------- output --

def main() -> None:
    week = sys.argv[1] if len(sys.argv) > 1 else FOCAL_WEEK
    contract = load()
    con = connect(contract=contract)
    llm = LLM(contract)
    store = open_store()

    print(f"Narrative layer — {week}")
    print(f"provider {llm.provider.name} / {llm.model}   cache {len(llm.cache)} entries\n")

    # entitlements shape the ANALYSIS, so each distinct scope is assessed separately
    scopes: dict[tuple, Assessment] = {}
    for persona_id in ("cfo", "eu_category_manager", "analyst"):
        regions = tuple(contract.persona(persona_id)["regions"])
        if regions not in scopes:
            all_regions = set(contract.raw["dimensions"]["region"]["values"])
            filters = None if set(regions) == all_regions else {"region": list(regions)}
            scopes[regions] = assess(con, contract, "net_revenue", week, filters, store=store)

    for persona_id in ("cfo", "eu_category_manager", "analyst"):
        persona = contract.persona(persona_id)
        a = scopes[tuple(persona["regions"])]
        n = narrate(llm, contract, a, persona_id)

        print("=" * 78)
        print(f"{persona['label']}   regions {', '.join(persona['regions'])}"
              f"   masked: {', '.join(persona.get('masked_columns') or ['—'])}")
        print(f"gap {a.delta:+,.0f} {contract.currency}   "
              f"confidence {a.score:.3f} ({a.band})   source: {n.source}")
        print("-" * 78)
        print(n.text)
        if n.rejected:
            print(f"\n  [{len(n.rejected)} draft(s) rejected by the numeric guard]")
        if n.validation:
            print(f"\n  guard: {n.validation.report()}")
        print()

    # the abstain path
    sparse = assess(con, contract, "net_revenue", week, {"sku": "HOME-NEW-01"})
    n = narrate(llm, contract, sparse, "cfo")
    print("=" * 78)
    print(f"Newly launched SKU — band {sparse.band}, source: {n.source}")
    print("-" * 78)
    print(n.text)

    print("\n" + "=" * 78)
    print("telemetry")
    for k, v in TELEMETRY.summary().items():
        print(f"  {k:20} {v:,.4f}" if isinstance(v, float) else f"  {k:20} {v:,}")


if __name__ == "__main__":
    main()
