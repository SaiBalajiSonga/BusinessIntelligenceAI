import type {
  Actions, AnnotationIn, Attribution, Contract, FeedbackIn, Freshness,
  Insight, Learning, Movement, Narrative, Persona, Split, Telemetry,
} from "./types";

const BASE = "/v1";

const cache = new Map<string, { data: any, time: number }>();
const CACHE_TTL = 30000;

async function get<T>(path: string, params: Record<string, string> = {}): Promise<T> {
  const qs = new URLSearchParams(params).toString();
  const url = `${BASE}/${path}${qs ? `?${qs}` : ""}`;
  
  const cached = cache.get(url);
  if (cached && Date.now() - cached.time < CACHE_TTL) {
    return cached.data as T;
  }
  
  const res = await fetch(url);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${path} failed (${res.status})`);
  }
  
  const data = await res.json();
  cache.set(url, { data, time: Date.now() });
  return data as T;
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

export const api = {
  // Meta
  personas: () => get<Persona[]>("personas"),
  freshness: () => get<Freshness[]>("freshness"),
  telemetry: () => get<Telemetry>("telemetry"),
  split: () => get<Split>("processing-split"),
  contract: () => get<Contract>("contract"),

  // Analysis
  movements: (week: string, persona: string) =>
    get<{ week: string; movements: Movement[] }>("movements", { week, persona }),
  insight: (week: string, persona: string) => get<Insight>("insight", { week, persona }),
  narrative: (week: string, persona: string) => get<Narrative>("narrative", { week, persona }),
  actions: (week: string, persona: string) => get<Actions>("actions", { week, persona }),
  attribution: (week: string, persona: string) =>
    get<Attribution>("attribution", { week, persona }),

  // Feedback
  submitFeedback: (body: FeedbackIn) =>
    post<{ id: string; recorded: boolean }>("feedback", body),
  listFeedback: (kpi = "net_revenue") =>
    get<{ count: number; by_verdict: Record<string, number>; rows: unknown[] }>(
      "feedback", { kpi }
    ),
  addAnnotation: (body: AnnotationIn) =>
    post<{ id: string; recorded: boolean }>("annotations", body),
  learning: (week: string, persona: string) => get<Learning>("learning", { week, persona }),
  testIntegration: (body: any) => post<any>("integrations/test", body),
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
