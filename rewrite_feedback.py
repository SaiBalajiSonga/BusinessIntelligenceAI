import re
with open('web/src/components/InlineFeedback.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# I will replace the entire file content using python script to ensure it's fully rewritten

new_code = '''import { useState } from "react";
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

const ThumbsUp = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
  </svg>
);

const ThumbsDown = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
  </svg>
);

const CheckIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="20 6 9 17 4 12"></polyline>
  </svg>
);

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
      toast(v === "correct" ? "Feedback recorded." : "Feedback recorded - learning loop updated.", "success");
      setState("submitted");
    } catch (e: unknown) {
      toast(Failed: , "error");
      setState("idle");
    } finally {
      setSubmitting(false);
    }
  };

  if (state === "submitted") {
    return (
      <div style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 500, color: "var(--brand)", padding: "4px 0" }}>
        <CheckIcon /> Feedback submitted
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-start" }}>
      {state === "idle" && (
        <div style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
          <span style={{ fontSize: 12, color: "var(--muted)", marginRight: 8 }}>Is this accurate?</span>
          <button 
            className="btn-feedback" 
            onClick={() => { setState("liked"); submit("correct"); }}
            title="Accurate"
          >
            <ThumbsUp />
          </button>
          <button 
            className="btn-feedback" 
            onClick={() => setState("disliked")}
            title="Inaccurate"
          >
            <ThumbsDown />
          </button>
        </div>
      )}

      {state === "liked" && (
        <div style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--muted)", padding: "4px 0" }}>
          <span className="spinner" style={{ width: 12, height: 12 }} /> Recording...
        </div>
      )}

      {state === "disliked" && (
        <div style={{ 
          background: "var(--surface)", 
          border: "1px solid var(--border)", 
          borderRadius: "var(--radius-lg)", 
          padding: "16px",
          width: "100%",
          maxWidth: 420,
          boxShadow: "0 4px 12px rgba(0,0,0,0.1)"
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", marginBottom: 16 }}>
            What was wrong?
          </div>
          
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
            {NEG_VERDICTS.map(v => (
              <button
                key={v.value}
                onClick={() => setVerdict(v.value)}
                className={eedback-pill }
                title={v.desc}
              >
                {v.label}
              </button>
            ))}
          </div>
          
          <textarea
            className="form-input"
            placeholder="Additional details (optional)..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            style={{ marginBottom: 16, minHeight: 60, width: "100%", fontSize: 13 }}
          />

          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button className="btn btn-sm btn-ghost" onClick={() => setState("idle")}>Cancel</button>
            <button 
              className="btn btn-sm btn-primary" 
              disabled={!verdict || submitting}
              onClick={() => submit(verdict as VerdictType, comment)}
            >
              {submitting ? "Submitting..." : "Submit Feedback"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
'''

with open('web/src/components/InlineFeedback.tsx', 'w', encoding='utf-8') as f:
    f.write(new_code)
