import re
with open('web/src/pages/RootCause.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

code = re.sub(r'o" ', '? ', code)
code = re.sub(r'o- ', '? ', code)
code = re.sub(r'dY"O ', '?? ', code)
code = re.sub(r'o\? ', '? ', code) # Just in case

with open('web/src/pages/RootCause.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
