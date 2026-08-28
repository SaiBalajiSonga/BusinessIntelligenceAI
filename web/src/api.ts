import type {
  Actions, Attribution, Freshness, Insight, Narrative, Persona, Split, Telemetry,
} from "./types";

async function get<T>(path: string, params: Record<string, string> = {}): Promise<T> {
  const qs = new URLSearchParams(params).toString();
  const res = await fetch(`/v1/${path}${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${path} failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  personas: () => get<Persona[]>("personas"),
  freshness: () => get<Freshness[]>("freshness"),
  insight: (week: string, persona: string) => get<Insight>("insight", { week, persona }),
  narrative: (week: string, persona: string) => get<Narrative>("narrative", { week, persona }),
  actions: (week: string, persona: string) => get<Actions>("actions", { week, persona }),
  attribution: (week: string, persona: string) => get<Attribution>("attribution", { week, persona }),
  telemetry: () => get<Telemetry>("telemetry"),
  split: () => get<Split>("processing-split"),
};

export const fmt = {
  money(v: number | null, currency = "GBP"): string {
    if (v === null || v === undefined) return "—";
    const sign = v < 0 ? "−" : "+";
    return `${sign}${Math.abs(v).toLocaleString("en-GB", { maximumFractionDigits: 0 })} ${currency}`;
  },
  abs(v: number): string {
    return Math.abs(v).toLocaleString("en-GB", { maximumFractionDigits: 0 });
  },
  pct(v: number | null, digits = 0): string {
    return v === null || v === undefined ? "—" : `${(v * 100).toFixed(digits)}%`;
  },
  ms(v: number): string {
    return v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${Math.round(v)}ms`;
  },
};
