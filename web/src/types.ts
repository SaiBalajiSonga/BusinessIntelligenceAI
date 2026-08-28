export type Band = "confident" | "qualified" | "abstain";
export type CauseStatus = "named lever" | "named constraint" | "localised" | "unattributed";

export interface Cause {
  factor: string;
  label: string;
  amount: number;
  rung: number;
  status: CauseStatus;
  credit: number;
  evidence: string;
  drivers: string[];
  owner: string | null;
  scope: Record<string, unknown> | null;
}

export interface Insight {
  kpi: string;
  week: string;
  currency: string;
  gap: number | null;
  actual: number | null;
  expected: number | null;
  confidence: {
    score: number;
    band: Band;
    coverage: number;
    components: Record<string, number>;
    action: string;
    llm_will_be_called: boolean;
  };
  causes: Cause[];
  contradictions: string[];
  would_raise_confidence: string[];
  no_counterfactual: string[];
  entitlement: {
    persona: string;
    regions: string[];
    masked_columns: string[];
    applied: string;
  };
}

export interface Narrative {
  week: string;
  persona: string;
  band: Band;
  text: string;
  source: string;
  llm_called: boolean;
  guard: {
    figures_checked: number;
    violations: string[];
    passed: boolean;
    drafts_rejected: number;
    report: string;
  };
  calls: {
    model: string;
    latency_ms: number;
    input_tokens: number;
    output_tokens: number;
    cost_usd: number;
    cached: boolean;
    attempt: number;
  }[];
}

export interface Recommendation {
  kind: "corrective" | "instrumentation";
  driver: string;
  lever: string;
  action: string;
  expected_impact: number | null;
  reversal_fraction: number | null;
  contribution: number;
  basis: string;
  owner: string;
  decision_rights: string;
  confidence: number;
  horizon_weeks: number;
  monitoring: { metrics: string[]; cadence: string; horizon_days: number; guardrail: string };
  assumptions: string[];
}

export interface Actions {
  gap: number;
  modelled_recovery: number;
  modelled_recovery_share: number | null;
  recommendations: Recommendation[];
}

export interface Freshness {
  source: string;
  governance: string;
  latest_data: string;
  lag_hours: number;
  sla_hours: number;
  status: "fresh" | "stale";
  freshness_score: number;
}

export interface Persona {
  id: string;
  label: string;
  regions: string[];
  masked_columns: string[];
  scope: Record<string, unknown> | null;
}

export interface Split {
  deterministic_ms: number;
  llm_ms: number;
  total_ms: number;
  llm_share: number;
  stages: { name: string; kind: "deterministic" | "llm"; ms: number; basis?: string }[];
  interpretation: string;
}

export interface Telemetry {
  llm: {
    calls: number; live_calls: number; cache_hits: number;
    input_tokens: number; output_tokens: number; cost_usd: number;
    p50_latency_ms: number; provider: string; model: string;
  };
  analysis_cache: { hits: number; misses: number; hit_rate: number; note: string };
}

export interface DrillStep { dimension: string; chosen: string | null }
export interface Attribution { path: DrillStep[] }
