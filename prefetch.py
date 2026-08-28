import re
with open('web/src/App.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Add api to imports if not there
if 'import { api }' not in code:
    code = code.replace('import { useState }', 'import { useState }\nimport { api }', 1)

# Modify the map inside the tabs
old_map = r'\{NAV\.map\(item => \{\n\s*const active = item\.to === "/" \? location\.pathname === "/" : location\.pathname\.startsWith\(item\.to\);\n\s*return \(\n\s*<Link\n\s*key=\{item\.to\}\n\s*to=\{item\.to\}'
new_map = '''{NAV.map(item => {
          const active = item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              onMouseEnter={() => {
                // Prefetch data based on route
                if (item.to === "/investigation") {
                  api.insight("2026-W32", "cfo");
                  api.narrative("2026-W32", "cfo");
                } else if (item.to === "/") {
                  api.movements("2026-W32", "cfo");
                } else if (item.to === "/system") {
                  api.learning("2026-W32", "cfo");
                }
              }}'''

code = re.sub(old_map, new_map, code, flags=re.DOTALL)

with open('web/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
