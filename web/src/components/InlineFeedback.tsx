import { useState } from "react";
import { api } from "../api";
import { toast } from "./Toast";
import type { VerdictType } from "../types";

interface Props {
  week: string;
  persona: string;
  kpi?: string;
  driver?: string | null;
  confidence?: number;
  impact?: number;
}

const NEG_VERDICTS: { value: VerdictType; label: string; desc: string }[] = [
  { value: "wrong_driver", label: "Wrong Driver", desc: "Engine blamed the wrong factor" },
  { value: "missed_factor", label: "Missed Factor", desc: "Failed to identify a key secondary driver" },
  { value: "hallucination", label: "Hallucination", desc: "Fabricated numbers or facts" },
  { value: "bad_tone", label: "Bad Tone", desc: "Inappropriate persona tone or verbosity" },
  { value: "known_cause",  label: "Known Cause",  desc: "Already planned/known event" },
  { value: "not_material", label: "Not Material", desc: "Too small to care about" },
];

export default function InlineFeedback({
  week, persona, kpi = "net_revenue", driver, confidence, impact
}: Props) {
  const [state, setState] = useState<"idle" | "liked" | "disliked" | "submitted">("idle");
  const [submitting, setSubmitting] = useState(false);
  const [verdict, setVerdict] = useState<VerdictType | "">("");
  const [comment, setComment] = useState("");

  const submit = async (v: VerdictType, c = "") => {
    setSubmitting(true);
    try {
      await api.submitFeedback({
        kpi, iso_week: week, persona, verdict: v,
        driver: driver ?? null,
        confidence_shown: confidence ?? null,
        impact_shown: impact ?? null,
        comment: c || null,
      });
      toast(v === "correct" ? "Thanks for the feedback!" : "Feedback recorded — learning loop updated", "success");
      setState("submitted");
    } catch (e: unknown) {
      toast(`Failed: ${(e as Error).message}`, "error");
      setState("idle");
    } finally {
      setSubmitting(false);
    }
  };

  if (state === "submitted") {
    return (
      <div style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--good)", background: "var(--pos-bg)", padding: "6px 12px", borderRadius: "var(--radius-sm)", border: "1px solid var(--pos)" }}>
        ✓ Feedback submitted
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-start" }}>
      {state === "idle" && (
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 13, color: "var(--muted)", marginRight: 4 }}>Was this accurate?</span>
          <button 
            className="btn btn-sm btn-ghost" 
            onClick={() => { setState("liked"); submit("correct"); }}
            title="Accurate"
          >
            👍
          </button>
          <button 
            className="btn btn-sm btn-ghost" 
            onClick={() => setState("disliked")}
            title="Inaccurate"
          >
            👎
          </button>
        </div>
      )}

      {state === "liked" && (
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--muted)" }}>
          <span className="spinner" style={{ width: 14, height: 14 }} /> Recording...
        </div>
      )}

      {state === "disliked" && (
        <div style={{ 
          background: "var(--surface-2)", 
          border: "1px solid var(--border)", 
          borderRadius: "var(--radius)", 
          padding: 16,
          width: "100%",
          maxWidth: 400
        }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)", marginBottom: 12 }}>
            What was wrong?
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
            {NEG_VERDICTS.map(v => (
              <label key={v.value} style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer", fontSize: 13 }}>
                <input 
                  type="radio" 
                  name="verdict" 
                  checked={verdict === v.value} 
                  onChange={() => setVerdict(v.value)}
                  style={{ marginTop: 3 }}
                />
                <div>
                  <div style={{ fontWeight: 500, color: "var(--ink)" }}>{v.label}</div>
                  <div style={{ color: "var(--muted)", fontSize: 12 }}>{v.desc}</div>
                </div>
              </label>
            ))}
          </div>
          
          <textarea
            className="form-textarea"
            placeholder="Additional details (optional)..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            style={{ marginBottom: 12, minHeight: 60 }}
          />

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button className="btn btn-sm btn-ghost" onClick={() => setState("idle")}>Cancel</button>
            <button 
              className="btn btn-sm btn-primary" 
              disabled={!verdict || submitting}
              onClick={() => submit(verdict as VerdictType, comment)}
            >
              {submitting ? "Submitting..." : "Submit"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
