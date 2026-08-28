import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

loader_css = '''
/* -------------------------------------------- Custom Loader -- */
.loader-animation {
  display: grid;
  grid-template-columns: repeat(2, 12px);
  gap: 4px;
  transform: rotate(45deg);
}

.cube {
  width: 12px;
  height: 12px;
  background-color: var(--brand);
  animation: foldCube 2.4s infinite linear both;
  transform-origin: 100% 100%;
}

.cube:nth-child(2) {
  transform: scale(1.1) rotateZ(90deg);
  animation-delay: 0.3s;
}
.cube:nth-child(4) {
  transform: scale(1.1) rotateZ(180deg);
  animation-delay: 0.6s;
}
.cube:nth-child(3) {
  transform: scale(1.1) rotateZ(270deg);
  animation-delay: 0.9s;
}

@keyframes foldCube {
  0%, 10% { transform: perspective(140px) rotateX(-180deg); opacity: 0; }
  25%, 75% { transform: perspective(140px) rotateX(0deg); opacity: 1; }
  90%, 100% { transform: perspective(140px) rotateY(180deg); opacity: 0; }
}
'''

if '/* -------------------------------------------- Custom Loader -- */' not in css:
    css += '\n' + loader_css

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
