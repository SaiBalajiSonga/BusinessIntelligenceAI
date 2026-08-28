import re
with open('web/src/styles.css', 'r', encoding='utf-8') as f:
    css = f.read()

dark_theme = '''[data-theme="dark"] {
  color-scheme: dark;

  /* Sleek SaaS dark mode (Vercel/Linear style) */
  --page:           #000000;
  --surface:        #09090b;
  --surface-2:      #18181b;
  --surface-3:      #27272a;
  --surface-hover:  #18181b;

  --ink:            #fafafa;
  --ink-2:          #a1a1aa;
  --muted:          #71717a;

  --border:         #27272a;
  --border-strong:  #3f3f46;
  --hairline:       #18181b;

  --brand:          #ffffff;
  --brand-dim:      #a1a1aa;
  --brand-subtle:   #18181b;
  --brand-text:     #fafafa;

  --confident:      #10b981;
  --confident-bg:   rgba(16, 185, 129, 0.1);
  --qualified:      #f59e0b;
  --qualified-bg:   rgba(245, 158, 11, 0.1);
  --abstain:        #ef4444;
  --abstain-bg:     rgba(239, 68, 68, 0.1);

  --good:           #10b981;
  --warning:        #f59e0b;
  --critical:       #ef4444;

  --pos:            #10b981;
  --pos-bg:         rgba(16, 185, 129, 0.1);
  --neg:            #ef4444;
  --neg-bg:         rgba(239, 68, 68, 0.1);

  --shadow-sm:      0 1px 2px rgba(0,0,0,0.8);
  --shadow:         0 4px 12px rgba(0,0,0,0.5);
  --shadow-md:      0 8px 24px rgba(0,0,0,0.6);
  --shadow-ring:    0 0 0 1px rgba(255, 255, 255, 0.2);
}'''

css = re.sub(r'\[data-theme="dark"\] \{.*?\}', dark_theme, css, flags=re.DOTALL)

kpi_material = '''.kpi-tile.material {
  border-color: var(--neg);
  /* Remove the massive solid red background, use a sleek glow instead */
  box-shadow: 0 0 12px var(--neg-bg);
  background: var(--surface);
}'''
css = re.sub(r'\.kpi-tile\.material \{.*?\}', kpi_material, css, flags=re.DOTALL)

topbar = '''.topbar {
  position: sticky;
  top: 0;
  background: var(--page);
  border-bottom: 1px solid var(--border);
  z-index: 90;
}'''
css = re.sub(r'\.topbar \{.*?\}', topbar, css, flags=re.DOTALL)

with open('web/src/styles.css', 'w', encoding='utf-8') as f:
    f.write(css)
