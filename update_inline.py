import re
with open('web/src/components/InlineFeedback.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

new_verdicts = '''const NEG_VERDICTS: { value: VerdictType; label: string; desc: string }[] = [
  { value: "wrong_driver", label: "Wrong Driver", desc: "Engine blamed the wrong factor" },
  { value: "missed_factor", label: "Missed Factor", desc: "Failed to identify a key secondary driver" },
  { value: "hallucination", label: "Hallucination", desc: "Fabricated numbers or facts" },
  { value: "bad_tone", label: "Bad Tone", desc: "Inappropriate persona tone or verbosity" },
  { value: "known_cause",  label: "Known Cause",  desc: "Already planned/known event" },
  { value: "not_material", label: "Not Material", desc: "Too small to care about" },
];'''

code = re.sub(r'const NEG_VERDICTS:.*?\];', new_verdicts, code, flags=re.DOTALL)

with open('web/src/components/InlineFeedback.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
