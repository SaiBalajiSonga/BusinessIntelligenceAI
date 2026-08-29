import Loader from "../components/Loader";
import { useEffect, useState } from "react";
import { api, fmt } from "../api";
import InlineFeedback from "../components/InlineFeedback";
import { ShieldCheck, ShieldAlert, AlertTriangle, Cpu, HelpCircle, Bot } from "lucide-react";
import type { Insight, Narrative } from "../types";

interface Props { week: string; persona: string; hideHeader?: boolean; }

const BAND_STYLE: Record<string, { badge: string; icon: string; label: string }> = {
  confident: { badge: "badge-confident", icon: "✅", label: "High Confidence" },
  qualified:  { badge: "badge-qualified",  icon: "⚠️", label: "Qualified Confidence" },
  abstain:    { badge: "badge-abstain",    icon: "🛑", label: "Engine Abstained" },
};

export default function NarrativeStudio({ week, persona, hideHeader }: Props) {
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [insight, setInsight] = useState<Insight | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([api.narrative(week, persona), api.insight(week, persona)])
      .then(([n, i]) => { setNarrative(n); setInsight(i); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [week, persona]);

  if (loading) return (
    <Loader text="Generating persona-specific narrative..." />
  );
  if (error) return <div className="error-banner">⚠️ {error}</div>;
  if (!narrative || !insight) return null;

  const band = narrative.band;
  const bs = BAND_STYLE[band] ?? BAND_STYLE.qualified;
  const totalTokens = narrative.calls.reduce((s, c) => s + c.input_tokens + c.output_tokens, 0);
  const totalCost = narrative.calls.reduce((s, c) => s + c.cost_usd, 0);
  const totalLatency = narrative.calls.reduce((s, c) => s + c.latency_ms, 0);

  return (
    <div>
      {!hideHeader && (
        <div className="page-header">
          <h1 className="page-title">Narrative Studio</h1>
          <p className="page-sub">
            Persona-specific synthesis · Numeric validator · Guard report · Analyst feedback loop
          </p>
        </div>
      )}

      <div className="grid grid-2-1" style={{ gap: 20 }}>
        {/* Left: Unified Narrative Card */}
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div className="card" style={{ padding: 0, marginBottom: 16 }}>
            {/* Header: Persona */}
            <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center", background: "var(--page)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div className="avatar" style={{ fontSize: 16, width: 36, height: 36, display: "flex", alignItems: "center", justifyContent: "center", borderRadius: "50%", background: "var(--brand-subtle)", border: "2px solid var(--brand)" }}>
                  {persona === "cfo" ? "??" : persona === "eu_category_manager" ? "???" : "??"}
                </div>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink)", lineHeight: 1.2, textTransform: "capitalize" }}>
                    {insight.entitlement.persona.replace(/_/g, " ")}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                    Regions: {insight.entitlement.regions.join(", ")}
                    {insight.entitlement.masked_columns.length > 0 && (
                      <> · 🔒 {insight.entitlement.masked_columns.length} field{insight.entitlement.masked_columns.length > 1 ? "s" : ""} masked</>
                    )}
                  </div>
                </div>
              </div>
              <span className={`badge ${bs.badge}`} style={{ fontSize: 12 }}>
                {bs.label}
              </span>
            </div>

            {/* Body: Narrative text */}
            <div style={{ padding: "24px 20px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16 }}>
                <div className="card-title" style={{ fontSize: 16 }}>Executive Narrative</div>
                {!narrative.llm_called && (
                  <span className="badge badge-neutral">No LLM call</span>
                )}
              </div>

              {band === "abstain" ? (
                <div style={{
                  padding: "24px",
                  background: "var(--abstain-bg)",
                  border: "1px solid rgba(239,68,68,.3)",
                  borderRadius: "var(--radius-sm)",
                  textAlign: "center",
                }}>
                  <AlertTriangle size={32} style={{ color: "var(--abstain)", marginBottom: 12 }} />
                  <div style={{ fontSize: 15, fontWeight: 600, color: "var(--abstain)", marginBottom: 8 }}>
                    Engine Abstained
                  </div>
                  <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.6 }}>
                    {insight.confidence.action}
                  </div>
                </div>
              ) : (
                <div className="prose" style={{ fontSize: 14 }}>
                  {narrative.text.split("\n\n").map((para, i) => (
                    <p key={i}>{para}</p>
                  ))}
                </div>
              )}

              {/* Guard badges */}
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--border-light)" }}>
                <span className="pill">
                  <span className="dot" style={{ background: narrative.guard.passed ? "var(--good)" : "var(--critical)" }} />
                  {narrative.guard.figures_checked} figures verified
                </span>
                {narrative.guard.drafts_rejected > 0 && (
                  <span className="pill" style={{ color: "var(--warning)" }}>
                    <ShieldAlert size={12} /> {narrative.guard.drafts_rejected} draft{narrative.guard.drafts_rejected > 1 ? "s" : ""} rejected
                  </span>
                )}
                <span className="pill">
                  <Bot size={12} /> {narrative.llm_called ? narrative.source : "Deterministic"}
                </span>
                {narrative.guard.violations.length > 0 && (
                  <span className="pill" style={{ color: "var(--critical)" }}>
                    {narrative.guard.violations.length} violation{narrative.guard.violations.length > 1 ? "s" : ""} caught
                  </span>
                )}
              </div>
            </div>

            {/* Footer: Analyst Feedback */}
            <div style={{ padding: "16px 20px", background: "var(--surface-2)", borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottomLeftRadius: "var(--radius)", borderBottomRightRadius: "var(--radius)" }}>
              <div style={{ fontSize: 12, color: "var(--muted)" }}>
                Did this narrative help you make a decision?
              </div>
              <InlineFeedback
                week={week}
                persona={persona}
                kpi={insight.kpi}
                confidence={insight.confidence.score}
                impact={insight.gap ?? undefined}
              />
            </div>
          </div>
        </div>

        {/* Right: Guard report + LLM stats */}
        <div className="grid" style={{ gap: 16, alignContent: "start" }}>
          {/* Guard report */}
          <div className="card">
            <div className="card-title" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}><ShieldCheck size={16} /> Data Verification Check</div>
            <dl className="kv-grid" style={{ marginBottom: narrative.guard.report !== "not applicable" ? 16 : 0 }}>
              <dt>Status</dt>
              <dd>
                <span className={`badge ${narrative.guard.passed ? "badge-confident" : "badge-abstain"}`}>
                  {narrative.guard.passed ? "Passed" : "Failed"}
                </span>
              </dd>
              <dt>Figures checked</dt>
              <dd>{narrative.guard.figures_checked}</dd>
              <dt>Drafts rejected</dt>
              <dd>{narrative.guard.drafts_rejected}</dd>
              <dt>Violations caught</dt>
              <dd>{narrative.guard.violations.length}</dd>
            </dl>
            {narrative.guard.violations.length > 0 && (
              <>
                <div className="section-label">Violations (hallucinated numbers)</div>
                <div className="evidence-block">
                  {narrative.guard.violations.join("\n")}
                </div>
              </>
            )}
            {narrative.guard.report !== "not applicable" && (
              <>
                <div className="section-label" style={{ marginTop: 14 }}>Full Report</div>
                <div className="evidence-block" style={{ fontSize: 11 }}>
                  {narrative.guard.report}
                </div>
              </>
            )}
          </div>

          {/* LLM calls */}
          {narrative.calls.length > 0 && (
            <div className="card">
              <div className="card-title" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}><Cpu size={16} /> System Diagnostics (LLM)</div>
              {narrative.calls.map((c, i) => (
                <div key={i} style={{
                  padding: "10px 12px",
                  background: "var(--surface-2)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border)",
                  marginBottom: 8,
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 500, color: "var(--ink)" }}>
                      Attempt {c.attempt + 1}
                    </span>
                    {c.cached && <span className="badge badge-neutral" style={{ fontSize: 10 }}>cached</span>}
                  </div>
                  <dl className="kv-grid" style={{ fontSize: 12 }}>
                    <dt>Model</dt><dd style={{ fontFamily: "monospace", fontSize: 11 }}>{c.model}</dd>
                    <dt>Latency</dt><dd>{fmt.ms(c.latency_ms)}</dd>
                    <dt>Tokens in</dt><dd>{c.input_tokens.toLocaleString()}</dd>
                    <dt>Tokens out</dt><dd>{c.output_tokens.toLocaleString()}</dd>
                    <dt>Cost (ref)</dt><dd>${c.cost_usd.toFixed(5)}</dd>
                  </dl>
                </div>
              ))}
              <div style={{
                marginTop: 8, padding: "10px 12px",
                background: "var(--brand-subtle)",
                borderRadius: "var(--radius-sm)",
                fontSize: 12,
              }}>
                <strong>Session totals:</strong>{" "}
                {totalTokens.toLocaleString()} tokens · ${totalCost.toFixed(5)} cost · {fmt.ms(totalLatency)} total
              </div>
            </div>
          )}

          {/* What would raise confidence */}
          {insight.would_raise_confidence.length > 0 && (
            <div className="card">
              <div className="card-title" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}><HelpCircle size={16} /> What Would Raise Confidence</div>
              <ul className="clean-list">
                {insight.would_raise_confidence.map((m) => <li key={m}>{m}</li>)}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
