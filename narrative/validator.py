"""
The numeric guard.

Every figure in generated prose is extracted and checked against the evidence
object it was rendered from. A number that is not in the evidence did not come
from the analytics — it came from the model, and it does not ship.

This is what turns "the LLM is not the source of quantitative truth" from a
claim in a slide into a property of the system.

Two judgement calls, both deliberate:

  ROUNDING IS ALLOWED, INVENTION IS NOT. -881,627 may be rendered as "881.6K"
  or "0.88 million"; a ratio of 0.672 may appear as "67.2%". These are the same
  fact in different clothes. A relative tolerance covers the rounding; anything
  outside it is a different number.

  SMALL INTEGERS ARE PROSE, NOT CLAIMS. "two drivers", "3 regions", "2026-W32"
  are not quantitative assertions. Flagging them would make the validator cry
  wolf until someone switched it off, which is the real failure mode. The
  threshold is in the contract, not buried here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# sign, optional currency, digits (with thousands separators or decimals),
# optional magnitude or percent suffix
NUMBER = re.compile(
    r"""
    (?P<sign>[-−–]?)\s*
    (?P<cur>[£$€]?)\s*
    (?P<num>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d*\.\d+|\d+)
    \s*
    (?P<suffix>%|bn\b|billion\b|million\b|thousand\b|[KkMm](?![A-Za-z]))?
    """,
    re.VERBOSE,
)

SUFFIX_SCALE = {
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "million": 1e6,
    "bn": 1e9, "billion": 1e9,
}

ISO_WEEK = re.compile(r"(\d{4})-W(\d{1,2})")


@dataclass(frozen=True)
class Figure:
    raw: str
    value: float
    is_percent: bool
    start: int
    end: int


@dataclass
class Validation:
    ok: bool
    figures: list[Figure] = field(default_factory=list)
    violations: list[Figure] = field(default_factory=list)
    allowed_count: int = 0

    def report(self) -> str:
        if self.ok:
            return f"all {len(self.figures)} figures trace to the evidence"
        bad = ", ".join(f"{v.raw!r}" for v in self.violations)
        return f"{len(self.violations)} of {len(self.figures)} figures not in evidence: {bad}"


# ---------------------------------------------------------- extraction --

def extract_figures(text: str) -> list[Figure]:
    out: list[Figure] = []
    for m in NUMBER.finditer(text):
        raw_num = m.group("num").replace(",", "")
        try:
            value = float(raw_num)
        except ValueError:
            continue

        suffix = (m.group("suffix") or "").lower().strip()
        is_percent = suffix == "%"
        if suffix in SUFFIX_SCALE:
            value *= SUFFIX_SCALE[suffix]
        if m.group("sign"):
            value = -value

        out.append(Figure(
            raw=m.group(0).strip(), value=value, is_percent=is_percent,
            start=m.start(), end=m.end(),
        ))
    return out


# ------------------------------------------------------------- evidence --

def evidence_values(evidence: Any) -> set[float]:
    """
    Every number reachable in the evidence object — including numbers embedded
    in its prose fields.

    That last part is not a loosening, it is the fix for a real false positive.
    The evidence carries human-readable justifications such as "discount depth
    0.2585 vs 0.09242 expected (+180%)" and "inventory is 72h stale against a
    24h SLA". Those figures were supplied BY the analytics, so a narrative that
    quotes them is being faithful. Scanning only structured leaves rejected them
    as inventions and pushed two of three personas to the template fallback.
    """
    found: set[float] = set()

    def walk(node: Any) -> None:
        if isinstance(node, bool) or node is None:
            return
        if isinstance(node, (int, float)):
            found.add(float(node))
        elif isinstance(node, str):
            for year, week in ISO_WEEK.findall(node):
                found.add(float(year))
                found.add(float(week))
            for fig in extract_figures(node):
                found.add(fig.value)
                if fig.is_percent:
                    found.add(fig.value / 100.0)   # "+180%" also licenses 1.80
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple, set)):
            for v in node:
                walk(v)

    walk(evidence)
    return found


def renderings(value: float) -> set[float]:
    """The same fact, legitimately dressed differently."""
    v = abs(value)
    out = {v, v * 100.0}                 # ratio rendered as a percentage
    for scale in (1e3, 1e6, 1e9):        # 881,627 rendered as 881.6K / 0.88M
        out.add(v / scale)
    return out


# ------------------------------------------------------------ validation --

def validate(
    text: str, evidence: Any, *,
    relative_tolerance: float = 0.005,
    allow_small_integers_up_to: int = 20,
    allow_years: tuple[int, int] = (2000, 2100),
) -> Validation:
    allowed = evidence_values(evidence)
    candidates: set[float] = set()
    for v in allowed:
        candidates |= renderings(v)

    figures = extract_figures(text)
    violations: list[Figure] = []

    for fig in figures:
        n = abs(fig.value)

        if n.is_integer() and n <= allow_small_integers_up_to:
            continue
        if n.is_integer() and allow_years[0] <= n <= allow_years[1]:
            continue

        probes = {n, n / 100.0} if fig.is_percent else {n}
        if not any(_close(p, c, relative_tolerance) for p in probes for c in candidates):
            violations.append(fig)

    return Validation(
        ok=not violations, figures=figures, violations=violations,
        allowed_count=len(allowed),
    )


def _close(a: float, b: float, rel: float) -> bool:
    if a == b:
        return True
    scale = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / scale <= rel
