"""
The HTTP surface.

Entitlement is the thing worth testing hardest here. If a persona's regions
became a display filter instead of a SQL filter, every endpoint would still
return 200 and the difference would be invisible — so the tests assert that two
personas get genuinely different *numbers*, not merely different fields.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api import service
from api.main import app

# no `with` block: the lifespan warm-up costs ~25s and these tests do not need it
client = TestClient(app)
WEEK = "2026-W32"


# ------------------------------------------------------------------ meta --

def test_health_answers_before_warm_up():
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_contract_is_served_as_the_semantic_layer():
    body = client.get("/v1/contract").json()
    for section in ("kpis", "sources", "drivers", "levers", "personas", "confidence"):
        assert section in body
    assert "net_revenue" in body["kpis"]


def test_freshness_flags_the_stale_source():
    rows = {r["source"]: r for r in client.get("/v1/freshness").json()}
    assert rows["inventory"]["status"] == "stale"
    assert rows["sales"]["status"] == "fresh"


def test_personas_expose_their_row_filter():
    by_id = {p["id"]: p for p in client.get("/v1/personas").json()}
    assert by_id["cfo"]["scope"] is None                      # whole portfolio
    assert by_id["eu_category_manager"]["scope"] == {"region": ["DE", "FR", "NL"]}
    assert "gross_margin_pct" in by_id["eu_category_manager"]["masked_columns"]


def test_an_unknown_persona_is_refused():
    r = client.get("/v1/insight", params={"persona": "ceo"})
    assert r.status_code == 400
    assert "unknown persona" in r.json()["detail"]


# ------------------------------------------------------------ malformed week --

@pytest.mark.parametrize("bad_week", ["", "notaweek", "2026-W60", "2026", "  "])
def test_learning_refuses_a_malformed_week_instead_of_crashing(bad_week):
    """
    The confirmed live bug: `week_start()` in feedback.learn raised a bare
    ValueError on a malformed or out-of-range ISO week, and nothing on the path
    from `/v1/learning` caught it — an unhandled 500 rather than a client error.
    """
    r = client.get("/v1/learning", params={"week": bad_week, "persona": "cfo"})
    assert r.status_code == 422
    assert "ISO week" in r.json()["detail"]


def test_learning_answers_for_a_real_week_and_every_persona():
    for persona in ("cfo", "eu_category_manager", "analyst"):
        r = client.get("/v1/learning", params={"week": WEEK, "persona": persona})
        assert r.status_code == 200
        body = r.json()
        assert body["backend"] == "duckdb"
        assert "calibration" in body and "driver_priors" in body
        assert "confidence_adjustment" in body


def test_a_malformed_week_is_refused_on_every_endpoint_that_takes_one():
    for path in ("/v1/movements", "/v1/insight", "/v1/attribution", "/v1/actions",
                 "/v1/narrative", "/v1/learning"):
        r = client.get(path, params={"week": "not-a-week", "persona": "cfo"})
        assert r.status_code == 422, f"{path} did not validate its week param"


# ----------------------------------------------------------- entitlement --

@pytest.fixture(scope="module")
def cfo():
    return client.get("/v1/insight", params={"week": WEEK, "persona": "cfo"}).json()


@pytest.fixture(scope="module")
def manager():
    return client.get("/v1/insight",
                      params={"week": WEEK, "persona": "eu_category_manager"}).json()


def test_entitlement_changes_the_analysis_not_the_display(cfo, manager):
    """
    The claim the architecture rests on. A row filter applied before the maths
    produces a different gap; a display filter would produce the same one.
    """
    assert cfo["gap"] != manager["gap"]
    assert abs(manager["gap"]) < abs(cfo["gap"])
    assert cfo["confidence"]["score"] != manager["confidence"]["score"]
    assert manager["entitlement"]["applied"].startswith("row filter in SQL")


def test_every_cause_carries_its_provenance(cfo):
    assert cfo["causes"]
    for c in cfo["causes"]:
        assert c["rung"] in (1, 2, 3, 4)
        assert c["status"] in ("named lever", "named constraint", "localised", "unattributed")
        assert 0.0 <= c["credit"] <= 1.0
        assert c["evidence"]


def test_confidence_reports_whether_the_model_will_be_called(cfo):
    conf = cfo["confidence"]
    assert conf["band"] in ("confident", "qualified", "abstain")
    assert conf["llm_will_be_called"] is (conf["band"] != "abstain")


def test_coverage_is_below_one_despite_an_exact_decomposition(cfo):
    assert cfo["confidence"]["coverage"] < 0.95


# --------------------------------------------------------------- actions --

def test_actions_carry_the_whole_chain():
    body = client.get("/v1/actions", params={"week": WEEK, "persona": "cfo"}).json()
    assert body["recommendations"]
    for r in body["recommendations"]:
        assert r["lever"] and r["action"] and r["owner"] and r["decision_rights"]
        assert r["monitoring"]["metrics"] and r["monitoring"]["guardrail"]
        assert r["assumptions"]


def test_modelled_recovery_never_exceeds_the_gap():
    body = client.get("/v1/actions", params={"week": WEEK, "persona": "cfo"}).json()
    assert 0 < body["modelled_recovery"] <= abs(body["gap"])


# ------------------------------------------------------------ attribution --

def test_movements_withholds_a_masked_kpi_from_an_unauthorized_persona():
    """
    Fix 3: row-level region filtering was real, but column-level masking
    (`masked_columns`) was only enforced inside narrative evidence-building.
    `/v1/movements` loops every KPI in the contract — including
    gross_margin_pct, which eu_category_manager is masked from — and returned
    it unfiltered. It must not appear in that persona's response at all, while
    an unmasked persona (analyst) must still see it (proving the test is not
    vacuous — e.g. because the KPI simply never moved this week).
    """
    masked = client.get("/v1/movements", params={"week": WEEK, "persona": "eu_category_manager"}).json()
    unmasked = client.get("/v1/movements", params={"week": WEEK, "persona": "analyst"}).json()

    masked_kpis = {m["kpi"] for m in masked["movements"]}
    unmasked_kpis = {m["kpi"] for m in unmasked["movements"]}

    assert "gross_margin_pct" not in masked_kpis
    assert "gross_margin_pct" in masked["masked_kpis"]
    assert "gross_margin_pct" in unmasked_kpis, \
        "the KPI must genuinely be present for an unmasked persona, or this test proves nothing"


def test_no_endpoint_leaks_a_masked_kpis_real_value():
    """
    A masked persona must not be able to retrieve gross_margin_pct's real
    value from ANY analysis endpoint, not just narrative evidence. The KPI id
    is allowed to appear in an explicit disclosure field (`masked_kpis`,
    `entitlement.masked_columns`) — that is transparency, not a leak — so this
    checks the actual data payloads each endpoint carries numbers in.
    """
    params = {"week": WEEK, "persona": "eu_category_manager"}

    m = client.get("/v1/movements", params=params).json()
    assert all(row["kpi"] != "gross_margin_pct" for row in m["movements"])

    i = client.get("/v1/insight", params=params).json()
    assert all(c["factor"] != "gross_margin_pct" for c in i["causes"])
    assert "gross_margin_pct" not in str(i.get("would_raise_confidence", []))

    att = client.get("/v1/attribution", params=params).json()
    assert "gross_margin_pct" not in str(att["levels"])

    act = client.get("/v1/actions", params=params).json()
    assert all(r["driver"] != "gross_margin_pct" for r in act["recommendations"])

    n = client.get("/v1/narrative", params=params).json()
    assert "gross_margin_pct" not in n["text"]
    evidence = dict(n["evidence"])
    evidence.pop("entitlement", None)   # legitimate disclosure of what's withheld, not a leak
    assert "gross_margin_pct" not in str(evidence)

    # /v1/series hands back raw weekly values, so an unenforced mask here would
    # leak the exact figure every other endpoint withholds.
    s = client.get("/v1/series", params={**params, "kpi": "gross_margin_pct"})
    assert s.status_code == 403


def test_series_returns_real_history_bounded_at_the_focal_week():
    """
    The sparkline history has to be the same series the baseline is fitted on,
    and must stop at the focal week: the warehouse holds later weeks, and
    drawing those would put data the analysis never saw into a chart captioned
    as its history.
    """
    body = client.get("/v1/series", params={"kpi": "net_revenue", "persona": "cfo", "week": WEEK}).json()

    assert body["kpi"] == "net_revenue"
    assert len(body["points"]) > 1
    weeks = [p["iso_week"] for p in body["points"]]
    assert weeks == sorted(weeks), "points must be in chronological order"
    assert max(weeks) <= WEEK, "history must not run past the week being analysed"

    # the last point is the actual the rest of the page reports for that week
    movements = client.get("/v1/movements", params={"week": WEEK, "persona": "cfo"}).json()
    net = next(m for m in movements["movements"] if m["kpi"] == "net_revenue")
    assert body["points"][-1]["value"] == pytest.approx(net["actual"], rel=1e-6)


def test_series_is_entitlement_scoped_not_just_filtered_for_display():
    """
    Two personas with different regions must get genuinely different numbers,
    the same way every other endpoint does — otherwise the sparkline would be
    drawing the whole portfolio under a scoped persona's name.
    """
    cfo = client.get("/v1/series", params={"kpi": "net_revenue", "persona": "cfo", "week": WEEK}).json()
    eu = client.get("/v1/series", params={"kpi": "net_revenue", "persona": "eu_category_manager", "week": WEEK}).json()

    assert eu["points"][-1]["value"] < cfo["points"][-1]["value"], \
        "a three-region persona must see less revenue than the whole portfolio"


def test_series_refuses_a_kpi_the_contract_does_not_define():
    r = client.get("/v1/series", params={"kpi": "not_a_real_kpi", "persona": "cfo"})
    assert r.status_code == 404


# ------------------------------------------------------- static UI serving --

def test_index_html_can_never_be_served_from_a_stale_cache():
    """
    A cached index.html shipped a blank white page to production.

    index.html is what maps to the content-hashed asset filenames, so an old
    copy requests JS and CSS that no longer exist and nothing renders. The trap
    is that FileResponse builds its ETag from (mtime, size) and every build of
    this file is the same *length* — Vite's hashes are fixed-width — so once
    the deploy platform normalises mtimes, two different builds get the same
    ETag, the server answers 304, and the browser keeps the dead HTML.

    Both halves are asserted: the response forbids storing it, and presenting
    the ETag the server itself just issued still does not produce a 304.
    """
    r = client.get("/")
    if r.status_code == 404:
        pytest.skip("no built web/dist in this checkout")

    assert "no-store" in r.headers.get("cache-control", ""), \
        "index.html must not be storable, or a deploy can leave a blank page behind"

    etag = r.headers.get("etag")
    if etag:
        again = client.get("/", headers={"If-None-Match": etag})
        assert again.status_code == 200, \
            "a conditional request must not 304 index.html into a stale build"


def test_spa_routes_serve_uncacheable_html_too():
    """The deep-link fallback returns the same document, so it needs the same
    protection — otherwise refreshing on /investigation restores the bug."""
    r = client.get("/investigation")
    if r.status_code == 404:
        pytest.skip("no built web/dist in this checkout")
    assert "no-store" in r.headers.get("cache-control", "")


def test_hashed_assets_are_cached_hard():
    """The corollary: index.html is only cheap to re-fetch because the bulk of
    the payload beside it is content-addressed and cacheable forever."""
    import pathlib

    assets = pathlib.Path(__file__).resolve().parent.parent / "web" / "dist" / "assets"
    if not assets.exists():
        pytest.skip("no built web/dist in this checkout")
    name = next((p.name for p in assets.glob("*.js")), None)
    if name is None:
        pytest.skip("no built JS asset")

    r = client.get(f"/assets/{name}")
    assert r.status_code == 200
    assert "immutable" in r.headers.get("cache-control", "")


# ------------------------------------------------------------ memoisation --

def test_memoise_computes_once_for_concurrent_callers_of_the_same_key():
    """
    Checking the cache, releasing the lock and then computing let two callers
    who missed on the same key both run the whole body. That is what happened
    on a cold start: the warm-up thread and the first request computed the same
    scope simultaneously, doubling ~10s of work and, under the GIL, halving the
    CPU left for the request someone was waiting on.
    """
    import threading
    import time as _time

    from api.cache import memoise

    runs: list[int] = []

    @memoise
    def slow(x: int) -> int:
        runs.append(x)
        _time.sleep(0.3)
        return x * 2

    got: list[int] = []
    threads = [threading.Thread(target=lambda: got.append(slow(21))) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(runs) == 1, f"body ran {len(runs)} times for one key; must be single-flight"
    assert got == [42] * 8, "every caller must still receive the value"


def test_memoise_does_not_serialise_distinct_keys():
    """
    Single-flight must not become a global bottleneck — the per-key lock exists
    precisely so unrelated scopes still compute in parallel.
    """
    import threading
    import time as _time

    from api.cache import memoise

    @memoise
    def slow(x: int) -> int:
        _time.sleep(0.3)
        return x

    started = _time.perf_counter()
    threads = [threading.Thread(target=slow, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = _time.perf_counter() - started

    assert elapsed < 1.2, f"distinct keys serialised ({elapsed:.2f}s for 6 x 0.3s)"


def test_the_drill_reaches_the_planted_stockout():
    body = client.get("/v1/attribution", params={"week": WEEK, "persona": "cfo"}).json()
    path = {step["dimension"]: step["chosen"] for step in body["path"]}
    assert path.get("sku") == "ELEC-002"
    assert path.get("region") == "NL"


# ------------------------------------------------------------- telemetry --

def test_telemetry_separates_real_cost_from_cache_hits():
    body = client.get("/v1/telemetry").json()
    assert "cost_usd" in body["llm"]
    assert body["llm"]["calls"] >= body["llm"]["live_calls"]
    assert "reference rates" in body["pricing_note"]


def test_processing_split_refuses_to_answer_from_a_warm_cache():
    """
    It reported 98% LLM when measured on demand, because the deterministic
    stages were all cache hits at 0ms. It now serves timings captured cold at
    warm-up, or admits it has none.
    """
    r = client.get("/v1/processing-split")
    if r.status_code == 503:
        assert "not measured yet" in r.json()["detail"]
        return
    body = r.json()
    assert body["measured"].startswith("once, at warm-up")
    assert body["deterministic_ms"] > body["llm_ms"]
    assert body["llm_share"] < 0.5


def test_cold_profile_is_populated_by_warming():
    """
    `warm()` is only an honest measurement of cold work if it is actually
    MEASURING cold work — every stage it times is behind a memoised function,
    so any of them the rest of the suite has already exercised for this week
    would report ~0ms without actually being fast. Clearing every stage's
    cache first is what makes this test's claim true regardless of what ran
    before it, rather than true by incidental test order.
    """
    service.COLD_PROFILE.clear()
    for fn in (service.movements_for, service.decomposition_for, service.drill_for,
               service.assessment_for, service.recommendations_for, service.narrative_for):
        fn.cache_clear()
    service.warm(WEEK)
    assert service.COLD_PROFILE["deterministic_ms"] > 0
    assert service.COLD_PROFILE["llm_share"] < 0.5


# ---------------------------------------------------------- integrations --

def test_integration_test_reports_the_real_warehouse_not_a_fabricated_one():
    """
    Fix 4: this endpoint used to `sleep(2.5)` and always return
    `tables_found: 14` no matter what was posted. It must now report numbers
    that actually come from querying DuckDB, and they must be real — the
    retail contract's four sources, with row counts that match the built
    warehouse — not a constant.
    """
    r = client.post("/v1/integrations/test",
                    json={"engine": "snowflake", "host": "x", "database": "y"})
    assert r.status_code == 200
    body = r.json()

    assert body["tables_found"] == 4
    assert body["missing_sources"] == "none"
    assert "14" not in body["message"]           # the old fabricated constant
    assert body["elapsed_ms"] < 500, "a real DuckDB count() should be fast, not a 2.5s fake sleep"
    for source, table in (("sales", "fct_sales"), ("traffic", "fct_traffic"),
                          ("marketing", "fct_marketing_weekly"), ("inventory", "fct_inventory")):
        assert f"{source}={table} (" in body["tables"]

    # the KPI count must reflect the ACTIVE contract, not a hardcoded 5
    assert body["kpis_generated"] == len(service.contract().kpi_ids)


def test_integration_test_still_simulates_the_auth_failure_path():
    r = client.post("/v1/integrations/test", json={"engine": "postgresql", "user": "fail"})
    assert r.status_code == 401


# -------------------------------------------------------- the feedback loop --

def test_posted_feedback_persists_and_lowers_a_later_assessment(monkeypatch):
    """
    Fix 1, at the HTTP boundary: POST /v1/feedback must not just record a row
    — it must persist the learned driver priors and invalidate the cached
    assessment, so the very next GET /v1/insight reflects it. Runs against an
    isolated in-memory store (monkeypatched in) so it never touches the real
    warehouse/feedback.duckdb file on disk.
    """
    import duckdb

    from feedback.store import DuckDBStore

    real_store = service._STORE
    test_store = DuckDBStore(duckdb.connect(":memory:"))
    monkeypatch.setattr(service, "_STORE", test_store)
    service.assessment_for.cache_clear()

    try:
        before = client.get("/v1/insight", params={"week": WEEK, "persona": "cfo"}).json()
        credited = {d for c in before["causes"] for d in c["drivers"]}
        assert "discount_depth" in credited, "discount_depth must be credited before feedback"

        for _ in range(20):
            r = client.post("/v1/feedback", json={
                "kpi": "net_revenue", "iso_week": WEEK, "persona": "analyst",
                "verdict": "wrong_driver", "driver": "discount_depth",
                "correct_driver": "fill_rate", "confidence_shown": before["confidence"]["score"],
            })
            assert r.status_code == 201
            # fill_rate also appears in `drivers_updated` — it is tracked as the
            # named replacement (`missed_by_engine`) even though it has never
            # itself been credited in this store
            assert "discount_depth" in r.json()["relearned"]["drivers_updated"]

        assert test_store.params("driver_prior")["net_revenue:discount_depth"]["weight"] < 1.0

        after = client.get("/v1/insight", params={"week": WEEK, "persona": "cfo"}).json()
        assert after["confidence"]["score"] < before["confidence"]["score"]
    finally:
        # `relearn()` cleared assessment/recommendation/narrative caches against
        # the FAKE store above; restore the real one so nothing downstream
        # scores against this test's throwaway feedback.
        service._STORE = real_store
        service.assessment_for.cache_clear()
        service.recommendations_for.cache_clear()
        service.narrative_for.cache_clear()
