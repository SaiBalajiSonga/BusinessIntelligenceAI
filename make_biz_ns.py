# -*- coding: utf-8 -*-
import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Numeric Guard Report -> Data Verification Check
code = code.replace('Numeric Guard Report', 'Data Verification Check')
code = code.replace('Failed (2 Hallucinations Intercepted)', 'Failed (Data mismatch detected)')

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
