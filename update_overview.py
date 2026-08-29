import re
with open('web/src/pages/Overview.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

if 'Info' not in code:
    code = code.replace('import Loader from "../components/Loader";', 'import Loader from "../components/Loader";\nimport { Info } from "lucide-react";')

code = code.replace('span style={{ fontSize: 16, flexShrink: 0 }}>??</span', 'span style={{ flexShrink: 0, marginTop: 2 }}><Info size={16} color="var(--brand)" /></span')

with open('web/src/pages/Overview.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
