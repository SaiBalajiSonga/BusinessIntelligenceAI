import Loader from "../components/Loader";
import { useEffect, useState } from "react";
import { api, fmt } from "../api";
import { Bridge, ConfidenceBars, SplitBar } from "../charts";
import InlineFeedback from "../components/InlineFeedback";
import type { Actions, Attribution, Cause, Insight, Split } from "../types";

interface Props {
  week: string;
  persona: string;
  onWeekChange?: (w: string) => void;
  onPersonaChange?: (p: string) => void;
  hideHeader?: boolean;
}

const WEIGHTS: Record<string, number> = {
  coverage: 0.45, freshness: 0.15, history_depth: 0.15,
  method_strength: 0.15, contradiction: -0.2,
};

const BAND_STYLE: Record<string, string> = {
  confident: "badge-confident",
  qualified: "badge-qualified",
  abstain:   "badge-abstain",
};

const SCENARIOS = [
  {
    id: "multifactor",
    icon: "📉",
    title: "Multi-Factor Drop",
    sub: "Price · Mix · Stockout · Competitor",
    badge: "Required",
    badgeColor: "var(--neg)",
    week: "2026-W32",
    persona: "cfo",
    desc: "Net Revenue dropped £612k vs expectation. LMDI decomposes it into four interacting drivers — none alone explains the gap.",
  },
  {
    id: "sparse",
    icon: "🌱",
    title: "Sparse History",
    sub: "New SKU < 12 weeks data",
    badge: "Required",
    badgeColor: "var(--qualified)",
    week: "2026-W32",
    persona: "eu_category_manager",
    desc: "HOME-NEW-01 has insufficient history for STL baseline. Engine falls back to peer benchmark and flags low confidence.",
  },
  {
    id: "abstain",
    icon: "🛑",
    title: "Low Confidence / Abstain",
    sub: "Contradictory signals detected",
    badge: "Required",
    badgeColor: "var(--abstain)",
    week: "2026-W32",
    persona: "analyst",
    desc: "When contradiction score or coverage is below threshold, the engine refuses to narrate and instead lists what would raise confidence.",
  },
  {
    id: "entitlement",
    icon: "🔒",
    title: "Role-Based Entitlement",
    sub: "Row filter applied before analysis",
    badge: "Required",
    badgeColor: "var(--brand)",
    week: "2026-W32",
    persona: "eu_category_manager",
    desc: "EU Category Manager sees only DE, FR, NL. Gross margin % is masked. Entitlement is enforced in SQL before any computation.",
  },
];

const RUNG_METHODS: Record<number, string> = {
  1: "Rung 1 — LMDI over the revenue identity. Exact; contributions sum to the gap with zero residual.",
  2: "Rung 2 — Bennet indicator splitting ASP into price and mix. Exact.",
  3: "Rung 3 — Dimensional attribution ranked by Jensen-Shannon surprise. Exact.",
  4: "Rung 4 — Difference-in-differences with two-way fixed effects. Carries assumptions.",
};

export default function RootCause({ week, persona, onWeekChange, onPersonaChange, hideHeader }: Props) {
  const [activeScenario, setActiveScenario] = useState("multifactor");
  const [insight, setInsight] = useState<Insight | null>(null);
  const [actions, setActions] = useState<Actions | null>(null);
  const [attribution, setAttribution] = useState<Attribution | null>(null);
  const [split, setSplit] = useState<Split | null>(null);
  const [selected, setSelected] = useState<Cause | null>(null);
    const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const scenario = SCENARIOS.find((s) => s.id === activeScenario) ?? SCENARIOS[0];
  const activeWeek = scenario.week;
  const activePersona = scenario.persona;

  useEffect(() => {
    let live = true;
    setLoading(true);
    setError(null);
    setSelected(null);
    Promise.all([
      api.insight(activeWeek, activePersona),
      api.actions(activeWeek, activePersona),
      api.attribution(activeWeek, activePersona),
      api.split().catch(() => null),
    ])
      .then(([i, a, at, sp]) => {
        if (!live) return;
        setInsight(i); setActions(a); setAttribution(at); setSplit(sp);
      })
      .catch((e) => live && setError(e.message))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [activeScenario, activeWeek, activePersona]);

  const cur = insight?.currency ?? "GBP";
  const band = insight?.confidence.band ?? "qualified";

  return (
    <div>
      {!hideHeader && (
        <>
          <div className="page-header">
            <h1 className="page-title">Root Cause Workspace</h1>
            <p className="page-sub">
              Deterministic decomposition · Jensen-Shannon surprise ranking · Causal inference
            </p>
          </div>

          <div className="scenario-grid">
            {SCENARIOS.map((s) => (
              <button
                key={s.id}
                className={`scenario-card${activeScenario === s.id ? " active" : ""}`}
                onClick={() => setActiveScenario(s.id)}
              >
                <span className="scenario-card-icon">{s.icon}</span>
                <div className="scenario-card-title">{s.title}</div>
                <div className="scenario-card-sub">{s.sub}</div>
                <span
                  className="scenario-badge"
                  style={{ background: `${s.badgeColor}20`, color: s.badgeColor, border: `1px solid ${s.badgeColor}40` }}
                >
                  {s.badge}
                </span>
              </button>
            ))}
          </div>

          <div style={{
            padding: "12px 16px",
            background: "var(--brand-subtle)",
            border: "1px solid var(--brand)",
            borderRadius: "var(--radius)",
            marginBottom: 20,
            fontSize: 13,
            color: "var(--ink-2)",
            display: "flex",
            gap: 10,
            alignItems: "flex-start",
          }}>
            <span style={{ fontSize: 16, flexShrink: 0 }}>ℹ️</span>
            <span>
              <strong style={{ color: "var(--ink)" }}>{scenario.title}:</strong> {scenario.desc}
              {" "}<span style={{ color: "var(--muted)" }}>
                Persona: <code>{activePersona}</code> · Week: <code>{activeWeek}</code>
              </span>
            </span>
          </div>
        </>
      )}

      {loading && (
        <Loader text="Running analysis cascade (Rungs 0-5)..." />
      )}

      {error && <div className="error-banner">⚠️ {error}</div>}

      {insight && !loading && (
        <>
          {/* Summary Tiles */}
          <div className="tiles-grid" style={{ marginBottom: 20 }}>
            <div className="kpi-tile">
              <div className="kpi-tile-label">Gap vs Expectation</div>
              <div className="kpi-tile-value" style={{ fontSize: 24, color: (insight.gap ?? 0) < 0 ? "var(--neg)" : "var(--pos)" }}>
                {fmt.money(insight.gap, cur)}
              </div>
              <div className="kpi-tile-foot">expected {fmt.moneyRaw(insight.expected ?? 0)}</div>
            </div>
            <div className="kpi-tile">
              <div className="kpi-tile-label">Confidence Score</div>
              <div className="kpi-tile-value" style={{ fontSize: 24 }}>
                {insight.confidence.score.toFixed(3)}
              </div>
              <span className={`badge ${BAND_STYLE[band]}`} style={{ marginTop: 4 }}>
                {band}
              </span>
            </div>
            <div className="kpi-tile">
              <div className="kpi-tile-label">Coverage</div>
              <div className="kpi-tile-value" style={{ fontSize: 24 }}>
                {fmt.pct(insight.confidence.coverage, 1)}
              </div>
              <div className="kpi-tile-foot">share tied to a named cause</div>
            </div>
            <div className="kpi-tile">
              <div className="kpi-tile-label">Modelled Recovery</div>
              <div className="kpi-tile-value" style={{ fontSize: 24, color: "var(--pos)" }}>
                {actions ? fmt.money(actions.modelled_recovery, cur) : "—"}
              </div>
              <div className="kpi-tile-foot">
                {actions?.modelled_recovery_share ? `${fmt.pct(actions.modelled_recovery_share)} of gap` : ""}
              </div>
            </div>
          </div>

          {/* Entitlement Banner */}
          {insight.entitlement.masked_columns.length > 0 && (
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 14px",
              background: "rgba(99,102,241,.08)",
              border: "1px solid rgba(99,102,241,.25)",
              borderRadius: "var(--radius-sm)",
              marginBottom: 16,
              fontSize: 12, color: "var(--ink-2)",
            }}>
              🔒 <strong style={{ color: "var(--brand)" }}>{insight.entitlement.persona}</strong>
              {" "}— regions: {insight.entitlement.regions.join(", ")} ·
              {" "}{insight.entitlement.masked_columns.length} field{insight.entitlement.masked_columns.length > 1 ? "s" : ""} masked
              ({insight.entitlement.masked_columns.join(", ")}) ·
              {" "}<span style={{ color: "var(--muted)" }}>{insight.entitlement.applied}</span>
            </div>
          )}

          <div className="grid grid-5-3">
            {/* Left column */}
            <div className="grid" style={{ gap: 16, alignContent: "start" }}>
              {/* Bridge Chart */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">Revenue Waterfall (LMDI Decomposition)</div>
                    <div className="card-sub">Expected → Actual. Zero residual by construction. Click any bar for evidence.</div>
                  </div>
                </div>
                {insight.expected !== null && insight.actual !== null && (
                  <Bridge
                    expected={insight.expected}
                    actual={insight.actual}
                    causes={insight.causes}
                    currency={cur}
                    onSelect={setSelected}
                  />
                )}
              </div>

              {/* Causes */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">Ranked Causes</div>
                    <div className="card-sub">
                      Sorted by contribution. Attribution ranked by Jensen-Shannon surprise, not size.
                    </div>
                  </div>
                </div>
                <div className="cause-list">
                  {insight.causes.map((c) => (
                    <button
                      key={c.factor}
                      className="cause-row"
                      onClick={() => setSelected(c)}
                    >
                      <span
                        className="cause-indicator"
                        style={{
                          background: c.amount < 0 ? "var(--neg)" : "var(--pos)",
                          opacity: c.status === "unattributed" ? 0.3 : 1,
                        }}
                      />
                      <span className="cause-info">
                        <span className="cause-name">{c.label}</span>
                        <span className="cause-meta">
                          Rung {c.rung} · {c.status}
                          {c.owner ? ` · ${c.owner.replace(/_/g, " ")}` : ""}
                        </span>
                      </span>
                      <span className="cause-amount" style={{ color: c.amount < 0 ? "var(--neg)" : "var(--pos)" }}>
                        {fmt.money(c.amount, "")}
                      </span>
                    </button>
                  ))}
                </div>

                {attribution && attribution.path.length > 0 && (
                  <div style={{
                    marginTop: 14, padding: "10px 12px",
                    background: "var(--surface-2)", borderRadius: "var(--radius-sm)",
                    fontSize: 12, color: "var(--ink-2)",
                  }}>
                    📍 Drill path: <strong>{attribution.path.map((s) => `${s.dimension}=${s.chosen}`).join(" → ")}</strong>
                    <span style={{ color: "var(--muted)" }}> · ranked by surprise, not size</span>
                  </div>
                )}
              </div>

              {/* Contradictions */}
              {insight.contradictions.length > 0 && (
                <div className="card" style={{ border: "1px solid rgba(245,158,11,.3)", background: "var(--warning-bg)" }}>
                  <div className="card-title" style={{ color: "var(--warning)", marginBottom: 10 }}>
                    ⚠️ Contradictory Evidence Detected
                  </div>
                  <ul className="clean-list">
                    {insight.contradictions.map((c) => (
                      <li key={c} style={{ color: "var(--ink-2)" }}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Abstain message */}
              {band === "abstain" && (
                <div className="card" style={{ border: "1px solid rgba(239,68,68,.3)", background: "var(--abstain-bg)" }}>
                  <div className="card-title" style={{ color: "var(--abstain)", marginBottom: 10 }}>
                    🛑 Engine Abstaining — Insufficient Evidence
                  </div>
                  <p style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.6 }}>
                    {insight.confidence.action}
                  </p>
                  {insight.would_raise_confidence.length > 0 && (
                    <>
                      <div className="section-label" style={{ marginTop: 14 }}>What would raise confidence</div>
                      <ul className="clean-list">
                        {insight.would_raise_confidence.map((m) => <li key={m}>{m}</li>)}
                      </ul>
                    </>
                  )}
                </div>
              )}
            </div>

            {/* Right column */}
            <div className="grid" style={{ gap: 16, alignContent: "start" }}>
              {/* Confidence */}
              <div className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">Confidence Engine</div>
                    <div className="card-sub">
                      Weighted components. Coverage counts only what's tied to a named cause.
                    </div>
                  </div>
                  <span className={`badge ${BAND_STYLE[band]}`}>{band}</span>
                </div>
                <ConfidenceBars components={insight.confidence.components} weights={WEIGHTS} />
                {insight.would_raise_confidence.length > 0 && (
                  <>
                    <hr className="divider" />
                    <div className="section-label">What would raise it</div>
                    <ul className="clean-list">
                      {insight.would_raise_confidence.map((m) => <li key={m}>{m}</li>)}
                    </ul>
                  </>
                )}
              </div>

              {/* LLM Split */}
              {split && (
                <div className="card">
                  <div className="card-header">
                    <div>
                      <div className="card-title">LLM vs Deterministic</div>
                      <div className="card-sub">Measured cold at warm-up, not on cached data.</div>
                    </div>
                  </div>
                  <SplitBar split={split} />
                  <p className="note" style={{ marginTop: 10 }}>{split.interpretation}</p>
                </div>
              )}

              {/* No counterfactual */}
              {insight.no_counterfactual.length > 0 && (
                <div className="card">
                  <div className="card-title" style={{ marginBottom: 10 }}>
                    🔭 Uninstrumented Drivers
                  </div>
                  <ul className="clean-list">
                    {insight.no_counterfactual.map((s) => <li key={s}>{s}</li>)}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {/* Evidence Drawer */}
      <div className="scrim" data-open={!!selected} onClick={() => setSelected(null)} />
      <aside className="drawer" data-open={!!selected} aria-label="Evidence detail">
        {selected && (
          <>
            <div className="drawer-header">
              <div style={{ flex: 1 }}>
                <div className="drawer-title">{selected.label}</div>
                <div className="drawer-sub">
                  {fmt.money(selected.amount, cur)} · Rung {selected.rung} · {selected.status}
                </div>
              </div>
              <button className="close-btn" onClick={() => setSelected(null)} aria-label="Close">×</button>
            </div>
            <div className="drawer-body">
              <dl className="kv-grid" style={{ marginBottom: 20 }}>
                <dt>Status</dt><dd>{selected.status}</dd>
                <dt>Coverage credit</dt><dd>{selected.credit.toFixed(3)}</dd>
                <dt>Owner</dt><dd>{selected.owner?.replace(/_/g, " ") ?? "unassigned"}</dd>
                <dt>Instrumented drivers</dt>
                <dd>{selected.drivers.length ? selected.drivers.join(", ") : "none instrumented"}</dd>
                <dt>Scope</dt>
                <dd>
                  {selected.scope
                    ? Object.entries(selected.scope).map(([k, v]) =>
                        `${k}=${Array.isArray(v) ? v.join("/") : v}`
                      ).join(", ")
                    : "portfolio"}
                </dd>
              </dl>

              <div className="section-label">Evidence Object</div>
              <div className="evidence-block" style={{ marginBottom: 20 }}>{selected.evidence}</div>

              <div className="section-label">How This Was Computed</div>
              <ul className="clean-list" style={{ marginBottom: 20 }}>
                <li>{RUNG_METHODS[selected.rung] ?? "—"}</li>
                {selected.status === "localised" && (
                  <li>Located by a control-group estimate; no instrumented driver names the cause.</li>
                )}
                {selected.status === "unattributed" && (
                  <li>No driver identified — this term counts zero toward coverage.</li>
                )}
              </ul>

              <div className="section-label">Analyst Feedback</div>
              <InlineFeedback
                week={activeWeek}
                persona={activePersona}
                driver={selected.factor}
                confidence={insight?.confidence.score}
                impact={selected.amount}
              />
            </div>
          </>
        )}
      </aside>

      
    </div>
  );
}
