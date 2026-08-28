import re
with open('feedback/store.py', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('VERDICTS = ("correct", "wrong_driver", "known_cause", "not_material", "unclear")', 'VERDICTS = ("correct", "wrong_driver", "known_cause", "not_material", "unclear", "hallucination", "missed_factor", "bad_tone")')

with open('feedback/store.py', 'w', encoding='utf-8') as f:
    f.write(code)
