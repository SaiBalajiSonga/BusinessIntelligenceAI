import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

# Make borders crisp
css = css.replace('--radius-sm:      6px;', '--radius-sm:      6px;')
css = css.replace('--radius:         12px;', '--radius:         6px;')
css = css.replace('--radius-lg:      16px;', '--radius-lg:      8px;')

# Remove the floating shadow on cards since GitHub prefers solid borders over floating shadows
css = css.replace('box-shadow: var(--shadow);', 'box-shadow: none;')
css = css.replace('.kpi-tile:hover { transform: translateY(-2px); box-shadow: var(--shadow-md); }', '.kpi-tile:hover { border-color: var(--border-strong); }')
css = css.replace('.scenario-card:hover { border-color: var(--brand-dim); box-shadow: var(--shadow); transform: translateY(-2px); }', '.scenario-card:hover { border-color: var(--brand-dim); }')

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
