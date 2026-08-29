# -*- coding: utf-8 -*-
import re
with open('web/src/pages/RootCause.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace SCENARIOS text
code = code.replace('LMDI decomposes it into four interacting drivers', 'Advanced analytics isolates the impact of four interacting drivers')
code = code.replace('When contradiction score or coverage is below threshold', 'When data signals are contradictory or missing')

# Replace Rung 1: LMDI Decomposition -> Rung 1: Driver Contribution Analysis
code = code.replace('Rung 1: LMDI Decomposition', 'Rung 1: Driver Contribution Analysis')

# Replace Rung 3: Jensen-Shannon Surprise -> Rung 3: Uncharacteristic Behavior Detection
code = code.replace('Rung 3: Jensen-Shannon Surprise', 'Rung 3: Uncharacteristic Behavior Detection')

# Replace Analytic Rung cascade
code = code.replace('Running analysis cascade (Rungs 0-5)...', 'Running Diagnostic Engine...')

with open('web/src/pages/RootCause.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
