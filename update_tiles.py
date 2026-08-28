import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

css = css.replace('.tiles-grid {\n  display: grid;\n  grid-template-columns: repeat(4, 1fr);\n  gap: 16px;\n  margin-bottom: 32px;\n}', '.tiles-grid {\n  display: grid;\n  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));\n  gap: 16px;\n  margin-bottom: 32px;\n}')
css = re.sub(r'@media \(max-width: 1200px\) \{ \.tiles-grid \{ grid-template-columns: repeat\(2, 1fr\); \} \}\n', '', css)

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
