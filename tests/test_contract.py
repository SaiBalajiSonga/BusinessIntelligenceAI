"""
Fix 5 — the active contract is a config choice, not a hardcoded path.

`contracts/kpis_saas.yaml` existed before this fix but was never loadable:
`engine/contract.py` hardcoded the retail path, so nothing could point at it.
These tests prove `KPI_CONTRACT_PATH` genuinely switches the active vertical,
that the default (unset) behaviour is unchanged, and that the SaaS contract is
a real, structurally complete contract — not a metadata stub.
"""

from __future__ import annotations

import pathlib

import pytest

from engine.contract import CONTRACT_PATH, active_contract_path, load

SAAS_PATH = pathlib.Path(__file__).resolve().parent.parent / "contracts" / "kpis_saas.yaml"


def test_the_default_path_is_retail_when_unset(monkeypatch):
    monkeypatch.delenv("KPI_CONTRACT_PATH", raising=False)
    assert active_contract_path() == CONTRACT_PATH


def test_the_env_var_overrides_the_default_path(monkeypatch):
    monkeypatch.setenv("KPI_CONTRACT_PATH", str(SAAS_PATH))
    assert active_contract_path() == SAAS_PATH


def test_load_with_no_argument_tracks_the_env_var_live(monkeypatch):
    """
    The resolution must happen OUTSIDE the lru_cache — caching the unresolved
    default would freeze whichever contract was loaded first for the life of
    the process, and a later change to KPI_CONTRACT_PATH would silently do
    nothing.
    """
    monkeypatch.delenv("KPI_CONTRACT_PATH", raising=False)
    retail = load()
    assert "net_revenue" in retail.kpi_ids

    monkeypatch.setenv("KPI_CONTRACT_PATH", str(SAAS_PATH))
    saas = load()
    assert "net_revenue" not in saas.kpi_ids
    assert "mrr" in saas.kpi_ids

    monkeypatch.delenv("KPI_CONTRACT_PATH", raising=False)
    assert "net_revenue" in load().kpi_ids, "unsetting the override must fall back to retail"


def test_the_saas_contract_is_a_real_kpi_set_not_a_stub():
    c = load(SAAS_PATH)
    assert set(c.kpi_ids) == {"mrr", "churn_mrr", "dau_to_mau", "cac"}
    assert c.currency == "USD"
    assert c.kpi("mrr")["label"] == "Monthly Recurring Revenue (MRR)"


@pytest.mark.parametrize("section", [
    "personas", "confidence", "attribution", "causal", "decompositions", "drivers", "levers",
])
def test_the_saas_contract_carries_every_section_the_api_needs(section):
    """
    `GET /v1/contract` reads `sources`, `drivers`, `levers`, `personas`,
    `confidence`, `attribution`, `causal` and `decompositions` off the raw
    contract directly — any one of these missing turns "point the server at
    kpis_saas.yaml" into a 500 on the very endpoint meant to prove it works.
    """
    c = load(SAAS_PATH)
    assert section in c.raw and c.raw[section], f"kpis_saas.yaml is missing its {section!r} section"


def test_the_saas_contract_defines_a_decomposition_for_its_headline_kpi():
    c = load(SAAS_PATH)
    assert c.decomposition("mrr") is not None


def test_the_saas_contract_defines_personas_with_a_masked_column():
    c = load(SAAS_PATH)
    masked = {p: c.persona(p)["masked_columns"] for p in c.personas}
    assert any(cols for cols in masked.values()), \
        "the SaaS contract should exercise column-level masking too, like the retail one does"


def test_retail_contract_is_unaffected_by_the_saas_contract_existing():
    """The default path must keep behaving exactly as before this fix."""
    c = load(CONTRACT_PATH)
    assert "net_revenue" in c.kpi_ids
    assert c.currency == "GBP"


# ------------------------------------------------------- the API surface --

def test_the_api_persona_list_is_read_from_the_active_contract_not_hardcoded():
    """
    `api/main.py` used to validate personas against a literal
    `PERSONAS = ("cfo", "eu_category_manager", "analyst")` tuple — which would
    have rejected every persona the SaaS contract defines, regardless of what
    KPI_CONTRACT_PATH pointed to. `_persona_ids()` must instead read the
    active contract, so a second vertical's personas are genuinely usable.
    """
    from api import main, service

    original = service._CONTRACT
    try:
        service._CONTRACT = load(SAAS_PATH)
        assert set(main._persona_ids()) == {"cfo", "customer_success_manager", "analyst"}
        main._persona("customer_success_manager")  # must not raise
        with pytest.raises(Exception):
            main._persona("eu_category_manager")   # a retail-only persona, now unknown
    finally:
        service._CONTRACT = original
