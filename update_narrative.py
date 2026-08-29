import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Add Lucide imports
if 'import { ShieldCheck' not in code:
    code = code.replace('import InlineFeedback from "../components/InlineFeedback";', 'import InlineFeedback from "../components/InlineFeedback";\nimport { ShieldCheck, ShieldAlert, FileText, Activity, BrainCircuit, MessageSquare, AlertTriangle, Cpu, HelpCircle, Bot } from "lucide-react";')

# Replace the 3 cards with one unified card
# I will find the left column container
old_left_col_start = code.find('        {/* Left: Persona + Narrative */}')
old_left_col_end = code.find('        {/* Right: Guard report + LLM stats */}')
if old_left_col_start != -1 and old_left_col_end != -1:
    old_left_col = code[old_left_col_start:old_left_col_end]
    
    new_left_col = '''        {/* Left: Unified Narrative Card */}
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div className="card" style={{ padding: 0, overflow: "hidden", marginBottom: 16 }}>
            {/* Header: Persona */}
            <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--border)", display: "flex", justifyContent: "space-between", alignItems: "center", background: "var(--page)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div className="avatar">{personaInfo.avatar}</div>
                <div>
                  <div style={{ fontSize: 15, fontWeight: 600, color: "var(--ink)", lineHeight: 1.2 }}>
                    {personaInfo.name}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                    Regions: {personaInfo.scope.region.join(", ")}
                  </div>
                </div>
              </div>
              <span className={adge } style={{ fontSize: 12 }}>
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
                  {narrative.text.split("\\n\\n").map((para, i) => (
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
            <div style={{ padding: "16px 20px", background: "var(--surface-2)", borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
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
        </div>\n\n'''
    code = code.replace(old_left_col, new_left_col)

# Fix emojis in the right column
code = code.replace('dY>,? Data Verification Check', '<ShieldCheck size={16} /> Data Verification Check')
code = code.replace('dY" LLM Calls', '<Cpu size={16} /> System Diagnostics (LLM)')
code = code.replace('dY"^ What Would Raise Confidence', '<HelpCircle size={16} /> What Would Raise Confidence')
code = code.replace('className="card-title" style={{ marginBottom: 12 }}>', 'className="card-title" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>')

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
