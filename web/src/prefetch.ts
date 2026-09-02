import { api, peek, startBootstrap } from "./api";

/**
 * Load the app's data up front, so a click lands on data that is already here.
 *
 * Two stages, because the work divides cleanly:
 *
 *  1. `/v1/bootstrap` — one request carrying the contract, personas,
 *     freshness, telemetry, the week's movements, every KPI's history, and the
 *     learning state. Against a serverless backend the request *count* is the
 *     latency: each call is another chance to land on a cold container and pay
 *     the Python import from scratch. Locally this is one 0.28s call in place
 *     of fourteen totalling 4.2s, and the gap only widens when the containers
 *     are cold.
 *
 *  2. The per-scenario analysis behind Investigate, fetched in parallel once
 *     the bootstrap is done. These four share a single assessment server-side,
 *     so asking together costs barely more than asking for one.
 *
 * The earlier version of this walked a list serially after waiting for an idle
 * callback, which on a cold backend meant a viewer could easily click through
 * before the queue had moved — the situation this is meant to prevent. Nothing
 * here blocks rendering: it is all cache-filling, and a request that fails is
 * simply a page that loads normally later.
 */

const FIRST_SCENARIO_PERSONA = "cfo";

/** What Investigate opens on, and what the other scenarios switch to. */
function analysisTargets(week: string): { persona: string; sku?: string }[] {
  return [
    { persona: FIRST_SCENARIO_PERSONA },
    { persona: "eu_category_manager" },
    { persona: "analyst", sku: "HOME-NEW-01" },
  ];
}

function prefetchAnalysis(week: string, target: { persona: string; sku?: string }): Promise<unknown> {
  const { persona, sku } = target;
  // Cheap to ask for together: all four read the same cached assessment.
  return Promise.all([
    peek.insight(week, persona, sku) ? null : api.insight(week, persona, sku),
    peek.narrative(week, persona, sku) ? null : api.narrative(week, persona, sku),
    peek.attribution(week, persona, sku) ? null : api.attribution(week, persona, sku),
    peek.actions(week, persona, sku) ? null : api.actions(week, persona, sku),
  ]).catch(() => {});
}

let started = false;

/** Idempotent — the shell may mount twice in development. */
export function prefetchAll(week: string, persona: string): () => void {
  if (started) return () => {};
  started = true;

  let cancelled = false;

  (async () => {
    try {
      await startBootstrap(week, persona);
    } catch {
      /* the pages will fetch what they need themselves */
    }
    if (cancelled) return;

    // The first scenario first — it is the one a click is most likely to want
    // — then the rest, so the common case is not queued behind the others.
    const [first, ...rest] = analysisTargets(week);
    await prefetchAnalysis(week, first);
    if (cancelled) return;

    // Only now: /v1/learning reports calibrated confidence, so it reaches for
    // the same assessment the analysis above just computed. Asked before that
    // it is one of the slowest calls in the app; asked after, it is nearly
    // free — which is why it is here and not in the bootstrap.
    if (!peek.learning(week, persona)) {
      await api.learning(week, persona).catch(() => {});
    }
    if (cancelled) return;

    await Promise.all(rest.map((t) => prefetchAnalysis(week, t)));
  })();

  return () => { cancelled = true; started = false; };
}
