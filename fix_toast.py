import re
with open('web/src/components/InlineFeedback.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('toast(Failed: , "error");', 'toast("Failed: " + (e as Error).message, "error");')

with open('web/src/components/InlineFeedback.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
