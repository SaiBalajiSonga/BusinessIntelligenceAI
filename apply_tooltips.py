# -*- coding: utf-8 -*-
import re

# For Overview.tsx
with open('web/src/pages/Overview.tsx', 'r', encoding='utf-8') as f:
    ov = f.read()
ov = ov.replace('>material<', ' className="has-tooltip" data-tooltip="Exceeds statistical (Z > 2.5) and business (GBP 150k) thresholds">material<')
ov = ov.replace('Z = {m.z.toFixed(2)}', '<span className="has-tooltip" data-tooltip="Z-score: Number of standard deviations away from the historical baseline">Z = {m.z.toFixed(2)}</span>')
ov = ov.replace('SLA compliance', '<span className="has-tooltip" data-tooltip="Service Level Agreement: The maximum acceptable data delay">SLA compliance</span>')
ov = ov.replace('P50 Latency', '<span className="has-tooltip" data-tooltip="Median response time: 50% of requests are faster than this">P50 Latency</span>')
with open('web/src/pages/Overview.tsx', 'w', encoding='utf-8') as f:
    f.write(ov)

# For RootCause.tsx
with open('web/src/pages/RootCause.tsx', 'r', encoding='utf-8') as f:
    rc = f.read()
rc = rc.replace('Deterministic decomposition', '<span className="has-tooltip" data-tooltip="Mathematically breaking down the KPI into exact components (no AI guessing)">Deterministic decomposition</span>')
rc = rc.replace('Jensen-Shannon surprise', '<span className="has-tooltip" data-tooltip="Information theory metric: ranks drivers by how wildly their distribution shifted">Jensen-Shannon surprise</span>')
rc = rc.replace('Causal inference', '<span className="has-tooltip" data-tooltip="Statistical methods used to prove cause-and-effect, not just correlation">Causal inference</span>')
rc = rc.replace('Coverage</div>', 'Coverage <span style={{fontSize: 14}} className="has-tooltip" data-tooltip="Percentage of the KPI gap successfully linked to a specific cause">??</span></div>')
rc = rc.replace('LMDI Decomposition', '<span className="has-tooltip" data-tooltip="Logarithmic Mean Divisia Index: Splits a gap perfectly with zero leftover unexplained variance">LMDI Decomposition</span>')
with open('web/src/pages/RootCause.tsx', 'w', encoding='utf-8') as f:
    f.write(rc)
