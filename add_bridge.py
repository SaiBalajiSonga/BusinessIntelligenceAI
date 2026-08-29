import re
with open('web/src/pages/NarrativeStudio.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Add Bridge import
if 'import { Bridge' not in code:
    code = code.replace('import type { Insight, Narrative } from "../types";', 'import { Bridge } from "../charts";\nimport type { Insight, Narrative } from "../types";')

# Revert layout and add right column with chart
old_layout = '<div style={{ maxWidth: 840, margin: "0 auto" }}>'
new_layout = '<div className="grid grid-2-1" style={{ gap: 24, alignItems: "start" }}>'
code = code.replace(old_layout, new_layout)

# Add right column before the closing tags of the grid container
closing_tags = '      </div>\n    </div>\n  );\n}'
right_col = '''
        {/* Right: Chart context */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16, position: "sticky", top: 16 }}>
          <div className="card" style={{ padding: 24 }}>
            <div className="card-title" style={{ marginBottom: 24 }}>Financial Impact Waterfall</div>
            {insight.expected !== null && insight.actual !== null ? (
              <div style={{ padding: "16px 0", height: 320, display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Bridge
                  expected={insight.expected}
                  actual={insight.actual}
                  causes={insight.causes}
                />
              </div>
            ) : (
              <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)" }}>
                Baseline data unavailable
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}'''
code = code.replace(closing_tags, right_col)

with open('web/src/pages/NarrativeStudio.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
