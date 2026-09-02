import type {
  Actions, AnnotationIn, Attribution, Contract, FeedbackIn, Freshness,
  Insight, KpiSeries, Learning, Movement, Narrative, Persona, Split, Telemetry,
} from "./types";

const BASE = "/v1";

/**
 * Request cache.
 *
 * Navigating away and back used to re-run every request on the page. The
 * previous 30s TTL meant reading one page for half a minute guaranteed a full
 * refetch of the one you came from, and on a cold serverless container that is
 * a 10-20s wait for numbers the browser already had.
 *
 * A long TTL is correct here rather than merely convenient: the analysis for a
 * given (week, persona) is deterministic and already memoised server-side, so
 * refetching it returns byte-identical output. The one thing that genuinely
 * changes it is recorded feedback, which re-runs calibration — so mutations
 * invalidate explicitly below instead of the cache quietly aging out.
 */
const cache = new Map<string, { data: unknown; time: number }>();
const inflight = new Map<string, Promise<unknown>>();
const CACHE_TTL = 15 * 60 * 1000;

function keyOf(path: string, params: Record<string, string> = {}): string {
  const qs = new URLSearchParams(params).toString();
  return `${BASE}/${path}${qs ? `?${qs}` : ""}`;
}

/** Cached value if present and fresh, else undefined. Synchronous by design:
 *  a component can seed its state from this during render and skip the
 *  loading state entirely, which is what stops the page blanking on revisit. */
function peekKey<T>(path: string, params: Record<string, string> = {}): T | undefined {
  const hit = cache.get(keyOf(path, params));
  if (!hit || Date.now() - hit.time >= CACHE_TTL) return undefined;
  return hit.data as T;
}

/** Drop cached responses. With no prefix, drops everything. */
export function invalidate(prefix?: string): void {
  if (!prefix) { cache.clear(); return; }
  for (const k of [...cache.keys()]) {
    if (k.startsWith(`${BASE}/${prefix}`)) cache.delete(k);
  }
}

async function get<T>(path: string, params: Record<string, string> = {}): Promise<T> {
  const url = keyOf(path, params);

  const cached = cache.get(url);
  if (cached && Date.now() - cached.time < CACHE_TTL) return cached.data as T;

  // Share one request per URL. The overview asks for personas while the shell
  // is already asking, and both pages mount at once on a route change.
  const pending = inflight.get(url);
  if (pending) return pending as Promise<T>;

  const request = (async () => {
    const res = await fetch(url);
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail ?? `${path} failed (${res.status})`);
    }
    const data = await res.json();
    cache.set(url, { data, time: Date.now() });
    return data;
  })().finally(() => inflight.delete(url));

  inflight.set(url, request);
  return request as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${path} failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

/**
 * Recording feedback re-runs calibration server-side, which moves confidence
 * scores and driver priors — so every cached analysis is genuinely stale after
 * one. Without this the loop would look broken: you would submit a correction
 * and the page would keep showing the pre-correction numbers.
 */
function postThenInvalidate<T>(path: string, body: unknown, ...stale: string[]): Promise<T> {
  return post<T>(path, body).then((res) => {
    stale.forEach(invalidate);
    return res;
  });
}

const ANALYSIS = ["insight", "narrative", "actions", "attribution", "movements", "learning", "feedback"];

/**
 * Each request's path and params, defined once.
 *
 * `api.x()` fetches it and `peek.x()` reads the cache for it, both through
 * these — so the two can never disagree about a cache key, which would make
 * `peek` silently always miss and quietly restore the old behaviour.
 */
type Req = [path: string, params: Record<string, string>];

/** An optional sku is omitted from the params rather than sent as undefined,
 *  so the cache key matches the URL actually requested. */
const scoped = (week: string, persona: string, sku?: string): Record<string, string> =>
  sku ? { week, persona, sku } : { week, persona };

const REQ = {
  personas: (): Req => ["personas", {}],
  freshness: (): Req => ["freshness", {}],
  telemetry: (): Req => ["telemetry", {}],
  split: (): Req => ["processing-split", {}],
  contract: (): Req => ["contract", {}],
  series: (kpi: string, persona: string, week: string, weeks = 26): Req =>
    ["series", { kpi, persona, week, weeks: String(weeks) }],
  movements: (week: string, persona: string): Req => ["movements", { week, persona }],
  insight: (week: string, persona: string, sku?: string): Req => ["insight", scoped(week, persona, sku)],
  narrative: (week: string, persona: string, sku?: string): Req => ["narrative", scoped(week, persona, sku)],
  actions: (week: string, persona: string, sku?: string): Req => ["actions", scoped(week, persona, sku)],
  attribution: (week: string, persona: string, sku?: string): Req => ["attribution", scoped(week, persona, sku)],
  listFeedback: (kpi = "net_revenue"): Req => ["feedback", { kpi }],
  learning: (week: string, persona: string): Req => ["learning", { week, persona }],
};

export const api = {
  // Meta
  personas: () => get<Persona[]>(...REQ.personas()),
  freshness: () => get<Freshness[]>(...REQ.freshness()),
  telemetry: () => get<Telemetry>(...REQ.telemetry()),
  split: () => get<Split>(...REQ.split()),
  contract: () => get<Contract>(...REQ.contract()),
  series: (kpi: string, persona: string, week: string, weeks = 26) =>
    get<KpiSeries>(...REQ.series(kpi, persona, week, weeks)),

  // Analysis
  movements: (week: string, persona: string) =>
    get<{ week: string; movements: Movement[] }>(...REQ.movements(week, persona)),
  insight: (week: string, persona: string, sku?: string) =>
    get<Insight>(...REQ.insight(week, persona, sku)),
  narrative: (week: string, persona: string, sku?: string) =>
    get<Narrative>(...REQ.narrative(week, persona, sku)),
  actions: (week: string, persona: string, sku?: string) =>
    get<Actions>(...REQ.actions(week, persona, sku)),
  attribution: (week: string, persona: string, sku?: string) =>
    get<Attribution>(...REQ.attribution(week, persona, sku)),

  // Feedback — these change the analysis, so they drop what they invalidate
  submitFeedback: (body: FeedbackIn) =>
    postThenInvalidate<{ id: string; recorded: boolean }>("feedback", body, ...ANALYSIS),
  listFeedback: (kpi = "net_revenue") =>
    get<{ count: number; by_verdict: Record<string, number>; rows: unknown[] }>(
      ...REQ.listFeedback(kpi)
    ),
  addAnnotation: (body: AnnotationIn) =>
    postThenInvalidate<{ id: string; recorded: boolean }>("annotations", body, ...ANALYSIS),
  learning: (week: string, persona: string) => get<Learning>(...REQ.learning(week, persona)),
  testIntegration: (body: any) => post<any>("integrations/test", body),
};

/**
 * Synchronous cache reads, mirroring `api`.
 *
 * A page seeds its state from these during the first render, so returning to a
 * page you have already opened shows it immediately instead of tearing down to
 * a skeleton and re-fetching numbers that cannot have changed.
 */
export const peek = {
  personas: () => peekKey<Persona[]>(...REQ.personas()),
  contract: () => peekKey<Contract>(...REQ.contract()),
  freshness: () => peekKey<Freshness[]>(...REQ.freshness()),
  telemetry: () => peekKey<Telemetry>(...REQ.telemetry()),
  split: () => peekKey<Split>(...REQ.split()),
  series: (kpi: string, persona: string, week: string, weeks = 26) =>
    peekKey<KpiSeries>(...REQ.series(kpi, persona, week, weeks)),
  movements: (week: string, persona: string) =>
    peekKey<{ week: string; movements: Movement[] }>(...REQ.movements(week, persona)),
  insight: (week: string, persona: string, sku?: string) =>
    peekKey<Insight>(...REQ.insight(week, persona, sku)),
  narrative: (week: string, persona: string, sku?: string) =>
    peekKey<Narrative>(...REQ.narrative(week, persona, sku)),
  actions: (week: string, persona: string, sku?: string) =>
    peekKey<Actions>(...REQ.actions(week, persona, sku)),
  attribution: (week: string, persona: string, sku?: string) =>
    peekKey<Attribution>(...REQ.attribution(week, persona, sku)),
  learning: (week: string, persona: string) => peekKey<Learning>(...REQ.learning(week, persona)),
  listFeedback: (kpi = "net_revenue") =>
    peekKey<{ count: number; by_verdict: Record<string, number>; rows: unknown[] }>(
      ...REQ.listFeedback(kpi)
    ),
};

export const fmt = {
  money(v: number | null, currency = "GBP"): string {
    if (v === null || v === undefined) return "—";
    const sign = v < 0 ? "−" : "+";
    return `${sign}£${Math.abs(v).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;
  },
  moneyRaw(v: number, currency = "GBP"): string {
    return `£${Math.abs(v).toLocaleString("en-GB", { maximumFractionDigits: 0 })}`;
  },
  abs(v: number): string {
    return Math.abs(v).toLocaleString("en-GB", { maximumFractionDigits: 0 });
  },
  pct(v: number | null, digits = 0): string {
    return v === null || v === undefined ? "—" : `${(v * 100).toFixed(digits)}%`;
  },
  /** Magnitude-aware compact currency: scales to K/M/B instead of always dividing by 1e6,
   *  so a sub-£1M value like AOV doesn't render as "£0.00M". */
  compact(v: number, symbol = "£"): string {
    const abs = Math.abs(v);
    const sign = v < 0 ? "−" : "";
    if (abs >= 1e9) return `${sign}${symbol}${(abs / 1e9).toFixed(2)}B`;
    if (abs >= 1e6) return `${sign}${symbol}${(abs / 1e6).toFixed(2)}M`;
    if (abs >= 1e3) return `${sign}${symbol}${(abs / 1e3).toFixed(1)}K`;
    return `${sign}${symbol}${abs.toLocaleString("en-GB", { maximumFractionDigits: 2 })}`;
  },
  ms(v: number): string {
    return v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${Math.round(v)}ms`;
  },
  date(iso: string): string {
    try { return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }); }
    catch { return iso; }
  },
};
