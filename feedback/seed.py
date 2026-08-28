"""
Seeded history, so the loop has something to have learned from.

A calibration curve needs a track record, and this project is three days old.
Rather than pretend otherwise, the seed injects a KNOWN miscalibration — the
engine is systematically overconfident, claiming 0.75 where it is right about
62% of the time — and the loop is then asked to find and correct it. That is a
harder test than real feedback would be at this sample size, because the answer
is known in advance and the correction is measurable.

Every seeded row is marked `author='seed'`, so it can be excluded or deleted.

    python -m feedback.seed          # write the history
    python -m feedback.seed --clear  # remove it
"""

from __future__ import annotations

import sys

import numpy as np

from feedback.store import Annotation, Feedback, Store, open_store

SEED_AUTHOR = "seed"
N_ROWS = 70
RNG_SEED = 4242

# The miscalibration being planted: true correctness = score ** 1.6, which sits
# below the diagonal everywhere — overconfidence, the failure mode that actually
# matters, because it is the one that gets a recommendation acted on.
def true_rate(score: float) -> float:
    return float(score ** 1.6)


DRIVERS = ["discount_depth", "marketing_spend", "fill_rate", "competitor_price_index"]

# how often each driver's attribution has held up historically
DRIVER_RELIABILITY = {
    "discount_depth": 0.90,      # exact, measured at source — rarely wrong
    "marketing_spend": 0.70,     # allocated from a weekly feed
    "fill_rate": 0.80,
    "competitor_price_index": 0.35,   # inferred, never observed — often wrong
}


def seed(store: Store, kpi: str = "net_revenue") -> dict[str, int]:
    rng = np.random.default_rng(RNG_SEED)
    written = {"feedback": 0, "annotations": 0}

    for i in range(N_ROWS):
        score = float(rng.uniform(0.40, 0.95))
        driver = str(rng.choice(DRIVERS, p=[0.3, 0.3, 0.25, 0.15]))

        # correctness reflects both the engine's calibration and the driver's
        # own track record, so the priors have something real to pick up
        p = true_rate(score) * DRIVER_RELIABILITY[driver]
        correct = bool(rng.random() < p)

        week = f"2026-W{(i % 26) + 1:02d}"
        if correct:
            verdict, corrected = ("correct", None)
        elif rng.random() < 0.75:
            verdict = "wrong_driver"
            corrected = str(rng.choice([d for d in DRIVERS if d != driver]))
        else:
            verdict, corrected = ("unclear", None)

        store.record_feedback(Feedback(
            kpi=kpi, iso_week=week, persona="analyst", verdict=verdict,
            driver=driver, correct_driver=corrected,
            confidence_shown=round(score, 4),
            impact_shown=float(rng.uniform(120_000, 900_000)),
            author=SEED_AUTHOR,
        ))
        written["feedback"] += 1

    # movements repeatedly judged real but not worth sending — the materiality
    # signal, deliberately clustered at the low end
    for i in range(8):
        store.record_feedback(Feedback(
            kpi=kpi, iso_week=f"2026-W{i + 4:02d}", persona="cfo",
            verdict="not_material", confidence_shown=float(rng.uniform(0.6, 0.9)),
            impact_shown=float(rng.uniform(150_000, 260_000)),
            comment="real, but below what I would act on", author=SEED_AUTHOR,
        ))
        written["feedback"] += 1

    for ann in (
        Annotation(
            label="Beauty entry-price campaign", starts_on="2026-07-13", ends_on="2026-08-23",
            kpi=kpi, dimension="category", value="Beauty",
            cause="planned acquisition push; mix shift toward cheaper lines is intended",
            expected=True, author=SEED_AUTHOR,
        ),
        Annotation(
            label="ELEC-002 supplier delay", starts_on="2026-07-27", ends_on="2026-08-16",
            kpi=kpi, dimension="sku", value="ELEC-002",
            cause="known freight backlog, replenishment already expedited",
            expected=False, author=SEED_AUTHOR,
        ),
    ):
        store.add_annotation(ann)
        written["annotations"] += 1

    return written


def clear(store: Store) -> None:
    con = getattr(store, "con", None)
    if con is None:
        raise RuntimeError("clear is only implemented for the local store")
    con.execute("DELETE FROM feedback WHERE author = ?", [SEED_AUTHOR])
    con.execute("DELETE FROM annotations WHERE author = ?", [SEED_AUTHOR])
    con.execute("DELETE FROM learned_params")


def main() -> None:
    store = open_store()
    if "--clear" in sys.argv:
        clear(store)
        print(f"cleared seeded rows from the {store.backend} store")
        return

    counts = seed(store)
    print(f"store: {store.backend}")
    print(f"  feedback rows  {counts['feedback']}")
    print(f"  annotations    {counts['annotations']}")
    print("\nplanted miscalibration: true correctness = claimed ** 1.6 (overconfident)")
    print("run `python -m feedback.learn` to see whether the loop recovers it")


if __name__ == "__main__":
    main()
