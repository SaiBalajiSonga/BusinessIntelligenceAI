import re
with open('web/src/components/InlineFeedback.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Remove fill completely
code = code.replace('fill={state === "liked" ? "currentColor" : "none"}', '')
code = code.replace('fill={state === "disliked" || state === "disliking" ? "currentColor" : "none"}', '')

with open('web/src/components/InlineFeedback.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
