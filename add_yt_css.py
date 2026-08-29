import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

yt_css = '''
/* -------------------------------------------- YouTube Feedback UI -- */
.btn-yt-feedback {
  background: transparent;
  border: none;
  color: var(--muted);
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 100px;
  cursor: pointer;
  transition: background-color 0.2s, color 0.2s;
  position: relative;
}
.btn-yt-feedback:hover {
  background: var(--surface-2);
  color: var(--ink);
}

@keyframes ytThumbLike {
  0% { transform: scale(1) rotate(0deg); }
  30% { transform: scale(1.3) rotate(-15deg); }
  60% { transform: scale(0.9) rotate(5deg); }
  100% { transform: scale(1) rotate(0deg); }
}

@keyframes ytThumbDislike {
  0% { transform: scale(1) rotate(0deg); }
  30% { transform: scale(1.3) rotate(15deg); }
  60% { transform: scale(0.9) rotate(-5deg); }
  100% { transform: scale(1) rotate(0deg); }
}

.btn-yt-feedback.active-like {
  color: var(--brand);
}
.btn-yt-feedback.active-like svg {
  animation: ytThumbLike 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
}

.btn-yt-feedback.active-dislike {
  color: var(--neg);
}
.btn-yt-feedback.active-dislike svg {
  animation: ytThumbDislike 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards;
}

@keyframes slideDown {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
'''

# Remove old feedback css to avoid clashes
old_feedback_start = css.find('/* -------------------------------------------- Feedback UI -- */')
if old_feedback_start != -1:
    css = css[:old_feedback_start]

css += '\n' + yt_css

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
