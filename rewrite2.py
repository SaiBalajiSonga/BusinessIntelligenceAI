import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

# Make sure we don't have duplicate .topbar
css = re.sub(r'\.topbar \{.*?\}', '', css, flags=re.DOTALL)

# Add it back once
topbar = '''
/* -------------------------------------------- Top Bar -- */
.topbar {
  position: sticky;
  top: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
  z-index: 90;
}
[data-theme="light"] .topbar {
  background: rgba(255, 255, 255, 0.7);
}
'''

css = css.replace('/* -------------------------------------------- Top Bar -- */', topbar)

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
