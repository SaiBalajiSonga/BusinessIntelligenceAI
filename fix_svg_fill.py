import re
with open('web/src/components/InlineFeedback.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix the SVG rendering issue
code = code.replace('strokeWidth={state === "liked" ? 2.5 : 2}', 'strokeWidth={2}')
code = code.replace('strokeWidth={state === "disliked" || state === "disliking" ? 2.5 : 2}', 'strokeWidth={2}')

with open('web/src/components/InlineFeedback.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
