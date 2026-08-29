import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Remove Bridge import
code = code.replace('import { Bridge } from "../charts";\n', '')

# 2. Change layout back to a simple left-aligned constrained container
old_layout = '<div className="grid grid-2-1" style={{ gap: 24, alignItems: "start" }}>'
new_layout = '<div style={{ maxWidth: 960 }}>'
code = code.replace(old_layout, new_layout)

# 3. Remove the entire right column with the chart
right_col_start = code.find('        {/* Right: Chart context */}')
if right_col_start != -1:
    code = code[:right_col_start] + '      </div>\n    </div>\n  );\n}\n'

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
