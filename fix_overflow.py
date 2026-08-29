import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Remove overflow: hidden
code = code.replace('overflow: "hidden", marginBottom: 16', 'marginBottom: 16')

# Add border radius to footer
old_footer = 'padding: "16px 20px", background: "var(--surface-2)", borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between"'
new_footer = 'padding: "16px 20px", background: "var(--surface-2)", borderTop: "1px solid var(--border)", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottomLeftRadius: "var(--radius)", borderBottomRightRadius: "var(--radius)"'
code = code.replace(old_footer, new_footer)

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
