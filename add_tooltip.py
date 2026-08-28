import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

tooltip_css = '''
/* -------------------------------------------- Tooltips -- */
.has-tooltip {
  position: relative;
  cursor: help;
  text-decoration: underline;
  text-decoration-style: dotted;
  text-underline-offset: 4px;
  text-decoration-color: var(--muted);
}

.has-tooltip::after {
  content: attr(data-tooltip);
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(-8px);
  background: var(--ink);
  color: var(--page);
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s ease;
  z-index: 1000;
  pointer-events: none;
  box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

.has-tooltip::before {
  content: "";
  position: absolute;
  bottom: 100%;
  left: 50%;
  transform: translateX(-50%) translateY(0);
  border: 6px solid transparent;
  border-top-color: var(--ink);
  opacity: 0;
  visibility: hidden;
  transition: all 0.2s ease;
  z-index: 1000;
  pointer-events: none;
}

.has-tooltip:hover::after,
.has-tooltip:hover::before {
  opacity: 1;
  visibility: visible;
  transform: translateX(-50%) translateY(-2px);
}
.has-tooltip:hover::before {
  transform: translateX(-50%) translateY(4px);
}
'''

if '/* -------------------------------------------- Tooltips -- */' not in css:
    css += '\n' + tooltip_css

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
