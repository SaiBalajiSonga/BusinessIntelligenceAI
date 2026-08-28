"""
FastAPI over the engine.

Every response that carries a number also carries how it was produced — the
rung, the method, the confidence, and the split between deterministic and LLM
processing. That is not decoration: a figure whose provenance cannot be shown
is exactly what this architecture exists to avoid shipping.

    uvicorn api.main:app --reload --port 8000
    open http://localhost:8000/docs
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api import service
from api.cache import STATS, Timings
from engine.confidence import ABSTAIN
from engine.detect import FOCAL_WEEK
from feedback.store import Annotation, Feedback
from narrative.provider import TELEMETRY

PERSONAS = ("cfo", "eu_category_manager", "analyst")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # warm in the background so the server answers /health immediately while
    # the focal week is being computed
    threading.Thread(target=service.warm, daemon=True).start()
    yield


app = FastAPI(
    title="KPI Intelligence Engine",
    description="Detects a material KPI movement, explains it with methods that "
                "can be checked, and abstains when the evidence will not carry a "
                "conclusion.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _persona(persona: str) -> str:
    if persona not in PERSONAS:
        raise HTTPException(400, f"unknown persona {persona!r}; expected one of {list(PERSONAS)}")
    return persona


def _scope_key(persona: str) -> tuple:
    return service._key(service.scope_for(persona))


# ------------------------------------------------------------------ meta --

@app.get("/v1/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "focal_week": FOCAL_WEEK, "llm": service.llm_info(),
            "warm": service.assessment_for.cache_size() > 0}


@app.get("/v1/contract", tags=["meta"])
def contract() -> dict:
    """The semantic layer: definitions, thresholds, drivers, levers, entitlements."""
    raw = service.contract().raw
    return {
        "version": raw["version"], "currency": raw["currency"], "as_of": raw["as_of"],
        "kpis": raw["kpis"], "sources": raw["sources"], "drivers": raw["drivers"],
        "levers": raw["levers"], "personas": raw["personas"],
        "confidence": raw["confidence"], "attribution": raw["attribution"],
        "causal": raw["causal"], "decompositions": raw["decompositions"],
    }


@app.get("/v1/freshness", tags=["meta"])
def source_freshness() -> list[dict]:
    """Per-source staleness. Feeds the confidence score, not just the display."""
    return service.freshness_for()


@app.get("/v1/personas", tags=["meta"])
def personas() -> list[dict]:
    c = service.contract()
    return [
        {"id": p, "label": c.persona(p)["label"], "regions": c.persona(p)["regions"],
         "masked_columns": service.masked_for(p), "scope": service.scope_for(p)}
        for p in PERSONAS
    ]


# -------------------------------------------------------------- movements --

@app.get("/v1/movements", tags=["analysis"])
def movements(
    week: str = Query(FOCAL_WEEK), persona: str = Query("cfo"),
) -> dict:
    """Rung 0. What moved, and did it clear both the statistical and money bars."""
    _persona(persona)
    t = Timings()
    with t.track("detect (Rung 0)"):
        found = service.movements_for(week, _scope_key(persona))
    return {
        "week": week, "persona": persona,
        "movements": [
            {
                "kpi": m.kpi, "label": m.label, "unit": m.unit,
                "actual": m.actual, "expected": m.expected, "delta": m.delta,
                "delta_pct": m.delta_pct, "z": m.z, "impact_gbp": m.impact_gbp,
                "material": m.material, "baseline_method": m.baseline_method,
                "history_weeks": m.history_weeks, "backtest_weeks": m.backtest_n,
                "not_flagged_because": m.reasons,
            } for m in found
        ],
        "processing": t.summary(),
    }


# ---------------------------------------------------------------- insight --

@app.get("/v1/insight", tags=["analysis"])
def insight(week: str = Query(FOCAL_WEEK), persona: str = Query("cfo")) -> dict:
    """
    The evidence object. Every number the narrative is allowed to use, with the
    rung and method that produced it.
    """
    _persona(persona)
    key = _scope_key(persona)
    t = Timings()

    with t.track("assess (Rungs 0-5)"):
        a = service.assessment_for(week, key)
    with t.track("decompose (Rungs 1-2)"):
        d = service.decomposition_for(week, key)

    return {
        "kpi": a.kpi, "week": week, "currency": service.contract().currency,
        "gap": a.delta,
        "actual": d.actual_revenue if a.delta is not None else None,
        "expected": d.expected_revenue if a.delta is not None else None,
        "confidence": {
            "score": a.score, "band": a.band, "coverage": a.coverage,
            "components": a.components, "action": a.action,
            "llm_will_be_called": a.band != ABSTAIN,
        },
        "causes": [
            {
                "factor": c.factor, "label": c.label, "amount": c.gbp, "rung": c.rung,
                "status": c.status, "credit": c.credit, "evidence": c.evidence,
                "drivers": c.drivers, "owner": c.owner, "scope": c.scope,
            } for c in sorted(a.causes, key=lambda x: x.gbp)
        ],
        "contradictions": a.contradictions,
        "would_raise_confidence": list(dict.fromkeys(a.missing)),
        "no_counterfactual": d.no_counterfactual,
        "entitlement": {
            "persona": persona,
            "regions": service.contract().persona(persona)["regions"],
            "masked_columns": service.masked_for(persona),
            "applied": "row filter in SQL, before any analysis",
        },
        "processing": t.summary(),
    }


@app.get("/v1/attribution", tags=["analysis"])
def attribution(week: str = Query(FOCAL_WEEK), persona: str = Query("cfo")) -> dict:
    """Rung 3. Where it happened, ranked by surprise rather than size."""
    _persona(persona)
    t = Timings()
    with t.track("drill (Rung 3)"):
        levels = service.drill_for(week, _scope_key(persona))

    return {
        "week": week, "persona": persona,
        "path": [{"dimension": lv.dimension, "chosen": lv.chosen} for lv in levels if lv.chosen],
        "levels": [
            {
                "depth": lv.depth, "dimension": lv.dimension,
                "divergence": lv.divergence, "chosen": lv.chosen,
                "considered": lv.considered, "stopped": lv.stopped,
                "slices": lv.table.to_dict(orient="records") if not lv.table.empty else [],
            } for lv in levels
        ],
        "processing": t.summary(),
    }


# ---------------------------------------------------------------- actions --

@app.get("/v1/actions", tags=["analysis"])
def actions(week: str = Query(FOCAL_WEEK), persona: str = Query("cfo")) -> dict:
    """driver -> lever -> action -> expected impact -> owner -> confidence -> monitoring."""
    _persona(persona)
    key = _scope_key(persona)
    t = Timings()
    with t.track("levers"):
        recs = service.recommendations_for(week, key)
        a = service.assessment_for(week, key)

    recoverable = sum(r.expected_impact or 0 for r in recs)
    return {
        "week": week, "persona": persona,
        "gap": a.delta,
        "modelled_recovery": recoverable,
        "modelled_recovery_share": recoverable / abs(a.delta) if a.delta else None,
        "recommendations": [
            {
                "kind": r.kind, "driver": r.driver, "lever": r.lever, "action": r.action,
                "expected_impact": r.expected_impact,
                "reversal_fraction": r.reversal_fraction,
                "contribution": r.contribution, "basis": r.basis,
                "owner": r.owner, "decision_rights": r.decision_rights,
                "confidence": r.confidence, "horizon_weeks": r.horizon_weeks,
                "monitoring": {
                    "metrics": r.monitoring.metrics, "cadence": r.monitoring.cadence,
                    "horizon_days": r.monitoring.horizon_days,
                    "guardrail": r.monitoring.guardrail,
                },
                "assumptions": r.assumptions,
            } for r in recs
        ],
        "processing": t.summary(),
    }


# -------------------------------------------------------------- narrative --

@app.get("/v1/narrative", tags=["narrative"])
def narrative(week: str = Query(FOCAL_WEEK), persona: str = Query("cfo")) -> dict:
    """
    Prose, and the receipt for it: which figures were checked, how many drafts
    were rejected, and whether the model was called at all.
    """
    _persona(persona)
    t = Timings()
    with t.track("assess (Rungs 0-5)"):
        a = service.assessment_for(week, _scope_key(persona))
    with t.track("narrate", kind="llm"):
        n = service.narrative_for(week, persona)

    return {
        "week": week, "persona": persona, "band": n.band, "text": n.text,
        "source": n.source, "llm_called": n.llm_called,
        "guard": {
            "figures_checked": len(n.validation.figures) if n.validation else 0,
            "violations": [f.raw for f in n.validation.violations] if n.validation else [],
            "passed": bool(n.validation and n.validation.ok),
            "drafts_rejected": len(n.rejected),
            "report": n.validation.report() if n.validation else "not applicable",
        },
        "calls": [
            {"model": c.model, "provider": c.provider, "latency_ms": c.latency_ms,
             "input_tokens": c.input_tokens, "output_tokens": c.output_tokens,
             "cost_usd": c.cost_usd, "cached": c.cached, "attempt": c.attempt}
            for c in n.completions
        ],
        "evidence": n.evidence,
        "processing": t.summary(),
    }


# -------------------------------------------------------------- telemetry --

# -------------------------------------------------------------- feedback --

class FeedbackIn(BaseModel):
    kpi: str = "net_revenue"
    iso_week: str = FOCAL_WEEK
    persona: str = "analyst"
    verdict: str = Field(description="correct | wrong_driver | known_cause | not_material | unclear")
    driver: str | None = None
    correct_driver: str | None = None
    confidence_shown: float | None = None
    impact_shown: float | None = None
    comment: str | None = None
    author: str | None = None


class AnnotationIn(BaseModel):
    label: str
    starts_on: str
    ends_on: str | None = None
    kpi: str | None = "net_revenue"
    dimension: str | None = None
    value: str | None = None
    cause: str | None = None
    expected: bool = True
    author: str | None = None


@app.post("/v1/feedback", tags=["feedback"], status_code=201)
def submit_feedback(body: FeedbackIn) -> dict:
    """
    A correction, structured rather than free text. A thumbs-down teaches
    nothing; "the driver was wrong, it was actually X" updates a prior.
    """
    try:
        fb = Feedback(**body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    return {"id": service.store().record_feedback(fb), "recorded": True}


@app.get("/v1/feedback", tags=["feedback"])
def list_feedback(kpi: str = Query("net_revenue")) -> dict:
    df = service.store().feedback(kpi)
    counts = df["verdict"].value_counts().to_dict() if not df.empty else {}
    return {"count": len(df), "by_verdict": counts,
            "rows": df.tail(50).to_dict(orient="records")}


@app.post("/v1/annotations", tags=["feedback"], status_code=201)
def add_annotation(body: AnnotationIn) -> dict:
    """A known event. A planned campaign is not an anomaly."""
    return {"id": service.store().add_annotation(Annotation(**body.model_dump())),
            "recorded": True}


@app.get("/v1/learning", tags=["feedback"])
def learning(week: str = Query(FOCAL_WEEK), persona: str = Query("cfo")) -> dict:
    """
    What the loop has learned, and what a later run does differently because
    of it. Kept as inspectable data rather than hidden inside a model file.
    """
    _persona(persona)
    state = service.learning_for(week, persona)
    a = service.assessment_for(week, _scope_key(persona))
    return {
        "week": week, "persona": persona, "backend": service.store().backend,
        **state.summary(),
        "confidence_adjustment": state.adjust(a.score),
    }


@app.get("/v1/telemetry", tags=["meta"])
def telemetry() -> dict:
    """Runtime cost of the whole session: latency, model calls, tokens, cost."""
    return {
        "llm": {**TELEMETRY.summary(), **service.llm_info()},
        "analysis_cache": {
            "hits": STATS.hits, "misses": STATS.misses,
            "hit_rate": round(STATS.hit_rate, 4),
            "note": "a cold assessment is ~7s; every repeat is served from memory",
        },
        "pricing_note": "cost is at reference rates, not what the free tier charges",
    }


@app.get("/v1/processing-split", tags=["meta"])
def processing_split() -> dict:
    """
    LLM versus non-LLM, measured on genuinely cold work.

    These timings are captured once during warm-up. Measuring on demand would
    time a warm cache, report 0ms of deterministic work, and conclude that the
    system is almost entirely an LLM — the exact opposite of what it is.
    """
    if not service.COLD_PROFILE:
        raise HTTPException(503, "still warming — the cold profile is not measured yet")

    s = dict(service.COLD_PROFILE)
    s["interpretation"] = (
        f"{1 - s['llm_share']:.1%} of processing time is deterministic. Every "
        f"quantity originates there; the LLM only renders what it is given."
    )
    return s


# ----------------------------------------------------------- static UI mount --
import pathlib
from fastapi.staticfiles import StaticFiles

_DIST = pathlib.Path(__file__).resolve().parent.parent / "web" / "dist"
if _DIST.exists():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="ui")

