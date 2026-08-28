import { useState } from "react";
import { api } from "../api";
import { toast } from "./Toast";
import type { VerdictType } from "../types";

interface Props {
  open: boolean;
  onClose: () => void;
  week: string;
  persona: string;
  kpi?: string;
  driver?: string;
  confidence?: number;
  impact?: number;
}

const VERDICTS: { value: VerdictType; label: string; icon: string; desc: string }[] = [
  { value: "correct",      label: "Confirmed",     icon: "✓", desc: "This driver and direction are right" },
  { value: "wrong_driver", label: "Wrong Driver",   icon: "✗", desc: "Different driver caused this movement" },
  { value: "known_cause",  label: "Known Cause",    icon: "📌", desc: "We already knew about this event" },
  { value: "not_material", label: "Not Material",   icon: "~", desc: "Not worth acting on" },
  { value: "unclear",      label: "Unclear",        icon: "?", desc: "Need more data to decide" },
];

export default function FeedbackModal({
  open, onClose, week, persona, kpi = "net_revenue", driver, confidence, impact,
}: Props) {
  const [verdict, setVerdict] = useState<VerdictType | "">("");
  const [correctDriver, setCorrectDriver] = useState("");
  const [comment, setComment] = useState("");
  const [author, setAuthor] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const submit = async () => {
    if (!verdict) { toast("Please select a verdict", "error"); return; }
    setSubmitting(true);
    try {
      await api.submitFeedback({
        kpi, iso_week: week, persona, verdict,
        driver: driver ?? null,
        correct_driver: correctDriver || null,
        confidence_shown: confidence ?? null,
        impact_shown: impact ?? null,
        comment: comment || null,
        author: author || null,
      });
      toast("Feedback recorded — learning loop updated", "success", "🧠");
      onClose();
      setVerdict(""); setCorrectDriver(""); setComment(""); setAuthor("");
    } catch (e: unknown) {
      toast(`Failed: ${(e as Error).message}`, "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <span style={{ fontSize: 20 }}>🧠</span>
          <span className="modal-title">Analyst Feedback</span>
          <button className="close-btn btn-ghost" onClick={onClose}>×</button>
        </div>

        <div className="modal-body">
          {driver && (
            <div style={{ marginBottom: 16 }}>
              <div className="form-label">Reviewing driver</div>
              <code>{driver.replace(/_/g, " ")}</code>
              {confidence !== undefined && (
                <span style={{ marginLeft: 10, fontSize: 12, color: "var(--muted)" }}>
                  Confidence shown: {(confidence * 100).toFixed(0)}%
                </span>
              )}
            </div>
          )}

          <div className="form-field">
            <div className="form-label">Verdict *</div>
            <div style={{ display: "grid", gap: 6 }}>
              {VERDICTS.map((v) => (
                <button
                  key={v.value}
                  onClick={() => setVerdict(v.value)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "10px 14px",
                    borderRadius: "var(--radius-sm)",
                    border: `1px solid ${verdict === v.value ? "var(--brand)" : "var(--border)"}`,
                    background: verdict === v.value ? "var(--brand-subtle)" : "var(--surface-2)",
                    color: verdict === v.value ? "var(--brand)" : "var(--ink-2)",
                    cursor: "pointer",
                    font: "inherit",
                    textAlign: "left",
                    width: "100%",
                    transition: "all 0.12s",
                  }}
                >
                  <span style={{ fontSize: 16, width: 22, textAlign: "center" }}>{v.icon}</span>
                  <span>
                    <span style={{ display: "block", fontSize: 13, fontWeight: 500, color: "inherit" }}>{v.label}</span>
                    <span style={{ fontSize: 11.5, color: "var(--muted)" }}>{v.desc}</span>
                  </span>
                </button>
              ))}
            </div>
          </div>

          {verdict === "wrong_driver" && (
            <div className="form-field">
              <label className="form-label">Correct Driver (optional)</label>
              <input
                className="form-input"
                placeholder="e.g. competitor_price_index"
                value={correctDriver}
                onChange={(e) => setCorrectDriver(e.target.value)}
              />
            </div>
          )}

          <div className="form-field">
            <label className="form-label">Comment (optional)</label>
            <textarea
              className="form-textarea"
              placeholder="Add context — what do you know that the engine doesn't?"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>

          <div className="form-field" style={{ marginBottom: 0 }}>
            <label className="form-label">Your name (optional)</label>
            <input
              className="form-input"
              placeholder="e.g. alice.smith"
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
            />
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" onClick={submit} disabled={submitting || !verdict}>
            {submitting ? "Saving…" : "Submit Feedback"}
          </button>
        </div>
      </div>
    </div>
  );
}
