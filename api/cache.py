"""
Memoisation, and the stopwatch that splits deterministic work from LLM work.

A cold assessment is about seven seconds — it fits roughly two hundred STL
fits, a decomposition, a dimensional drill and a panel regression. That is fine
for a scheduled digest and unacceptable behind a click, so results are cached on
the arguments that produced them. The warehouse is static within a run, so there
is nothing to invalidate.

The stopwatch exists because the brief asks for a clear breakdown of LLM versus
non-LLM processing, and that cannot be reconstructed after the fact.
"""

from __future__ import annotations

import functools
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0

    @property
    def entries(self) -> int:
        return self.misses

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


STATS = CacheStats()
_LOCK = threading.Lock()


def memoise(fn):
    """
    Keyed on the call arguments, and single-flight per key.

    Thread-safe matters here because uvicorn runs sync endpoints in a worker
    pool and two clicks can land at once — but so does not computing the same
    thing twice. Checking the store, releasing the lock and then computing
    meant two callers who missed on the same key both ran the full assessment:
    on a cold start the warm-up thread and the first real request raced to
    compute exactly the same scope, doubling ~10s of pandas and statsmodels
    work and, under the GIL, halving the CPU available to the request that
    someone was actually waiting on.

    So each key gets its own lock: the first caller computes, later callers for
    that same key wait and take its result. The global lock is only ever held
    for dict access, never across the computation, so unrelated keys still run
    concurrently.
    """
    store: dict[tuple, object] = {}
    locks: dict[tuple, threading.Lock] = {}

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        key = (args, tuple(sorted(kwargs.items())))
        with _LOCK:
            if key in store:
                STATS.hits += 1
                return store[key]
            lock = locks.setdefault(key, threading.Lock())

        with lock:
            # Whoever held this lock before us may have just stored the value.
            with _LOCK:
                if key in store:
                    STATS.hits += 1
                    return store[key]
            value = fn(*args, **kwargs)
            with _LOCK:
                store[key] = value
                STATS.misses += 1
                locks.pop(key, None)
            return value

    def cache_clear() -> None:
        with _LOCK:
            store.clear()

    wrapper.cache_clear = cache_clear        # type: ignore[attr-defined]
    wrapper.cache_size = lambda: len(store)  # type: ignore[attr-defined]
    return wrapper


# ------------------------------------------------------------- stopwatch --

@dataclass
class Stage:
    name: str
    kind: str          # "deterministic" | "llm"
    ms: float


@dataclass
class Timings:
    stages: list[Stage] = field(default_factory=list)

    @contextmanager
    def track(self, name: str, kind: str = "deterministic"):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.stages.append(Stage(name, kind, (time.perf_counter() - t0) * 1000))

    def summary(self) -> dict:
        det = sum(s.ms for s in self.stages if s.kind == "deterministic")
        llm = sum(s.ms for s in self.stages if s.kind == "llm")
        total = det + llm
        return {
            "deterministic_ms": round(det, 1),
            "llm_ms": round(llm, 1),
            "total_ms": round(total, 1),
            "llm_share": round(llm / total, 4) if total else 0.0,
            "stages": [
                {"name": s.name, "kind": s.kind, "ms": round(s.ms, 1)} for s in self.stages
            ],
        }
