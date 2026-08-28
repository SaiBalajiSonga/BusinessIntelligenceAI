import re
with open('web/src/pages/FeedbackHub.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

new_styles = '''const VERDICT_STYLE: Record<string, { badge: string; icon: string }> = {
  correct:       { badge: "badge-confident", icon: "?" },
  wrong_driver:  { badge: "badge-neg",       icon: "?" },
  missed_factor: { badge: "badge-warning",   icon: "??" },
  hallucination: { badge: "badge-critical",  icon: "??" },
  bad_tone:      { badge: "badge-neutral",   icon: "??" },
  known_cause:   { badge: "badge-neutral",   icon: "??" },
  not_material:  { badge: "badge-qualified", icon: "~" },
  unclear:       { badge: "badge-neutral",   icon: "?" },
};'''

code = re.sub(r'const VERDICT_STYLE:.*?};', new_styles, code, flags=re.DOTALL)

with open('web/src/pages/FeedbackHub.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
