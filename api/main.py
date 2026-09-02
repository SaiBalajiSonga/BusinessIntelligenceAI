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

import re
import threading
from contextlib import asynccontextmanager
from datetime import date
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

# Persona ids come from the ACTIVE contract, not a literal here — a hardcoded
# tuple is exactly what stops a second vertical (contracts/kpis_saas.yaml)
# from ever being more than decoration, since every persona-taking endpoint
# would keep validating against retail's ids no matter what KPI_CONTRACT_PATH
# pointed to.
def _persona_ids() -> tuple[str, ...]:
    return tuple(service.contract().personas)


_ISO_WEEK = re.compile(r"^(\d{4})-W(\d{1,2})$")


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
    valid = _persona_ids()
    if persona not in valid:
        raise HTTPException(400, f"unknown persona {persona!r}; expected one of {list(valid)}")
    return persona


def _scope_key(persona: str) -> tuple:
    return service._key(service.scope_for(persona))


def _week(week: str) -> str:
    """
    A malformed or out-of-range `week` reached `feedback.learn.week_start`
    unvalidated and raised a bare ValueError, which is exactly how an empty or
    bad `week` query param turned into an unhandled 500 on `/v1/learning`. Every
    endpoint that takes a week now rejects it up front with a real 422 instead.
    """
    m = _ISO_WEEK.match(week or "")
    if not m:
        raise HTTPException(422, f"{week!r} is not an ISO week (expected e.g. '2026-W32')")
    try:
        date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)
    except ValueError:
        raise HTTPException(422, f"{week!r} is not a valid ISO week") from None
    return week


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
        for p in _persona_ids()
    ]


# -------------------------------------------------------------- movements --

@app.get("/v1/movements", tags=["analysis"])
def movements(
    week: str = Query(FOCAL_WEEK), persona: str = Query("cfo"),
) -> dict:
    """Rung 0. What moved, and did it clear both the statistical and money bars."""
    _persona(persona)
    _week(week)
    masked = set(service.masked_for(persona))
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
            } for m in found if m.kpi not in masked
        ],
        # transparency, not a data leak: which KPIs exist but were withheld —
        # the same disclosure `/v1/insight` already makes for narrative evidence
        "masked_kpis": sorted({m.kpi for m in found} & masked),
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
    _week(week)
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
            "raw_score": a.raw_score, "calibration_applied": a.calibration_applied,
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
    _week(week)
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
    _week(week)
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
    _week(week)
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
    verdict: str = Field(description="correct | wrong_driver | known_cause | not_material | unclear | hallucination | missed_factor | bad_tone")
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

    Recording the row is only half of it — the loop is not closed until the
    learned calibration and driver priors are recomputed, persisted, and the
    next assessment actually reads them. `service.relearn` does all three, so
    a later `GET /v1/insight` for this KPI can score differently because of
    what was just submitted.
    """
    try:
        fb = Feedback(**body.model_dump())
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    fb_id = service.store().record_feedback(fb)
    state = service.relearn(fb.kpi)
    return {
        "id": fb_id, "recorded": True,
        "relearned": {
            "calibration_fitted": state.calibration.fitted,
            "drivers_updated": sorted(state.priors),
        },
    }


@app.get("/v1/feedback", tags=["feedback"])
def list_feedback(kpi: str = Query("net_revenue")) -> dict:
    import pandas as pd
    df = service.store().feedback(kpi)
    if df is None or not isinstance(df, pd.DataFrame):
        return {"count": 0, "by_verdict": {}, "rows": []}
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
    _week(week)
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
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_DIST = pathlib.Path(__file__).resolve().parent.parent / "web" / "dist"

if (_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

@app.get("/")
def serve_root():
    index_file = _DIST / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"status": "ok", "message": "KPI Intelligence API is running. Open /docs for Swagger UI."}

@app.get("/{full_path:path}")
def serve_spa(full_path: str):
    if full_path.startswith("v1") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
        raise HTTPException(404, "Not Found")
    target = _DIST / full_path
    if target.exists() and target.is_file():
        return FileResponse(str(target))
    index_file = _DIST / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    raise HTTPException(404, "Not Found")




class IntegrationCreds(BaseModel):
    engine: str
    host: str | None = None
    database: str | None = None
    user: str | None = None
    password: str | None = None

@app.post("/v1/integrations/test", tags=["system"])
def test_integration(creds: IntegrationCreds) -> dict:
    """
    No Snowflake/BigQuery/Postgres/Redshift/Databricks connector exists yet —
    building one is a real, separate undertaking, not something to fake behind
    a sleep. What this CAN do honestly is report the truth about the warehouse
    the engine actually runs on: does each source the active KPI contract
    declares really have a table here, and how many rows does it really hold.
    That is a real check, not theater, and it fails truthfully — a stated
    engine we cannot reach, or a source with no data — rather than always
    returning the same fabricated "14 tables, 5 KPIs" regardless of input.
    """
    import time

    if creds.engine == "postgresql" and creds.user == "fail":
        # the one deliberately-scripted path, kept only to exercise the error
        # UI — it never claims to have attempted a connection
        raise HTTPException(401, "Authentication failed for user 'fail' (simulated — "
                                  "no live PostgreSQL connector is implemented)")

    t0 = time.perf_counter()
    result = service.introspect_sources()
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    found, missing = result["found"], result["missing"]
    total = len(found) + len(missing)

    if not found:
        raise HTTPException(
            502,
            f"Could not verify any of this contract's {total} declared source(s) against "
            f"the live DuckDB warehouse: " +
            "; ".join(f"{m['source']} ({m['reason']})" for m in missing),
        )

    return {
        "status": "success" if not missing else "partial",
        "message": (
            f"No external {creds.engine} connector is implemented — reporting what "
            f"this engine's own DuckDB warehouse actually contains: {len(found)} of "
            f"{total} contract source(s) verified in {elapsed_ms} ms."
        ),
        "schema_introspected": True,
        "tables_found": len(found),
        "tables": ", ".join(f"{f['source']}={f['table']} ({f['row_count']:,} rows)" for f in found),
        "kpis_generated": len(service.contract().kpi_ids),
        "missing_sources": ", ".join(m["source"] for m in missing) or "none",
        "elapsed_ms": elapsed_ms,
    }
