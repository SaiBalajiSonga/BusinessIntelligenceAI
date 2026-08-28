import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    code = f.read()

new_badges = '''
.badge-warning    { background: rgba(210, 153, 34, 0.15); color: var(--warning); }
.badge-critical   { background: rgba(248, 81, 73, 0.15);  color: var(--critical); }
'''

code = code.replace('.badge-neutral    { background: var(--surface-2);     color: var(--ink-2); }', '.badge-neutral    { background: var(--surface-2);     color: var(--ink-2); }' + new_badges)

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(code)
