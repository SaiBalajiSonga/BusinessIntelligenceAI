import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(r'<div className="card-title" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>.*?Data Verification Check</div>', '<div className="card-title" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}><ShieldCheck size={16} /> Data Verification Check</div>', code)

code = re.sub(r'<div className="card-title" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>.*?LLM Calls</div>', '<div className="card-title" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}><Cpu size={16} /> System Diagnostics (LLM)</div>', code)

code = re.sub(r'<div className="card-title" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}>.*?What Would Raise Confidence</div>', '<div className="card-title" style={{ marginBottom: 12, display: "flex", alignItems: "center", gap: 8 }}><HelpCircle size={16} /> What Would Raise Confidence</div>', code)

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
