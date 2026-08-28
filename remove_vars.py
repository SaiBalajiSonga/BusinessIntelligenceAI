import re
with open('web/src/pages/RootCause.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(r'const \[fbOpen, setFbOpen\] = useState\(false\);\n\s*const \[fbTarget, setFbTarget\] = useState<Cause \| null>\(null\);\n', '', code)

with open('web/src/pages/RootCause.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
