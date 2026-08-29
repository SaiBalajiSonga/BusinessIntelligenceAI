# -*- coding: utf-8 -*-
import re
with open('web/src/pages/Overview.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Replace Z-Score -> Anomaly Score
code = code.replace('data-tooltip="Z-score: Number of standard deviations away from the historical baseline"', 'data-tooltip="Anomaly Score: How unusual this movement is compared to historical patterns (Z-score)"')
code = code.replace('Z = {m.z.toFixed(2)}', 'Anomaly: {m.z.toFixed(2)}')
code = code.replace('<th>Z-score</th>', '<th>Anomaly Score</th>')

# Replace Telemetry
code = code.replace('<div className="card-title">Runtime Economics</div>', '<div className="card-title">System Diagnostics (Admin)</div>')

# Replace Freshness title
code = code.replace('<div className="card-title">Data Source Freshness</div>', '<div className="card-title">Data Quality & SLA Compliance</div>')

with open('web/src/pages/Overview.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
