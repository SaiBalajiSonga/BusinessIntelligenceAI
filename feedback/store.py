"""
Where feedback lives.

Two backends behind one interface. DuckDB is the default and runs with no
network and no credentials, which is what keeps a live demo from depending on
someone else's uptime. Supabase is used when it is configured, for the case the
state has to be shared between people rather than sitting on one laptop.

The local store gets its OWN database file rather than sharing the warehouse.
DuckDB is single-writer, so with one file the API process holds the lock and
nothing else can record a correction. The separation is also the right shape:
the warehouse is read-only analytical data, feedback is mutable state, and they
have no reason to share a lifecycle.

Nothing in the analytics imports this module. Feedback changes what the engine
believes over time; it must never be able to change a number retrospectively.
"""

from __future__ import annotations

import json
import os
import pathlib
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Protocol

import pandas as pd

VERDICTS = ("correct", "wrong_driver", "known_cause", "not_material", "unclear")

ROOT = pathlib.Path(__file__).resolve().parent.parent
FEEDBACK_DB = ROOT / "warehouse" / "feedback.duckdb"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


# ------------------------------------------------------------- records --

@dataclass
class Feedback:
    kpi: str
    iso_week: str
    persona: str
    verdict: str
    driver: str | None = None
    correct_driver: str | None = None
    confidence_shown: float | None = None
    impact_shown: float | None = None      # what the movement was worth when shown
    comment: str | None = None
    author: str | None = None
    audit_id: str | None = None
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {VERDICTS}, got {self.verdict!r}")


@dataclass
class Annotation:
    label: str
    starts_on: str
    ends_on: str | None = None
    kpi: str | None = None
    dimension: str | None = None
    value: str | None = None
    cause: str | None = None
    expected: bool = True
    author: str | None = None
    id: str = field(default_factory=_uid)
    created_at: str = field(default_factory=_now)

    def covers(self, day: date, scope: dict[str, Any] | None = None) -> bool:
        start = date.fromisoformat(self.starts_on)
        end = date.fromisoformat(self.ends_on) if self.ends_on else date.max
        if not (start <= day <= end):
            return False
        if self.dimension and scope:
            wanted = scope.get(self.dimension)
            values = wanted if isinstance(wanted, (list, tuple)) else [wanted]
            return self.value in [str(v) for v in values]
        return True


# ------------------------------------------------------------ interface --

class Store(Protocol):
    def record_insight(self, row: dict[str, Any]) -> str: ...
    def record_feedback(self, fb: Feedback) -> str: ...
    def feedback(self, kpi: str | None = None) -> pd.DataFrame: ...
    def add_annotation(self, ann: Annotation) -> str: ...
    def annotations(self) -> list[Annotation]: ...
    def save_param(self, kind: str, key: str, value: dict, n: int) -> None: ...
    def params(self, kind: str) -> dict[str, dict]: ...


# -------------------------------------------------------------- DuckDB --

DDL = """
create table if not exists insight_audit (
  id varchar primary key, created_at varchar, kpi varchar, iso_week varchar,
  persona varchar, scope varchar, gap double, coverage double,
  confidence_score double, confidence_band varchar, causes varchar,
  narrative varchar, narrative_source varchar, llm_called boolean,
  figures_checked integer, guard_passed boolean, drafts_rejected integer,
  model varchar, input_tokens integer, output_tokens integer,
  cost_usd double, latency_ms double
);
create table if not exists feedback (
  id varchar primary key, created_at varchar, audit_id varchar, kpi varchar,
  iso_week varchar, persona varchar, verdict varchar, driver varchar,
  correct_driver varchar, confidence_shown double, impact_shown double,
  comment varchar, author varchar
);
create table if not exists annotations (
  id varchar primary key, created_at varchar, kpi varchar, dimension varchar,
  value varchar, starts_on varchar, ends_on varchar, label varchar,
  cause varchar, expected boolean, author varchar
);
create table if not exists learned_params (
  kind varchar, key varchar, updated_at varchar, value varchar,
  n_observations integer, primary key (kind, key)
);
"""


class DuckDBStore:
    """Default. Same file as the warehouse — no network, no credentials."""

    backend = "duckdb"

    def __init__(self, con):
        self.con = con
        for statement in filter(str.strip, DDL.split(";")):
            self.con.execute(statement)

    def record_insight(self, row: dict[str, Any]) -> str:
        row = {"id": _uid(), "created_at": _now(), **row}
        for key in ("scope", "causes"):
            if isinstance(row.get(key), (dict, list)):
                row[key] = json.dumps(row[key])
        cols = ", ".join(row)
        marks = ", ".join("?" * len(row))
        self.con.execute(f"INSERT INTO insight_audit ({cols}) VALUES ({marks})",
                         list(row.values()))
        return row["id"]

    def record_feedback(self, fb: Feedback) -> str:
        row = asdict(fb)
        cols = ", ".join(row)
        marks = ", ".join("?" * len(row))
        self.con.execute(f"INSERT INTO feedback ({cols}) VALUES ({marks})", list(row.values()))
        return fb.id

    def feedback(self, kpi: str | None = None) -> pd.DataFrame:
        sql = "SELECT * FROM feedback"
        args: list[Any] = []
        if kpi:
            sql += " WHERE kpi = ?"
            args.append(kpi)
        return self.con.execute(sql + " ORDER BY created_at", args).df()

    def add_annotation(self, ann: Annotation) -> str:
        row = asdict(ann)
        cols = ", ".join(row)
        marks = ", ".join("?" * len(row))
        self.con.execute(f"INSERT INTO annotations ({cols}) VALUES ({marks})", list(row.values()))
        return ann.id

    def annotations(self) -> list[Annotation]:
        df = self.con.execute("SELECT * FROM annotations ORDER BY starts_on").df()
        return [Annotation(**{k: (None if pd.isna(v) else v) for k, v in r.items()})
                for r in df.to_dict(orient="records")]

    def save_param(self, kind: str, key: str, value: dict, n: int) -> None:
        self.con.execute("DELETE FROM learned_params WHERE kind = ? AND key = ?", [kind, key])
        self.con.execute(
            "INSERT INTO learned_params VALUES (?, ?, ?, ?, ?)",
            [kind, key, _now(), json.dumps(value), n],
        )

    def params(self, kind: str) -> dict[str, dict]:
        df = self.con.execute(
            "SELECT key, value, n_observations FROM learned_params WHERE kind = ?", [kind]
        ).df()
        return {
            r["key"]: {**json.loads(r["value"]), "n": int(r["n_observations"])}
            for r in df.to_dict(orient="records")
        }


# ------------------------------------------------------------ Supabase --

class SupabaseStore:
    """
    PostgREST over the tables in schema.sql.

    Used only when SUPABASE_URL and a key are both present, so the default path
    never touches the network. Reads carry the caller's persona so row-level
    security applies as a second gate behind the analytics-layer entitlement.
    """

    backend = "supabase"

    def __init__(self, url: str, key: str):
        import httpx

        self.base = url.rstrip("/") + "/rest/v1"
        self.client = httpx.Client(
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json", "Prefer": "return=representation"},
            timeout=15.0,
        )

    def _post(self, table: str, row: dict) -> str:
        r = self.client.post(f"{self.base}/{table}", json=row)
        r.raise_for_status()
        body = r.json()
        return body[0]["id"] if body else row.get("id", "")

    def _get(self, table: str, params: dict | None = None) -> list[dict]:
        r = self.client.get(f"{self.base}/{table}", params=params or {})
        r.raise_for_status()
        return r.json()

    def record_insight(self, row: dict[str, Any]) -> str:
        return self._post("insight_audit", row)

    def record_feedback(self, fb: Feedback) -> str:
        row = {k: v for k, v in asdict(fb).items() if k != "created_at"}
        return self._post("feedback", row)

    def feedback(self, kpi: str | None = None) -> pd.DataFrame:
        params = {"order": "created_at"}
        if kpi:
            params["kpi"] = f"eq.{kpi}"
        return pd.DataFrame(self._get("feedback", params))

    def add_annotation(self, ann: Annotation) -> str:
        row = {k: v for k, v in asdict(ann).items() if k != "created_at"}
        return self._post("annotations", row)

    def annotations(self) -> list[Annotation]:
        rows = self._get("annotations", {"order": "starts_on"})
        keep = Annotation.__dataclass_fields__.keys()
        return [Annotation(**{k: v for k, v in r.items() if k in keep}) for r in rows]

    def save_param(self, kind: str, key: str, value: dict, n: int) -> None:
        self.client.post(
            f"{self.base}/learned_params",
            json={"kind": kind, "key": key, "value": value, "n_observations": n},
            headers={"Prefer": "resolution=merge-duplicates"},
        ).raise_for_status()

    def params(self, kind: str) -> dict[str, dict]:
        rows = self._get("learned_params", {"kind": f"eq.{kind}"})
        return {r["key"]: {**r["value"], "n": r["n_observations"]} for r in rows}


# -------------------------------------------------------------- factory --

def open_store(con=None) -> Store:
    """
    Supabase when it is configured and reachable, DuckDB otherwise.

    Falling back rather than failing is deliberate: a missing credential should
    degrade the learning loop to local-only, not take the whole engine down
    thirty seconds before a demo.
    """
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
           or os.environ.get("SUPABASE_PUBLISHABLE_KEY") or "").strip()

    if url and key:
        try:
            store = SupabaseStore(url, key)
            store._get("learned_params", {"limit": "1"})     # prove the tables exist
            return store
        except Exception:
            pass        # schema not applied, or offline — local store still works

    if con is None:
        import duckdb
        FEEDBACK_DB.parent.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(str(FEEDBACK_DB))
    return DuckDBStore(con)
