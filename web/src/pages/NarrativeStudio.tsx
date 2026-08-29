import Loader from "../components/Loader";
import { useEffect, useState } from "react";
import { api } from "../api";
import InlineFeedback from "../components/InlineFeedback";
import { ShieldAlert, AlertTriangle, HelpCircle, Bot } from "lucide-react";
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

      <div style={{ maxWidth: 960 }}>
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

              
              {insight.would_raise_confidence.length > 0 && (
                <div style={{ marginTop: 24, padding: "16px", background: "rgba(245, 158, 11, 0.05)", border: "1px solid rgba(245, 158, 11, 0.2)", borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--warning)", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                    <HelpCircle size={14} /> What would raise engine confidence?
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "var(--ink-2)", lineHeight: 1.5 }}>
                    {insight.would_raise_confidence.map((m) => <li key={m}>{m}</li>)}
                  </ul>
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

        
      </div>
    </div>
  );
}
