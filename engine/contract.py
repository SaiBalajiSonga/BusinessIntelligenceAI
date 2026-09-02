"""
Loads contracts/kpis.yaml.

Thin on purpose. The contract is data; this module only gives it typed-ish
accessors so the rest of the engine never reaches into raw dicts.
"""

from __future__ import annotations

import functools
import os
import pathlib
from typing import Any

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "contracts" / "kpis.yaml"


class Contract:
    def __init__(self, raw: dict[str, Any]):
        self._raw = raw

    # ------------------------------------------------------------- basics --

    @property
    def currency(self) -> str:
        return self._raw["currency"]

    @property
    def as_of(self) -> str:
        return self._raw["as_of"]

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw

    # --------------------------------------------------------------- KPIs --

    @property
    def kpi_ids(self) -> list[str]:
        return list(self._raw["kpis"])

    def kpi(self, kpi_id: str) -> dict[str, Any]:
        try:
            return self._raw["kpis"][kpi_id]
        except KeyError:
            raise KeyError(f"unknown KPI {kpi_id!r}; contract defines {self.kpi_ids}") from None

    def materiality(self, kpi_id: str) -> tuple[float, float]:
        m = self.kpi(kpi_id)["materiality"]
        return float(m["min_abs_delta"]), float(m["min_z"])

    def baseline_spec(self, kpi_id: str) -> dict[str, Any]:
        return self.kpi(kpi_id)["baseline"]

    # ------------------------------------------------------------ sources --

    @property
    def sources(self) -> dict[str, Any]:
        return self._raw["sources"]

    def source(self, source_id: str) -> dict[str, Any]:
        return self._raw["sources"][source_id]

    # -------------------------------------------------------------- other --

    @property
    def drivers(self) -> dict[str, Any]:
        return self._raw["drivers"]

    @property
    def personas(self) -> dict[str, Any]:
        return self._raw["personas"]

    def persona(self, persona_id: str) -> dict[str, Any]:
        try:
            return self._raw["personas"][persona_id]
        except KeyError:
            raise KeyError(
                f"unknown persona {persona_id!r}; contract defines {list(self.personas)}"
            ) from None

    def decomposition(self, kpi_id: str) -> dict[str, Any] | None:
        return self._raw.get("decompositions", {}).get(kpi_id)

    @property
    def confidence(self) -> dict[str, Any]:
        return self._raw["confidence"]


def active_contract_path() -> pathlib.Path:
    """
    Which contract file is active, resolved fresh on every call.

    `KPI_CONTRACT_PATH` makes the vertical selectable — contracts/kpis_saas.yaml
    exists precisely so a second vertical is a config choice, not decoration.
    Defaulting to the retail path when the variable is unset keeps every
    existing deployment's behaviour unchanged.
    """
    override = os.environ.get("KPI_CONTRACT_PATH", "").strip()
    return pathlib.Path(override) if override else CONTRACT_PATH


def load(path: pathlib.Path | str | None = None) -> Contract:
    """
    Load a contract, defaulting to whatever `KPI_CONTRACT_PATH` (or the retail
    path) resolves to right now. The resolution happens here, OUTSIDE the
    cache — caching on the unresolved `None` would freeze the very first
    environment seen for the life of the process, and a later change to
    `KPI_CONTRACT_PATH` (as tests that flip verticals rely on) would silently
    keep returning the first contract ever loaded.
    """
    resolved = pathlib.Path(path) if path is not None else active_contract_path()
    return _load_cached(str(resolved))


@functools.lru_cache(maxsize=8)
def _load_cached(path_str: str) -> Contract:
    with open(path_str) as fh:
        return Contract(yaml.safe_load(fh))
