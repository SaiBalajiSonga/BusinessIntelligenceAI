import re
with open('web/src/App.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Add import
if 'import Integrations' not in code:
    code = code.replace('import System from "./pages/System";', 'import System from "./pages/System";\nimport Integrations from "./pages/Integrations";')

# Update NAV
old_nav = r'const NAV = \[\n\s*\{ to: "/", label: "Dashboard" \},\n\s*\{ to: "/investigation", label: "KPI Investigation" \},\n\s*\{ to: "/system", label: "System & Learning" \},\n\];'
new_nav = '''const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/investigation", label: "KPI Investigation" },
  { to: "/system", label: "System & Learning" },
  { to: "/integrations", label: "Data Connections" },
];'''
code = re.sub(old_nav, new_nav, code)

# Update routing
old_routes = r'<Route path="/system" element=\{<System />\} />\n\s*</Routes>'
new_routes = '''<Route path="/system" element={<System />} />
            <Route path="/integrations" element={<Integrations />} />
          </Routes>'''
code = re.sub(old_routes, new_routes, code)

with open('web/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
