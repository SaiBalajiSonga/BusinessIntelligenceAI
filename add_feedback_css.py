import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

feedback_css = '''
/* -------------------------------------------- Feedback UI -- */
.btn-feedback {
  background: transparent;
  border: 1px solid transparent;
  color: var(--muted);
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-feedback:hover {
  background: var(--surface-2);
  color: var(--ink);
}

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

if '/* -------------------------------------------- Feedback UI -- */' not in css:
    css += '\n' + feedback_css

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
