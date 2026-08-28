import re
with open('api/main.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('verdict: str = Field(description="correct | wrong_driver | known_cause | not_material | unclear")', 'verdict: str = Field(description="correct | wrong_driver | known_cause | not_material | unclear | hallucination | missed_factor | bad_tone")')

with open('api/main.py', 'w', encoding='utf-8') as f:
    f.write(code)
