"""
The engine, wrapped for HTTP.

Everything here is cached and entitlement-scoped. The important rule is that a
persona's regions become a SQL filter BEFORE any analysis runs, so two personas
receive genuinely different analyses rather than one analysis with fields
hidden. That difference shows up as a different gap, different drivers and a
different confidence score — which is the point.
"""

from __future__ import annotations

import threading
from typing import Any

import duckdb

from api.cache import Timings, memoise
from engine.attribute import drill
from engine.confidence import Assessment, assess
from engine.contract import Contract, load
from engine.decompose import Decomposition, decompose
from engine.detect import FOCAL_WEEK, Movement, detect
from engine.levers import Recommendation, recommend
from engine.warehouse import connect, freshness
from feedback.learn import Learning, learn, persist
from feedback.store import Store, open_store
from narrative.provider import LLM
from narrative.synthesize import Narrative, narrate

_LOCAL = threading.local()
_CONTRACT: Contract | None = None
_ROOT_CON: duckdb.DuckDBPyConnection | None = None


def contract() -> Contract:
    global _CONTRACT
    if _CONTRACT is None:
        _CONTRACT = load()
    return _CONTRACT


def con() -> duckdb.DuckDBPyConnection:
    """
    One cursor per thread.

    DuckDB connections are not safe to share across threads, and uvicorn runs
    sync endpoints in a worker pool. `cursor()` hands back an independent handle
    onto the same database, which is the supported way to do this.
    """
    global _ROOT_CON
    if _ROOT_CON is None:
        _ROOT_CON = connect(contract=contract())
    handle = getattr(_LOCAL, "con", None)
    if handle is None:
        handle = _LOCAL.con = _ROOT_CON.cursor()
    return handle


# ------------------------------------------------------------ entitlement --

def scope_for(persona_id: str) -> dict[str, Any] | None:
    """A persona's row filter. None means the whole portfolio."""
    c = contract()
    regions = set(c.persona(persona_id).get("regions", []))
    everything = set(c.raw["dimensions"]["region"]["values"])
    return None if regions >= everything else {"region": sorted(regions)}


def masked_for(persona_id: str) -> list[str]:
    return list(contract().persona(persona_id).get("masked_columns", []))


def _key(scope: dict[str, Any] | None) -> tuple:
    return tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in (scope or {}).items()))


# ------------------------------------------------------------- the calls --
# Cached on the entitlement scope rather than the persona, so the CFO and the
# analyst share one computation while the regional manager gets their own.

@memoise
def movements_for(week: str, scope_key: tuple, scope: Any = None) -> list[Movement]:
    return detect(con(), contract(), week, dict(_unkey(scope_key)) or None)


@memoise
def assessment_for(week: str, scope_key: tuple) -> Assessment:
    return assess(con(), contract(), "net_revenue", week, dict(_unkey(scope_key)) or None,
                  store=store())


@memoise
def decomposition_for(week: str, scope_key: tuple) -> Decomposition:
    return decompose(con(), contract(), week, dict(_unkey(scope_key)) or None)


@memoise
def drill_for(week: str, scope_key: tuple):
    return drill(con(), contract(), "net_revenue", week, dict(_unkey(scope_key)) or None)


@memoise
def recommendations_for(week: str, scope_key: tuple) -> list[Recommendation]:
    scope = dict(_unkey(scope_key)) or None
    return recommend(con(), contract(), assessment_for(week, scope_key), week, scope)


@memoise
def narrative_for(week: str, scope_key: tuple, persona_id: str) -> Narrative:
    return narrate(_llm(), contract(), assessment_for(week, scope_key), persona_id)


@memoise
def freshness_for() -> list[dict]:
    return freshness(con(), contract()).to_dict(orient="records")


def introspect_sources() -> dict[str, Any]:
    """
    What `/v1/integrations/test` actually checks: for every source the ACTIVE
    contract declares, does this DuckDB warehouse really hold the table it
    claims to, and how many rows does it really have.

    No external connector exists for Snowflake/BigQuery/Postgres/etc — this
    reports the truth about the one warehouse the engine actually has access
    to, rather than fabricating a response for whichever `engine` was posted.
    """
    from engine.warehouse import SOURCE_TABLES

    cn = con()
    c = contract()
    found: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for source_id in c.sources:
        table = SOURCE_TABLES.get(source_id)
        if table is None:
            missing.append({"source": source_id, "table": None,
                            "reason": "no physical table is mapped for this source in this warehouse"})
            continue
        try:
            n = cn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            found.append({"source": source_id, "table": table, "row_count": int(n)})
        except Exception as e:
            missing.append({"source": source_id, "table": table, "reason": str(e)})

    return {"found": found, "missing": missing}


def _unkey(scope_key: tuple) -> dict:
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in scope_key}


_STORE: Store | None = None


def store() -> Store:
    """Feedback lives in its own database — DuckDB is single-writer, and the
    warehouse connection is already held by this process."""
    global _STORE
    if _STORE is None:
        _STORE = open_store()
    return _STORE


def learning_for(week: str, persona_id: str) -> Learning:
    """Not memoised: the whole point is that it changes when feedback arrives."""
    return learn(
        store(), kpi="net_revenue", iso_week=week,
        current_threshold=float(contract().raw["materiality"]["min_impact_gbp"]),
        scope=scope_for(persona_id),
    )


def relearn(kpi: str) -> Learning:
    """
    Close the loop: recompute calibration + driver priors from the feedback
    recorded so far, PERSIST them (so they survive a restart and are visible as
    plain data), and invalidate every cached assessment that could have used
    the stale priors — otherwise a corrected driver prior would sit in the
    store unread until the process cache happened to expire.

    Called synchronously right after `POST /v1/feedback` records a row, so the
    very next `assess()` — which reads the store via `assessment_for` — reflects
    it immediately.
    """
    state = learn(
        store(), kpi=kpi, iso_week=FOCAL_WEEK,
        current_threshold=float(contract().raw["materiality"]["min_impact_gbp"]),
    )
    persist(store(), state, kpi)
    assessment_for.cache_clear()
    recommendations_for.cache_clear()
    narrative_for.cache_clear()
    return state


_LLM: LLM | None = None


def _llm() -> LLM:
    global _LLM
    if _LLM is None:
        _LLM = LLM(contract())
    return _LLM


def llm_info() -> dict:
    llm = _llm()
    return {"provider": llm.provider.name, "model": llm.model, "cached_prompts": len(llm.cache)}


# ------------------------------------------------------------- warm start --

# The cold cost of each stage, measured once while warming. Serving these is
# the only honest way to answer "how much of this is the LLM?" — asking a warm
# cache reports 0ms of deterministic work and makes the LLM look like the whole
# system, which is the opposite of true.
COLD_PROFILE: dict[str, Any] = {}


def warm(week: str = FOCAL_WEEK) -> None:
    """
    Pre-compute the focal week for every distinct entitlement scope, recording
    what each stage actually costs on the way through.

    Without this the first click costs seven seconds, which reads as a broken
    demo rather than a thorough one.
    """
    import time

    con()
    scopes = {_key(scope_for(p)) for p in contract().personas}
    stages: list[dict[str, Any]] = []

    def timed(name: str, fn, kind: str = "deterministic"):
        t0 = time.perf_counter()
        result = fn()
        stages.append({"name": name, "kind": kind,
                       "ms": round((time.perf_counter() - t0) * 1000, 1)})
        return result

    first = True
    for scope_key in scopes:
        if first:
            timed("reconcile + detect (Rung 0)", lambda: movements_for(week, scope_key))
            timed("decompose (Rungs 1-2)", lambda: decomposition_for(week, scope_key))
            timed("attribute (Rung 3)", lambda: drill_for(week, scope_key))
            timed("assess + causal (Rungs 4-5)", lambda: assessment_for(week, scope_key))
            timed("levers", lambda: recommendations_for(week, scope_key))
            first = False
        else:
            movements_for(week, scope_key)
            assessment_for(week, scope_key)
            decomposition_for(week, scope_key)
            drill_for(week, scope_key)
            recommendations_for(week, scope_key)

    cfo_scope_key = _key(scope_for("cfo"))
    n = timed("narrate", lambda: narrative_for(week, cfo_scope_key, "cfo"), kind="llm")

    # a prompt-cache hit would understate the model's real cost, so prefer a
    # measured live call where one exists
    from narrative.provider import TELEMETRY
    live = [c.latency_ms for c in TELEMETRY.live_calls]
    llm_stage = next(s for s in stages if s["kind"] == "llm")
    if live:
        llm_stage["ms"] = round(sum(live) / len(live), 1)
        llm_stage["basis"] = "measured live generation"
    else:
        llm_stage["basis"] = "served from the prompt cache — real generation is slower"

    det = sum(s["ms"] for s in stages if s["kind"] == "deterministic")
    llm = sum(s["ms"] for s in stages if s["kind"] == "llm")
    COLD_PROFILE.update({
        "measured": "once, at warm-up, on a cold cache",
        "deterministic_ms": round(det, 1), "llm_ms": round(llm, 1),
        "total_ms": round(det + llm, 1),
        "llm_share": round(llm / (det + llm), 4) if det + llm else 0.0,
        "stages": stages,
    })
