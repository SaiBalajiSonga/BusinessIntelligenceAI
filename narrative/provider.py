"""
The LLM boundary.

One interface, several backends. Groq, NVIDIA, OpenRouter and Ollama are all
OpenAI-compatible, so switching provider is a change of environment variables
rather than of code. `mock` returns deterministic canned text with no network at
all, which is what lets the rest of the system be developed and demonstrated
without a key.

Every call is measured — latency, tokens, cost at reference pricing, cache
hit or miss — because "what does an insight cost" is a question the brief asks
directly and it cannot be answered retrospectively.

The cache is keyed on the exact prompt, so the same evidence never pays twice.
On a free tier that is not an optimisation, it is what stops a live demo dying
on a rate limit.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import time
from dataclasses import asdict, dataclass, field

from engine.contract import Contract, load

ROOT = pathlib.Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- results --

@dataclass
class Completion:
    text: str
    model: str
    provider: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cached: bool = False
    cost_usd: float = 0.0
    finish_reason: str = "stop"
    attempt: int = 1

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class Telemetry:
    """Every LLM call this process made. Rendered in the cost panel."""
    calls: list[Completion] = field(default_factory=list)

    def record(self, c: Completion) -> Completion:
        self.calls.append(c)
        return c

    def reset(self) -> None:
        self.calls.clear()

    @property
    def live_calls(self) -> list[Completion]:
        return [c for c in self.calls if not c.cached]

    def summary(self) -> dict[str, float | int]:
        live = self.live_calls
        return {
            "calls": len(self.calls),
            "live_calls": len(live),
            "cache_hits": len(self.calls) - len(live),
            "input_tokens": sum(c.input_tokens for c in live),
            "output_tokens": sum(c.output_tokens for c in live),
            "cost_usd": sum(c.cost_usd for c in live),
            "total_latency_ms": sum(c.latency_ms for c in self.calls),
            "p50_latency_ms": _median([c.latency_ms for c in live]),
        }


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2


TELEMETRY = Telemetry()


# ------------------------------------------------------------------ cache --

class PromptCache:
    def __init__(self, path: pathlib.Path | None, enabled: bool = True):
        self.path = path
        self.enabled = enabled
        self._mem: dict[str, dict] = {}
        if enabled and path and path.exists():
            try:
                self._mem = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                self._mem = {}      # a corrupt cache is not worth an exception

    @staticmethod
    def key(model: str, system: str, user: str, temperature: float) -> str:
        blob = json.dumps([model, system, user, temperature], sort_keys=True)
        return hashlib.sha256(blob.encode()).hexdigest()[:32]

    def get(self, key: str) -> Completion | None:
        if not self.enabled or key not in self._mem:
            return None
        return Completion(**{**self._mem[key], "cached": True, "latency_ms": 0.0})

    def put(self, key: str, c: Completion) -> None:
        if not self.enabled:
            return
        self._mem[key] = asdict(c)
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._mem, indent=1))

    def __len__(self) -> int:
        return len(self._mem)


# -------------------------------------------------------------- providers --

class MockProvider:
    """
    Deterministic, offline, no key. Echoes only figures it was given, so the
    validator sees a well-behaved witness by default; tests inject bad output
    deliberately rather than waiting for a model to misbehave.
    """
    name = "mock"

    def __init__(self, model: str = "mock-1", canned: str | None = None):
        self.model = model
        self.canned = canned

    def complete(self, system: str, user: str, max_tokens: int, temperature: float) -> Completion:
        t0 = time.perf_counter()
        text = self.canned if self.canned is not None else _echo(user)
        return Completion(
            text=text, model=self.model, provider=self.name,
            latency_ms=(time.perf_counter() - t0) * 1000,
            input_tokens=len(system + user) // 4, output_tokens=len(text) // 4,
        )


def _echo(user: str) -> str:
    """Reflect the evidence lines back as prose — every number is one we were given."""
    facts = [ln.strip() for ln in user.splitlines() if ":" in ln and any(ch.isdigit() for ch in ln)]
    if not facts:
        return "No material movement to report."
    head = facts[0]
    rest = "; ".join(facts[1:4])
    return f"{head}. Contributing factors: {rest}." if rest else f"{head}."


class OpenAICompatibleProvider:
    """Groq, NVIDIA NIM, OpenRouter, Ollama — all speak the same dialect."""

    def __init__(self, name: str, model: str, api_key: str, base_url: str,
                 pricing: tuple[float, float], timeout: float = 60.0):
        from openai import OpenAI      # imported lazily so `mock` needs no dependency

        self.name = name
        self.model = model
        self.pricing = pricing
        self._client = OpenAI(api_key=api_key or "not-needed", base_url=base_url,
                              timeout=timeout, max_retries=1)

    def complete(self, system: str, user: str, max_tokens: int, temperature: float) -> Completion:
        t0 = time.perf_counter()
        r = self._client.chat.completions.create(
            model=self.model, max_tokens=max_tokens, temperature=temperature,
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": user}],
        )
        latency = (time.perf_counter() - t0) * 1000
        usage = r.usage
        in_tok = usage.prompt_tokens if usage else 0
        out_tok = usage.completion_tokens if usage else 0
        cost = (in_tok * self.pricing[0] + out_tok * self.pricing[1]) / 1_000_000

        return Completion(
            text=(r.choices[0].message.content or "").strip(),
            model=self.model, provider=self.name, latency_ms=latency,
            input_tokens=in_tok, output_tokens=out_tok, cost_usd=cost,
            finish_reason=r.choices[0].finish_reason or "stop",
        )


# ------------------------------------------------------------------ front --

class LLM:
    """Provider + cache + telemetry. The only thing the rest of the code sees."""

    def __init__(self, contract: Contract | None = None, provider: str | None = None,
                 canned: str | None = None):
        contract = contract or load()
        cfg = contract.raw["llm"]
        self.cfg = cfg
        self.max_tokens = int(cfg["max_output_tokens"])
        self.temperature = float(cfg["temperature"])
        self.retries = int(cfg["retry_on_validation_failure"])

        price = cfg["reference_pricing_usd_per_mtok"]
        pricing = (float(price["input"]), float(price["output"]))

        cache_cfg = cfg.get("cache", {})
        self.cache = PromptCache(
            ROOT / cache_cfg["path"] if cache_cfg.get("path") else None,
            enabled=bool(cache_cfg.get("enabled", True)),
        )

        name = (provider or os.environ.get("LLM_PROVIDER") or "mock").strip().lower()
        model = os.environ.get("LLM_MODEL", "mock-1")

        if name == "mock":
            self.provider = MockProvider(model="mock-1", canned=canned)
        else:
            self.provider = OpenAICompatibleProvider(
                name=name, model=model,
                api_key=os.environ.get("LLM_API_KEY", ""),
                base_url=os.environ.get("LLM_BASE_URL", ""),
                pricing=pricing,
            )

    @property
    def model(self) -> str:
        return self.provider.model

    def complete(self, system: str, user: str, attempt: int = 1) -> Completion:
        key = PromptCache.key(self.provider.model, system, user, self.temperature)
        hit = self.cache.get(key)
        if hit is not None:
            hit.attempt = attempt
            return TELEMETRY.record(hit)

        c = self.provider.complete(system, user, self.max_tokens, self.temperature)
        c.attempt = attempt
        self.cache.put(key, c)
        return TELEMETRY.record(c)
