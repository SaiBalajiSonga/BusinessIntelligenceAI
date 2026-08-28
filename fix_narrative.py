import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(r'o" ', '? ', code)
code = re.sub(r'o- ', '? ', code)
code = re.sub(r'dY"O ', '?? ', code)

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
