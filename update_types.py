import re
with open('web/src/types.ts', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('export type VerdictType = "correct" | "wrong_driver" | "known_cause" | "not_material" | "unclear";', 'export type VerdictType = "correct" | "wrong_driver" | "known_cause" | "not_material" | "unclear" | "hallucination" | "missed_factor" | "bad_tone";')

with open('web/src/types.ts', 'w', encoding='utf-8') as f:
    f.write(code)
