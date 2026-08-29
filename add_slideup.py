import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

anim_css = '''
@keyframes slideUp {
  from { opacity: 0; transform: translateY(10px) scale(0.95); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
'''
if 'slideUp' not in css:
    css += '\n' + anim_css

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
