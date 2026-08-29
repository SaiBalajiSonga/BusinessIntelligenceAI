import { useState } from "react";
import { api } from "../api";
import { toast } from "./Toast";
import type { VerdictType } from "../types";
import { ThumbsUp, ThumbsDown } from "lucide-react";

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
  const [state, setState] = useState<"idle" | "liked" | "disliking" | "disliked">("idle");
  const [submitting, setSubmitting] = useState(false);
  const [verdict, setVerdict] = useState<VerdictType | "">("");
  const [comment, setComment] = useState("");

  const submit = async (v: VerdictType, c = "", isUnlike = false) => {
    // In a real app we'd have an API to remove feedback. 
    // Here we just visually revert it.
    if (isUnlike) return;

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
    } catch (e: any) {
      toast("Failed: " + (e.message || "Unknown error"), "error");
      setState("idle");
    } finally {
      setSubmitting(false);
    }
  };

  const handleLike = () => {
    if (state === "liked") {
      setState("idle");
      // Optional: submit undo API call here
    } else {
      setState("liked");
      submit("correct");
    }
  };

  const handleDislike = () => {
    if (state === "disliked" || state === "disliking") {
      setState("idle");
      setVerdict("");
      setComment("");
    } else {
      setState("disliking");
    }
  };

  const submitDislike = () => {
    setState("disliked");
    submit(verdict as VerdictType, comment);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-start" }}>
      <div style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
        <span style={{ fontSize: 12, color: "var(--muted)", marginRight: 8, opacity: (state === "idle" || state === "disliking") ? 1 : 0, transition: "opacity 0.2s" }}>
          Is this accurate?
        </span>
        <button 
          className={`btn-yt-feedback ${state === "liked" ? "active-like" : ""}`}
          onClick={handleLike}
          title={state === "liked" ? "Unlike" : "Like"}
        >
          <ThumbsUp 
            size={16} 
            strokeWidth={state === "liked" ? 2.5 : 2} 
            fill={state === "liked" ? "currentColor" : "none"} 
          />
        </button>
        <div style={{ width: 1, height: 16, background: "var(--border)", margin: "0 4px" }} />
        <button 
          className={`btn-yt-feedback ${state === "disliked" || state === "disliking" ? "active-dislike" : ""}`} 
          onClick={handleDislike}
          title={state === "disliked" ? "Remove dislike" : "Dislike"}
        >
          <ThumbsDown 
            size={16} 
            strokeWidth={state === "disliked" || state === "disliking" ? 2.5 : 2} 
            fill={state === "disliked" || state === "disliking" ? "currentColor" : "none"} 
          />
        </button>
      </div>

      {state === "disliking" && (
        <div style={{ 
          background: "var(--surface)", 
          border: "1px solid var(--border)", 
          borderRadius: "var(--radius-lg)", 
          padding: "16px",
          width: "100%",
          maxWidth: 420,
          boxShadow: "0 4px 12px rgba(0,0,0,0.1)",
          animation: "slideDown 0.2s ease-out"
        }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", marginBottom: 16, display: "flex", alignItems: "center", gap: 6 }}>
            What was wrong?
          </div>
          
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
            {NEG_VERDICTS.map(v => (
              <button
                key={v.value}
                onClick={() => setVerdict(v.value)}
                className={`feedback-pill ${verdict === v.value ? "active" : ""}`}
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
              onClick={submitDislike}
            >
              {submitting ? "Submitting..." : "Submit Feedback"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
