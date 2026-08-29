import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('import { api, fmt } from "../api";', 'import { api } from "../api";')
code = code.replace('  const totalTokens = narrative.calls.reduce((acc, c) => acc + c.input_tokens + c.output_tokens, 0);\n', '')
code = code.replace('  const totalCost = narrative.calls.reduce((acc, c) => acc + c.cost_usd, 0);\n', '')
code = code.replace('  const totalLatency = narrative.calls.reduce((acc, c) => acc + c.latency_ms, 0);\n', '')

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
