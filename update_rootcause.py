# -*- coding: utf-8 -*-
import re
with open('web/src/pages/RootCause.tsx', 'r', encoding='utf-8') as f:
    code = f.read()

if 'TrendingDown' not in code:
    code = code.replace('import InlineFeedback from "../components/InlineFeedback";', 'import InlineFeedback from "../components/InlineFeedback";\nimport { TrendingDown, Sprout, OctagonAlert, Lock, Info, AlertTriangle, Telescope } from "lucide-react";')

old_scenarios = r'const SCENARIOS = \[.*?\];'
new_scenarios = '''const SCENARIOS = [
  {
    id: "multifactor",
    icon: <TrendingDown size={18} />,
    title: "Multi-Factor Drop",
    sub: "Price · Mix · Stockout · Competitor",
    badge: "Required",
    badgeColor: "var(--neg)",
    week: "2026-W32",
    persona: "cfo",
    desc: "Net Revenue dropped £612k vs expectation. LMDI decomposes it into four interacting drivers — none alone explains the gap.",
  },
  {
    id: "sparse",
    icon: <Sprout size={18} />,
    title: "Sparse History",
    sub: "New SKU < 12 weeks data",
    badge: "Required",
    badgeColor: "var(--qualified)",
    week: "2026-W32",
    persona: "eu_category_manager",
    desc: "HOME-NEW-01 has insufficient history for STL baseline. Engine falls back to peer benchmark and flags low confidence.",
  },
  {
    id: "abstain",
    icon: <OctagonAlert size={18} />,
    title: "Low Confidence / Abstain",
    sub: "Contradictory signals detected",
    badge: "Required",
    badgeColor: "var(--abstain)",
    week: "2026-W32",
    persona: "analyst",
    desc: "When contradiction score or coverage is below threshold, the engine refuses to narrate and instead lists what would raise confidence.",
  },
  {
    id: "entitlement",
    icon: <Lock size={18} />,
    title: "Role-Based Entitlement",
    sub: "Row filter applied before analysis",
    badge: "Required",
    badgeColor: "var(--brand)",
    week: "2026-W32",
    persona: "eu_category_manager",
    desc: "EU Category Manager sees only DE, FR, NL. Gross margin % is masked. Entitlement is enforced in SQL before any computation.",
  },
];'''
code = re.sub(old_scenarios, new_scenarios, code, flags=re.DOTALL)

# Replace other emojis
code = code.replace('span style={{ fontSize: 16, flexShrink: 0 }}>??</span', 'span style={{ flexShrink: 0, marginTop: 2 }}><Info size={16} color="var(--brand)" /></span')
code = code.replace('?? <strong', '<Lock size={14} style={{ display: "inline", marginBottom: -2 }} /> <strong')
code = code.replace('?? Contradictory Evidence Detected', '<AlertTriangle size={18} style={{ display: "inline", marginBottom: -4, marginRight: 6 }} /> Contradictory Evidence Detected')
code = code.replace('?? Engine Abstaining — Insufficient Evidence', '<OctagonAlert size={18} style={{ display: "inline", marginBottom: -4, marginRight: 6 }} /> Engine Abstaining — Insufficient Evidence')
code = code.replace('?? Uninstrumented Drivers', '<Telescope size={18} style={{ display: "inline", marginBottom: -4, marginRight: 6 }} /> Uninstrumented Drivers')

with open('web/src/pages/RootCause.tsx', 'w', encoding='utf-8') as f:
    f.write(code)
