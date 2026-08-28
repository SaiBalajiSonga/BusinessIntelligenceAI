import re
with open('web/src/pages/RootCause.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Add import
if 'InlineFeedback' not in code:
    code = code.replace('import FeedbackModal from "../components/FeedbackModal";', 'import InlineFeedback from "../components/InlineFeedback";')

# Remove fbOpen and FeedbackModal
code = re.sub(r'const \[fbOpen, setFbOpen\] = useState\(false\);\n\s*const \[fbTarget, setFbTarget\] = useState<Cause \| null>\(null\);\n', '', code)
code = re.sub(r'<FeedbackModal.*?/>', '', code, flags=re.DOTALL)

# Replace the buttons block
old_buttons = r'<div style=\{\{\n\s*display: "flex",\n\s*gap: 8,\n\s*marginTop: 24.*?</aside>'
new_buttons = '''<div style={{ marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--border)" }}>
                  <InlineFeedback
                    week={activeWeek}
                    persona={activePersona}
                    driver={selected.factor}
                    confidence={insight?.confidence.score}
                    impact={selected.amount}
                  />
                </div>
              </div>
            </aside>'''
code = re.sub(old_buttons, new_buttons.strip(), code, flags=re.DOTALL)

with open('web/src/pages/RootCause.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
