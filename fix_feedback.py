import re
with open('web/src/components/InlineFeedback.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

# Fix emojis
code = code.replace('toast(v === "correct" ? "Thanks for the feedback!" : "Feedback recorded ?" learning loop updated", "success");', 'toast(v === "correct" ? "Thanks for the feedback!" : "Feedback recorded - learning loop updated", "success");')
code = code.replace('o" Feedback submitted', '? Feedback submitted')
code = code.replace('dY?', '??')
code = code.replace('dYZ', '??')

with open('web/src/components/InlineFeedback.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
