import { useEffect, useState } from "react";
import { api, fmt } from "../api";
import { toast } from "../components/Toast";
import type { FeedbackRecord, Learning } from "../types";

interface Props { week: string; persona: string; }

const VERDICT_STYLE: Record<string, { badge: string; icon: string }> = {
  correct:       { badge: "badge-confident", icon: "?" },
  wrong_driver:  { badge: "badge-neg",       icon: "?" },
  missed_factor: { badge: "badge-warning",   icon: "??" },
  hallucination: { badge: "badge-critical",  icon: "??" },
  bad_tone:      { badge: "badge-neutral",   icon: "??" },
  known_cause:   { badge: "badge-neutral",   icon: "??" },
  not_material:  { badge: "badge-qualified", icon: "~" },
  unclear:       { badge: "badge-neutral",   icon: "?" },
};

export default function FeedbackHub({ week, persona }: Props) {
  const [feedbackData, setFeedbackData] = useState<{
    count: number;
    by_verdict: Record<string, number>;
    rows: FeedbackRecord[];
  } | null>(null);
  const [learning, setLearning] = useState<Learning | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Annotation form
  const [annLabel, setAnnLabel] = useState("");
  const [annStart, setAnnStart] = useState("");
  const [annEnd, setAnnEnd] = useState("");
  const [annDimension, setAnnDimension] = useState("");
  const [annValue, setAnnValue] = useState("");
  const [annAuthor, setAnnAuthor] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    setLoading(true);
    Promise.all([
      api.listFeedback(),
      api.learning(week, persona),
    ])
      .then(([f, l]) => {
        setFeedbackData(f as typeof feedbackData);
        setLearning(l);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, [week, persona]);

  const submitAnnotation = async () => {
    if (!annLabel || !annStart) { toast("Label and start date are required", "error"); return; }
    setSubmitting(true);
    try {
      await api.addAnnotation({
        label: annLabel,
        starts_on: annStart,
        ends_on: annEnd || null,
        dimension: annDimension || null,
        value: annValue || null,
        author: annAuthor || null,
      });
      toast("Annotation added — engine will consider this in future runs", "success", "📌");
      setAnnLabel(""); setAnnStart(""); setAnnEnd(""); setAnnDimension(""); setAnnValue(""); setAnnAuthor("");
      load();
    } catch (e: unknown) {
      toast(`Failed: ${(e as Error).message}`, "error");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return (
    <div className="loading-screen"><div className="spinner" /><div className="loading-text">Loading feedback & learning state…</div></div>
  );
  if (error) return <div className="error-banner">⚠️ {error}</div>;

  const rows = (feedbackData?.rows ?? []) as FeedbackRecord[];
  const byVerdict = feedbackData?.by_verdict ?? {};
  const total = feedbackData?.count ?? 0;

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Feedback & Learning</h1>
        <p className="page-sub">
          Analyst verdicts · Isotonic calibration · Driver prior updates · Business annotations
        </p>
      </div>

      <div className="grid grid-2" style={{ gap: 20, marginBottom: 24 }}>
        {/* Learning Summary */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>🧠 Learning Loop State</div>
          {learning ? (
            <>
              <dl className="kv-grid" style={{ marginBottom: 14 }}>
                <dt>Backend</dt>
                <dd>
                  <span className="badge badge-neutral">{learning.backend}</span>
                </dd>
                <dt>Feedback records</dt>
                <dd>{learning.feedback_count ?? total}</dd>
                <dt>Calibration adjustment</dt>
                <dd style={{ fontFamily: "monospace", color: "var(--brand)" }}>
                  {learning.confidence_adjustment?.shifted_by > 0 ? "+" : ""}
                  {learning.confidence_adjustment?.shifted_by?.toFixed(3) ?? "0.000"}
                </dd>
              </dl>
              <div style={{
                padding: "12px 14px",
                background: "var(--brand-subtle)",
                borderRadius: "var(--radius-sm)",
                fontSize: 12.5,
                color: "var(--ink-2)",
                lineHeight: 1.6,
              }}>
                <strong style={{ color: "var(--ink)" }}>How it works:</strong> Each "wrong_driver" verdict
                decreases that driver's prior probability. Verdicts are accumulated and an isotonic regression
                maps raw confidence scores to calibrated probabilities. The updated priors are stored in
                <code> learned_params</code> and applied on the next run.
              </div>
            </>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">🧠</div>
              <div className="empty-state-sub">No learning state yet — submit feedback to begin calibration</div>
            </div>
          )}
        </div>

        {/* Verdict Summary */}
        <div className="card">
          <div className="card-title" style={{ marginBottom: 14 }}>📊 Feedback Summary</div>
          {total === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📬</div>
              <div className="empty-state-title">No feedback yet</div>
              <div className="empty-state-sub">
                Use the ✓/✗ buttons on insights and narratives to submit your first verdict.
              </div>
            </div>
          ) : (
            <>
              <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.02em", marginBottom: 12 }}>
                {total} <span style={{ fontSize: 14, fontWeight: 400, color: "var(--muted)" }}>records</span>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {Object.entries(byVerdict).map(([verdict, count]) => {
                  const style = VERDICT_STYLE[verdict] ?? { badge: "badge-neutral", icon: "?" };
                  const pct = total > 0 ? (count / total) * 100 : 0;
                  return (
                    <div key={verdict} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span className={`badge ${style.badge}`} style={{ width: 130, justifyContent: "center" }}>
                        {style.icon} {verdict.replace(/_/g, " ")}
                      </span>
                      <div style={{ flex: 1, height: 8, background: "var(--surface-3)", borderRadius: 4, overflow: "hidden" }}>
                        <div style={{
                          width: `${pct}%`, height: "100%",
                          background: verdict === "correct" ? "var(--confident)" :
                            verdict === "wrong_driver" ? "var(--abstain)" : "var(--qualified)",
                          borderRadius: 4,
                          transition: "width 0.4s ease",
                        }} />
                      </div>
                      <span style={{ fontSize: 12, color: "var(--muted)", minWidth: 24, textAlign: "right" }}>
                        {count}
                      </span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Annotation Form */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-title" style={{ marginBottom: 4 }}>📌 Add Business Annotation</div>
        <div className="card-sub" style={{ marginBottom: 16 }}>
          Known events the engine should be aware of — planned campaigns, system migrations, holidays.
          A known event is not an anomaly. The engine checks annotations before flagging.
        </div>
        <div className="grid grid-2" style={{ gap: 12 }}>
          <div className="form-field">
            <label className="form-label">Event Label *</label>
            <input
              className="form-input"
              placeholder="e.g. Black Friday campaign 2026"
              value={annLabel}
              onChange={(e) => setAnnLabel(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label className="form-label">Dimension (optional)</label>
            <select className="form-select" value={annDimension} onChange={(e) => setAnnDimension(e.target.value)}>
              <option value="">— Portfolio-wide —</option>
              <option value="region">region</option>
              <option value="channel">channel</option>
              <option value="category">category</option>
              <option value="sku">sku</option>
            </select>
          </div>
          <div className="form-field">
            <label className="form-label">Starts on *</label>
            <input
              type="date"
              className="form-input"
              value={annStart}
              onChange={(e) => setAnnStart(e.target.value)}
            />
          </div>
          <div className="form-field">
            <label className="form-label">Ends on (optional)</label>
            <input
              type="date"
              className="form-input"
              value={annEnd}
              onChange={(e) => setAnnEnd(e.target.value)}
            />
          </div>
          {annDimension && (
            <div className="form-field">
              <label className="form-label">{annDimension} value</label>
              <input
                className="form-input"
                placeholder={`e.g. ${annDimension === "region" ? "DE" : annDimension === "channel" ? "web" : "value"}`}
                value={annValue}
                onChange={(e) => setAnnValue(e.target.value)}
              />
            </div>
          )}
          <div className="form-field">
            <label className="form-label">Author (optional)</label>
            <input
              className="form-input"
              placeholder="e.g. alice.smith"
              value={annAuthor}
              onChange={(e) => setAnnAuthor(e.target.value)}
            />
          </div>
        </div>
        <button
          className="btn btn-primary"
          onClick={submitAnnotation}
          disabled={submitting || !annLabel || !annStart}
        >
          {submitting ? "Saving…" : "📌 Add Annotation"}
        </button>
      </div>

      {/* Feedback Log */}
      <div className="card">
        <div className="card-header">
          <div>
            <div className="card-title">Feedback Log</div>
            <div className="card-sub">
              Last {rows.length} of {total} records · net_revenue KPI
            </div>
          </div>
          <button className="btn btn-sm" onClick={load}>↻ Refresh</button>
        </div>
        {rows.length === 0 ? (
          <div className="empty-state">
            <div className="empty-state-icon">📭</div>
            <div className="empty-state-title">No feedback recorded yet</div>
            <div className="empty-state-sub">
              Submit verdicts from the Root Cause or Narrative pages to see them here.
            </div>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>When</th>
                <th>Week</th>
                <th>Persona</th>
                <th>Verdict</th>
                <th>Driver</th>
                <th>Correct driver</th>
                <th>Comment</th>
                <th>Author</th>
              </tr>
            </thead>
            <tbody>
              {[...rows].reverse().map((r) => {
                const vs = VERDICT_STYLE[r.verdict] ?? { badge: "badge-neutral", icon: "?" };
                return (
                  <tr key={r.id}>
                    <td style={{ fontSize: 11, fontFamily: "monospace", color: "var(--muted)" }}>
                      {fmt.date(r.created_at)}
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>{r.iso_week}</td>
                    <td style={{ fontSize: 12 }}>{r.persona?.replace(/_/g, " ")}</td>
                    <td>
                      <span className={`badge ${vs.badge}`}>
                        {vs.icon} {r.verdict?.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td style={{ fontSize: 12, fontFamily: "monospace" }}>
                      {r.driver?.replace(/_/g, " ") ?? "—"}
                    </td>
                    <td style={{ fontSize: 12, fontFamily: "monospace" }}>
                      {r.correct_driver?.replace(/_/g, " ") ?? "—"}
                    </td>
                    <td style={{ fontSize: 12, maxWidth: 200, color: "var(--muted)" }}>
                      {r.comment ?? "—"}
                    </td>
                    <td style={{ fontSize: 12 }}>{r.author ?? "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
