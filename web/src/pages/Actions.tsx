import { useEffect, useState } from "react";
import { api, fmt } from "../api";
import FeedbackModal from "../components/FeedbackModal";
import type { Actions, Recommendation } from "../types";

interface Props { week: string; persona: string; }

const KIND_ICON: Record<string, string> = {
  corrective: "⚡",
  instrumentation: "🔭",
};

const OWNER_AVATARS: Record<string, string> = {
  category_manager: "CM",
  marketing_lead: "ML",
  supply_planner: "SP",
  pricing_council: "PC",
};

function LeverSimulator({ rec, onImpactChange }: {
  rec: Recommendation;
  onImpactChange: (v: number) => void;
}) {
  const [pct, setPct] = useState(100);
  const maxImpact = Math.abs(rec.contribution);
  const simImpact = maxImpact * (pct / 100);

  useEffect(() => onImpactChange(simImpact), [simImpact, onImpactChange]);

  if (!rec.expected_impact) return null;

  return (
    <div className="lever-simulator">
      <div className="lever-label">
        <span className="lever-name">
          What-If: Reversal of {rec.lever}
        </span>
        <span className="lever-val">
          {fmt.money(simImpact, "")} recovered
        </span>
      </div>
      <div style={{ marginBottom: 4, display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--muted)" }}>
        <span>0% reversal</span>
        <span>{pct}% reversal selected</span>
        <span>100% reversal</span>
      </div>
      <input
        type="range"
        min={0} max={100} value={pct}
        onChange={(e) => setPct(Number(e.target.value))}
        style={{ width: "100%" }}
      />
      <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
        {[25, 50, 75, 100].map((v) => (
          <button
            key={v}
            className={`btn btn-xs ${pct === v ? "btn-primary" : ""}`}
            onClick={() => setPct(v)}
          >
            {v}%
          </button>
        ))}
      </div>
      <div style={{ marginTop: 10, fontSize: 11.5, color: "var(--muted)" }}>
        Assumes linear response · Full reversal = {fmt.money(rec.expected_impact, "")} · {rec.basis}
      </div>
    </div>
  );
}

function RecCard({ rec, week, persona }: { rec: Recommendation; week: string; persona: string }) {
  const [simImpact, setSimImpact] = useState(Math.abs(rec.contribution));
  const [expanded, setExpanded] = useState(false);
  const [fbOpen, setFbOpen] = useState(false);

  return (
    <div className="action-card">
      <div className="action-card-header">
        <div
          className={`action-card-icon ${rec.kind}`}
          title={rec.kind === "corrective" ? "Corrective action" : "Instrumentation"}
        >
          {KIND_ICON[rec.kind] ?? "⚡"}
        </div>
        <div style={{ flex: 1 }}>
          <div className="action-card-title">{rec.lever}</div>
          <div className="action-card-driver">
            Driver: <code style={{ fontSize: 11 }}>{rec.driver.replace(/_/g, " ")}</code>
            {" "}· Confidence: {(rec.confidence * 100).toFixed(0)}%
          </div>
        </div>
        {rec.expected_impact && (
          <div className="action-card-impact">
            <div className="impact-value">{fmt.money(simImpact, "")}</div>
            <div className="impact-label">modelled recovery</div>
          </div>
        )}
      </div>

      <div className="action-card-body">
        {/* Owner + Meta */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14, flexWrap: "wrap" }}>
          <div style={{
            width: 30, height: 30,
            borderRadius: "50%",
            background: "var(--brand-subtle)",
            border: "1px solid var(--brand)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 10, fontWeight: 700, color: "var(--brand)",
          }}>
            {OWNER_AVATARS[rec.owner] ?? rec.owner.slice(0,2).toUpperCase()}
          </div>
          <span style={{ fontSize: 12.5, color: "var(--ink-2)", fontWeight: 500 }}>
            {rec.owner.replace(/_/g, " ")}
          </span>
          <span className="tag">{rec.horizon_weeks}w horizon</span>
          <span className="tag">{rec.kind}</span>
          <span className="tag" style={{ color: "var(--muted)" }}>
            {rec.monitoring.cadence} monitoring
          </span>
        </div>

        {/* Action Text */}
        <div className="action-text">{rec.action}</div>

        {/* What-If Lever */}
        {rec.kind === "corrective" && rec.expected_impact && (
          <LeverSimulator rec={rec} onImpactChange={setSimImpact} />
        )}

        {/* Expand / Collapse Details */}
        <button
          className="btn btn-ghost btn-sm"
          onClick={() => setExpanded((v) => !v)}
          style={{ marginTop: 8 }}
        >
          {expanded ? "▲ Hide details" : "▼ Show monitoring & constraints"}
        </button>

        {expanded && (
          <div style={{ marginTop: 12 }}>
            <hr className="divider" />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
              <div>
                <div className="section-label">Decision Rights</div>
                <p style={{ fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.5 }}>
                  {rec.decision_rights}
                </p>
              </div>
              <div>
                <div className="section-label">Monitoring Plan</div>
                <p style={{ fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.5 }}>
                  Track {rec.monitoring.metrics.join(", ")} {rec.monitoring.cadence} for {rec.monitoring.horizon_days}d.
                </p>
              </div>
            </div>
            {rec.monitoring.guardrail && (
              <div style={{
                marginTop: 12, padding: "10px 14px",
                background: "var(--warning-bg)", border: "1px solid rgba(245,158,11,.3)",
                borderRadius: "var(--radius-sm)", fontSize: 12.5, color: "var(--ink-2)",
              }}>
                🛡️ <strong>Guardrail:</strong> {rec.monitoring.guardrail}
              </div>
            )}
            {rec.assumptions.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div className="section-label">Assumptions</div>
                <ul className="clean-list">
                  {rec.assumptions.map((a) => <li key={a}>Assumes {a}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Feedback */}
        <div className="feedback-btns" style={{ marginTop: 12 }}>
          <button className="btn btn-xs btn-confirm" onClick={() => setFbOpen(true)}>✓ Confirm</button>
          <button className="btn btn-xs btn-danger" onClick={() => setFbOpen(true)}>✗ Wrong Lever</button>
        </div>
      </div>

      <FeedbackModal
        open={fbOpen}
        onClose={() => setFbOpen(false)}
        week={week}
        persona={persona}
        driver={rec.driver}
        confidence={rec.confidence}
        impact={rec.contribution}
      />
    </div>
  );
}

interface Props {
  week: string;
  persona: string;
  hideHeader?: boolean;
}

export default function ActionPlaybook({ week, persona, hideHeader }: Props) {
  const [actions, setActions] = useState<Actions | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api.actions(week, persona)
      .then(setActions)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [week, persona]);

  if (loading) return (
    <div className="loading-screen"><div className="spinner" /><div className="loading-text">Loading recommendations…</div></div>
  );

  if (error) return <div className="error-banner">⚠️ {error}</div>;

  const recs = actions?.recommendations ?? [];
  const corrective = recs.filter((r) => r.kind === "corrective");
  const instrumentation = recs.filter((r) => r.kind === "instrumentation");

  return (
    <div>
      {!hideHeader && (
        <div className="page-header">
          <h1 className="page-title">Action Playbook</h1>
          <p className="page-sub">
            Recommended mitigations · Expected impact bounds · Guardrails · Decision rights
          </p>
        </div>
      )}

      {/* Recovery Summary */}
      <div className="grid" style={{ gridTemplateColumns: "repeat(3, 1fr)", gap: 14, marginBottom: 24 }}>
        <div className="kpi-tile">
          <div className="kpi-tile-label">Total Gap</div>
          <div className="kpi-tile-value" style={{ fontSize: 22, color: "var(--neg)" }}>
            {fmt.money(actions?.gap ?? 0, "GBP")}
          </div>
        </div>
        <div className="kpi-tile">
          <div className="kpi-tile-label">Addressable (Modelled)</div>
          <div className="kpi-tile-value" style={{ fontSize: 22, color: "var(--pos)" }}>
            {fmt.money(actions?.modelled_recovery ?? 0, "GBP")}
          </div>
          <div className="kpi-tile-foot">
            {actions?.modelled_recovery_share ? `${fmt.pct(actions.modelled_recovery_share)} of gap` : ""}
          </div>
        </div>
        <div className="kpi-tile">
          <div className="kpi-tile-label">Actions Available</div>
          <div className="kpi-tile-value" style={{ fontSize: 22 }}>{corrective.length}</div>
          <div className="kpi-tile-foot">+ {instrumentation.length} instrumentation</div>
        </div>
      </div>

      {/* How impact is computed */}
      <div style={{
        padding: "12px 16px",
        background: "var(--confident-bg)",
        border: "1px solid rgba(16,185,129,.3)",
        borderRadius: "var(--radius)",
        marginBottom: 20,
        fontSize: 12.5,
        color: "var(--ink-2)",
        display: "flex",
        gap: 10,
      }}>
        ✅ Expected impact is <strong style={{ color: "var(--ink)" }}>computed from attributed contribution, never written by the model.</strong>
        {" "}Each slider recalculates: <code>recovery = |contribution| × reversal_fraction</code>.
      </div>

      {corrective.length > 0 && (
        <>
          <div className="section-label" style={{ marginBottom: 12 }}>Corrective Actions</div>
          <div className="grid" style={{ gap: 14, marginBottom: 24 }}>
            {corrective.map((r) => (
              <RecCard key={r.driver} rec={r} week={week} persona={persona} />
            ))}
          </div>
        </>
      )}

      {instrumentation.length > 0 && (
        <>
          <div className="section-label" style={{ marginBottom: 12 }}>Instrumentation Recommendations</div>
          <div className="grid" style={{ gap: 14 }}>
            {instrumentation.map((r) => (
              <RecCard key={r.driver} rec={r} week={week} persona={persona} />
            ))}
          </div>
        </>
      )}

      {recs.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">🎯</div>
          <div className="empty-state-title">No recommendations</div>
          <div className="empty-state-sub">Engine abstained or gap is below action threshold (£25k)</div>
        </div>
      )}
    </div>
  );
}
