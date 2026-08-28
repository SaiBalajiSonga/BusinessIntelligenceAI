import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Add import
if 'InlineFeedback' not in code:
    code = code.replace('import FeedbackModal from "../components/FeedbackModal";', 'import InlineFeedback from "../components/InlineFeedback";')

# Replace fbOpen state
code = re.sub(r'const \[fbOpen, setFbOpen\] = useState\(false\);\n', '', code)

# Replace the analyst feedback box
old_box = r'\{!hideHeader && \(\n\s*<div style=\{\{\n\s*marginTop: 24.*?</div>\n\s*\)\}'
new_box = '''
        <div style={{ marginTop: 24, paddingTop: 20, borderTop: "1px solid var(--border)" }}>
          <InlineFeedback
            week={week}
            persona={persona}
            kpi={insight.kpi}
            confidence={insight.confidence.score}
            impact={insight.gap ?? undefined}
          />
        </div>
'''
code = re.sub(old_box, new_box.strip(), code, flags=re.DOTALL)

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
