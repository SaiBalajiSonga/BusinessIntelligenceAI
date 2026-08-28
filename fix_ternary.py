import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix the corrupted ternary
code = re.sub(r'\{persona === "cf\? \? ".*?\n', '{persona === "cfo" ? "??" : persona === "eu_category_manager" ? "???" : "??"}\n', code)

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
