# -*- coding: utf-8 -*-
import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    ns = f.read()

ns = ns.replace('isotonic calibration', '<span className="has-tooltip" data-tooltip="Machine learning method to convert raw confidence scores into true probabilities">isotonic calibration</span>')
ns = ns.replace('Tokens in</dt>', 'Tokens in</dt>') # skip

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(ns)
