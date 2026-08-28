import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

form_css = '''
/* -------------------------------------------- Forms -- */
.form-field {
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
}
.form-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--ink);
  margin-bottom: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.form-input {
  background: var(--page);
  border: 1px solid var(--border);
  color: var(--ink);
  padding: 10px 12px;
  border-radius: 6px;
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s;
}
.form-input:focus {
  border-color: var(--brand);
}
.btn-primary {
  background: var(--brand);
  color: white;
  border: none;
}
.btn-primary:hover {
  background: #4f46e5;
  color: white;
}
.btn-ghost {
  background: transparent;
  border: 1px solid transparent;
}
.btn-ghost:hover {
  background: var(--surface-2);
}
'''

if '/* -------------------------------------------- Forms -- */' not in css:
    css += '\n' + form_css

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
