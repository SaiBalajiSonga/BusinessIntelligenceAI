import NarrativeStudio from "./NarrativeStudio";
import RootCause from "./RootCause";
import ActionPlaybook from "./Actions";

export default function DeepDive({ week, persona }: { week: string; persona: string }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "40px" }}>
      <div className="page-header" style={{ marginBottom: "0" }}>
        <h1 className="page-title">KPI Investigation</h1>
        <p className="page-sub">
          End-to-end analysis of the focal week. Narrative synthesis, root cause attribution, and recommended actions.
        </p>
      </div>

      <div style={{ padding: "32px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow)" }}>
        <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--ink)", marginBottom: "24px" }}>1. Executive Narrative</h2>
        <NarrativeStudio week={week} persona={persona} hideHeader />
      </div>

      <div style={{ padding: "32px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow)" }}>
        <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--ink)", marginBottom: "24px" }}>2. Root Cause Attribution</h2>
        <RootCause week={week} persona={persona} hideHeader />
      </div>

      <div style={{ padding: "32px", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", boxShadow: "var(--shadow)" }}>
        <h2 style={{ fontSize: "18px", fontWeight: 600, color: "var(--ink)", marginBottom: "24px" }}>3. Action Playbook</h2>
        <ActionPlaybook week={week} persona={persona} hideHeader />
      </div>
    </div>
  );
}
