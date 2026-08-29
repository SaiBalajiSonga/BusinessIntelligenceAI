import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

anim_css = '''
/* -------------------------------------------- SVG Animations -- */
@keyframes thumbPopLeft {
  0% { transform: scale(1) rotate(0deg); }
  40% { transform: scale(1.2) rotate(-15deg); color: var(--brand); }
  100% { transform: scale(1) rotate(0deg); color: var(--brand); }
}

@keyframes thumbPopRight {
  0% { transform: scale(1) rotate(0deg); }
  40% { transform: scale(1.2) rotate(15deg); color: var(--neg); }
  100% { transform: scale(1) rotate(0deg); color: var(--neg); }
}

.btn-feedback.anim-like svg {
  animation: thumbPopLeft 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
  fill: var(--brand);
}

.btn-feedback.anim-dislike svg {
  animation: thumbPopRight 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
  fill: var(--neg);
}
'''

if '/* -------------------------------------------- SVG Animations -- */' not in css:
    css += '\n' + anim_css

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
