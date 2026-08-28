"""
Loads contracts/kpis.yaml.

Thin on purpose. The contract is data; this module only gives it typed-ish
accessors so the rest of the engine never reaches into raw dicts.
"""

from __future__ import annotations

import functools
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


@functools.lru_cache(maxsize=1)
def load(path: pathlib.Path | str = CONTRACT_PATH) -> Contract:
    with open(path) as fh:
        return Contract(yaml.safe_load(fh))
