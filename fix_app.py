# -*- coding: utf-8 -*-
import re
with open('web/src/App.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Add Route
old_routes_end = r'            } />\n\s*</Routes>'
new_routes_end = '''            } />
            <Route path="/integrations" element={<Integrations />} />
          </Routes>'''
code = re.sub(old_routes_end, new_routes_end, code)

# Ensure import exists
if 'import Integrations' not in code:
    code = code.replace('import ToastContainer from "./components/Toast";', 'import ToastContainer from "./components/Toast";\nimport Integrations from "./pages/Integrations";')

with open('web/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(code)

# Fix emojis in Integrations.tsx
with open('web/src/pages/Integrations.tsx', 'r', encoding='utf-8') as f:
    intg = f.read()

intg = re.sub(r'icon: ".*?", desc: "Connect to your Snowflake', 'icon: "??", desc: "Connect to your Snowflake', intg)
intg = re.sub(r'icon: ".*?", desc: "Connect to your GCP', 'icon: "??", desc: "Connect to your GCP', intg)
intg = re.sub(r'icon: ".*?", desc: "Connect to standard PostgreSQL', 'icon: "??", desc: "Connect to standard PostgreSQL', intg)
intg = re.sub(r'icon: ".*?", desc: "Connect to your AWS', 'icon: "??", desc: "Connect to your AWS', intg)
intg = re.sub(r'icon: ".*?", desc: "Connect to Databricks', 'icon: "??", desc: "Connect to Databricks', intg)
intg = re.sub(r'\{ error\}</div>', '?? {error}</div>', intg) # wait, just replace the error banner
intg = re.sub(r'<div className="error-banner".*?\{error\}</div>', '<div className="error-banner" style={{ marginBottom: 16 }}>?? {error}</div>', intg)
intg = re.sub(r'<div style=\{\{ fontSize: 48, marginBottom: 16 \}\}>.*?</div>', '<div style={{ fontSize: 48, marginBottom: 16 }}>?</div>', intg)

with open('web/src/pages/Integrations.tsx', 'w', encoding='utf-8') as f:
    f.write(intg)

