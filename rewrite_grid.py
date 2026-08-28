import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

css = css.replace('.tiles-grid {\n  display: grid;\n  grid-template-columns: repeat(4, 1fr);\n  gap: 24px;\n  margin-bottom: 32px;\n}', '.tiles-grid {\n  display: grid;\n  grid-template-columns: repeat(4, 1fr);\n  gap: 16px;\n  margin-bottom: 32px;\n}')

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
