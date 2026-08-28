import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

github_theme = '''[data-theme="dark"] {
  color-scheme: dark;

  /* Sleek SaaS dark mode (GitHub / Supabase inspired) */
  --page:           #0d1117;
  --surface:        #161b22;
  --surface-2:      #21262d;
  --surface-3:      #30363d;
  --surface-hover:  #21262d;

  --ink:            #c9d1d9;
  --ink-2:          #8b949e;
  --muted:          #6e7681;

  --border:         #30363d;
  --border-strong:  #484f58;
  --hairline:       #21262d;

  --brand:          #58a6ff;
  --brand-dim:      #388bfd;
  --brand-subtle:   rgba(56, 139, 253, 0.1);
  --brand-text:     #79c0ff;

  --confident:      #3fb950;
  --confident-bg:   rgba(46, 160, 67, 0.15);
  --qualified:      #d29922;
  --qualified-bg:   rgba(187, 128, 9, 0.15);
  --abstain:        #f85149;
  --abstain-bg:     rgba(248, 81, 73, 0.1);

  --good:           #3fb950;
  --warning:        #d29922;
  --critical:       #f85149;

  --pos:            #3fb950;
  --pos-bg:         rgba(46, 160, 67, 0.15);
  --neg:            #f85149;
  --neg-bg:         rgba(248, 81, 73, 0.15);

  --shadow-sm:      0 0 0 1px var(--border);
  --shadow:         0 3px 6px rgba(1, 4, 9, 0.8), 0 0 0 1px var(--border);
  --shadow-md:      0 8px 24px rgba(1, 4, 9, 1), 0 0 0 1px var(--border);
  --shadow-ring:    0 0 0 3px rgba(88, 166, 255, 0.3);
}'''

css = re.sub(r'\[data-theme="dark"\] \{.*?\}', github_theme, css, flags=re.DOTALL)

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
