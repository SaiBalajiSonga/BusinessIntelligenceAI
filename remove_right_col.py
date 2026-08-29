import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Change grid-2-1 to a centered layout
code = code.replace('<div className="grid grid-2-1" style={{ gap: 20 }}>', '<div style={{ maxWidth: 840, margin: "0 auto" }}>')

# 2. Extract "What Would Raise Confidence" logic
confidence_start = code.find('{/* What would raise confidence */}')
confidence_end = code.find('      </div>\n    </div>\n  );\n}')
if confidence_start != -1 and confidence_end != -1:
    confidence_block = code[confidence_start:confidence_end]
    
    # Remove the entire Right Column
    right_col_start = code.find('{/* Right: Guard report + LLM stats */}')
    if right_col_start != -1:
        code = code[:right_col_start] + '      </div>\n    </div>\n  );\n}\n'
    
    # We want to insert the confidence block inside the main card, before the Guard Badges.
    # Actually, before Guard Badges is a good place.
    guard_badges_start = code.find('{/* Guard badges */}')
    if guard_badges_start != -1:
        new_confidence = '''
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
              
              '''
        code = code[:guard_badges_start] + new_confidence + code[guard_badges_start:]

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
