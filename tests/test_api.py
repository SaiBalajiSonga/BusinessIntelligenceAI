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
    service.COLD_PROFILE.clear()
    service.warm(WEEK)
    assert service.COLD_PROFILE["deterministic_ms"] > 0
    assert service.COLD_PROFILE["llm_share"] < 0.5
