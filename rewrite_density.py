import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

# Make density tighter
css = css.replace('.card {\n  background: var(--surface);\n  border: 1px solid var(--border);\n  border-radius: var(--radius-lg);\n  padding: 32px;\n  box-shadow: none;\n}', '.card {\n  background: var(--surface);\n  border: 1px solid var(--border);\n  border-radius: var(--radius-lg);\n  padding: 24px;\n  box-shadow: none;\n}')
css = css.replace('.kpi-tile {\n  background: var(--surface);\n  border: 1px solid var(--border);\n  border-radius: var(--radius-lg);\n  padding: 24px;\n  box-shadow: none;\n  transition: transform 0.2s ease, box-shadow 0.2s ease;\n}', '.kpi-tile {\n  background: var(--surface);\n  border: 1px solid var(--border);\n  border-radius: var(--radius-lg);\n  padding: 20px;\n  box-shadow: none;\n  transition: border-color 0.2s ease;\n}')

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
