import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

pill_css = '''
.feedback-pill {
  background: var(--page);
  border: 1px solid var(--border);
  color: var(--ink-2);
  padding: 6px 12px;
  border-radius: 100px;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}
.feedback-pill:hover {
  background: var(--surface-2);
  border-color: var(--muted);
}
.feedback-pill.active {
  background: rgba(99, 102, 241, 0.1);
  border-color: var(--brand);
  color: var(--brand);
}
'''

css += '\n' + pill_css

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
