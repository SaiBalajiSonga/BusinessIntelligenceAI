import { useEffect, useState } from "react";
import Loader from "../components/Loader";
import { SkeletonInvestigate } from "../components/Skeleton";
import { api, fmt } from "../api";
import { Bridge, ConfidenceBars, Pipeline } from "../charts";
import InlineFeedback from "../components/InlineFeedback";
import { RecCard } from "./Actions";
import {
  TrendingDown, Sprout, OctagonAlert, Lock, AlertTriangle,
  MapPin, Telescope, CheckCircle2, Bot, ShieldAlert, HelpCircle,
  BookOpen, Layers, Gauge, Zap as ZapIcon, Users, ChevronDown, ChevronUp,
} from "lucide-react";
import type { Actions, Attribution, Insight, Narrative, Persona, Split } from "../types";

interface Props { week: string; persona: string; }

const WEIGHTS: Record<string, number> = {
  coverage: 0.45, freshness: 0.15, history_depth: 0.15,
  method_strength: 0.15, contradiction: -0.2,
};

const BAND_BADGE: Record<string, string> = {
  confident: "badge-confident", qualified: "badge-qualified", abstain: "badge-abstain",
};

const SCENARIOS = [
  {
    id: "multifactor", icon: <TrendingDown size={17} />, title: "Multi-Factor Drop",
    sub: "Price · Mix · Stockout · Competitor", week: "2026-W32", persona: "cfo",
    desc: "Net Revenue dropped £612k vs expectation — four interacting drivers, none alone sufficient to explain the gap.",
  },
  {
    id: "sparse", icon: <Sprout size={17} />, title: "Sparse History",
    sub: "New SKU, under 12 weeks of data", week: "2026-W32", persona: "eu_category_manager",
    desc: "HOME-NEW-01 has insufficient history for an STL baseline — the engine falls back to a peer benchmark and flags reduced confidence.",
  },
  {
    id: "abstain", icon: <OctagonAlert size={17} />, title: "Low Confidence",
    sub: "Under 12 weeks of history, drilled in", week: "2026-W32", persona: "analyst", sku: "HOME-NEW-01",
    desc: "Scoped down to HOME-NEW-01 alone, there isn't even enough history to establish a baseline — not just a lower score, a genuine refusal to guess. The LLM is never called.",
  },
  {
    id: "entitlement", icon: <Lock size={17} />, title: "Role-Based Entitlement",
    sub: "Row filter applied before analysis", week: "2026-W32", persona: "eu_category_manager",
    desc: "The EU Category Manager sees only DE, FR, NL, with Gross Margin % masked — enforced in SQL, not in the UI.",
  },
];

const RUNG_METHODS: Record<number, string> = {
  1: "Rung 1 — LMDI over the revenue identity. Exact; contributions sum to the gap with zero residual.",
  2: "Rung 2 — Bennet indicator splitting ASP into price and mix. Exact.",
  3: "Rung 3 — Dimensional attribution ranked by Jensen-Shannon surprise. Exact.",
  4: "Rung 4 — Difference-in-differences with two-way fixed effects. Carries assumptions.",
};

const SECTIONS = [
  { id: "story", label: "The Story", icon: BookOpen },
  { id: "evidence", label: "Evidence", icon: Layers },
  { id: "confidence", label: "Confidence", icon: Gauge },
  { id: "actions", label: "Next Steps", icon: ZapIcon },
];

export default function Investigate({ week: _week, persona: _persona }: Props) {
  const [scenarioId, setScenarioId] = useState("multifactor");
  const [insight, setInsight] = useState<Insight | null>(null);
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [actions, setActions] = useState<Actions | null>(null);
  const [attribution, setAttribution] = useState<Attribution | null>(null);
  const [split, setSplit] = useState<Split | null>(null);
  const [expandedCause, setExpandedCause] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState("story");
  const [loading, setLoading] = useState(true);
  const [actionsLoading, setActionsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [compareOpen, setCompareOpen] = useState(false);
  const [compareData, setCompareData] = useState<Record<string, Narrative | "loading" | "error">>({});

  const scenario = SCENARIOS.find((s) => s.id === scenarioId) ?? SCENARIOS[0];
  const week = scenario.week;
  const persona = scenario.persona;
  const sku = "sku" in scenario ? scenario.sku : undefined;

  useEffect(() => { api.personas().then(setPersonas).catch(() => {}); }, []);

  useEffect(() => {
    let live = true;
    setLoading(true);
    setActionsLoading(true);
    setError(null);
    setExpandedCause(null);
    setCompareOpen(false);
    setCompareData({});
    setInsight(null); setNarrative(null); setActions(null); setAttribution(null); setSplit(null);

    // The story, evidence and confidence sections only need these three — fetch
    // them as their own group so the page can render the instant they're back,
    // rather than waiting on Actions too. On a cold serverless container any one
    // of the five calls below can be the unlucky one that eats a 10-20s Python
    // cold start; blocking the whole page on the slowest of five reads as "stuck
    // loading" even when four of them answered in under a second.
    Promise.all([
      api.insight(week, persona, sku),
      api.narrative(week, persona, sku),
      api.attribution(week, persona, sku),
    ])
      .then(([i, n, at]) => {
        if (!live) return;
        setInsight(i); setNarrative(n); setAttribution(at);
      })
      .catch((e) => live && setError(e.message))
      .finally(() => live && setLoading(false));

    // Actions and the processing split load independently — their own section
    // shows a local loading state instead of holding up everything above it.
    Promise.all([
      api.actions(week, persona, sku),
      api.split().catch(() => null),
    ])
      .then(([a, sp]) => {
        if (!live) return;
        setActions(a); setSplit(sp);
      })
      .catch(() => {})
      .finally(() => live && setActionsLoading(false));

    return () => { live = false; };
  }, [scenarioId]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActiveSection(visible[0].target.id);
      },
      { rootMargin: "-20% 0px -70% 0px" }
    );
    SECTIONS.forEach((s) => {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [insight]);

  const cur = insight?.currency ?? "GBP";
  const band = insight?.confidence.band ?? "qualified";
  const isNeg = (insight?.gap ?? 0) < 0;

  const toggleCompare = () => {
    const opening = !compareOpen;
    setCompareOpen(opening);
    if (opening) {
      personas.forEach((p) => {
        if (compareData[p.id]) return;
        setCompareData((d) => ({ ...d, [p.id]: "loading" }));
        api.narrative(week, p.id, sku)
          .then((n) => setCompareData((d) => ({ ...d, [p.id]: n })))
          .catch(() => setCompareData((d) => ({ ...d, [p.id]: "error" })));
      });
    }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-eyebrow">Decision workspace</div>
        <h1 className="page-title">Investigate</h1>
        <p className="page-sub">
          One movement, followed end to end — from raw evidence to a narrative you can act on. Pick a scenario to see how the engine handles it.
        </p>
      </div>

      <div className="scenario-grid">
        {SCENARIOS.map((s, i) => (
          <button
            key={s.id}
            className={`scenario-card reveal${scenarioId === s.id ? " active" : ""}`}
            style={{ ["--i" as string]: i }}
            onClick={() => setScenarioId(s.id)}
          >
            <span className="scenario-card-icon">{s.icon}</span>
            <div className="scenario-card-title">{s.title}</div>
            <div className="scenario-card-sub">{s.sub}</div>
          </button>
        ))}
      </div>

      {loading && <SkeletonInvestigate />}
      {error && <div className="error-banner"><AlertTriangle size={16} /> {error}</div>}

      {insight && narrative && !loading && (
        <div className="investigate-layout">
          <nav className="investigate-rail">
            {SECTIONS.map((s, i) => {
              const Icon = s.icon;
              return (
                <a key={s.id} href={`#${s.id}`} className={`rail-link${activeSection === s.id ? " active" : ""}`}>
                  <span className="rail-num">{String(i + 1).padStart(2, "0")}</span>
                  <Icon size={14} /> {s.label}
                </a>
              );
            })}
          </nav>

          <div className="investigate-main">
            {/* ---- 1. The Story ---- */}
            <section id="story" className="investigate-section">
              <div className="hero-band">
                <span className="hero-number" style={{ color: isNeg ? "var(--neg)" : "var(--pos)" }}>
                  {fmt.money(insight.gap, cur)}
                </span>
                <span className="hero-sub">
                  {insight.expected !== null ? `vs expected ${fmt.moneyRaw(insight.expected)} · ` : "no expectation established · "}week {week}
                </span>
                <span className={`badge ${BAND_BADGE[band]}`} style={{ marginLeft: "auto" }}>
                  {band === "confident" ? <CheckCircle2 size={12} /> : band === "abstain" ? <OctagonAlert size={12} /> : <AlertTriangle size={12} />}
                  {band}
                </span>
              </div>
              <p className="note" style={{ marginBottom: 8 }}>{scenario.desc}</p>
              <p className="note" style={{ marginBottom: 20, display: "flex", alignItems: "center", gap: 6 }}>
                <Users size={12} /> Viewing as <strong style={{ color: "var(--ink-2)" }}>{insight.entitlement.persona}</strong>
                <span style={{ color: "var(--muted)" }}>— fixed by this scenario, not switchable here (pick a different scenario above to change it)</span>
              </p>

              {insight.entitlement.masked_columns.length > 0 && (
                <div style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
                  background: "var(--brand-subtle)", border: `1px solid color-mix(in srgb, var(--brand) 25%, transparent)`,
                  borderRadius: "var(--radius-sm)", marginBottom: 20, fontSize: 12.5, color: "var(--ink-2)",
                }}>
                  <Lock size={13} style={{ color: "var(--brand-text)", flexShrink: 0 }} />
                  <span><strong style={{ color: "var(--brand-text)" }}>{insight.entitlement.persona}</strong> — regions {insight.entitlement.regions.join(", ")} ·
                  {" "}{insight.entitlement.masked_columns.length} field{insight.entitlement.masked_columns.length > 1 ? "s" : ""} masked ({insight.entitlement.masked_columns.join(", ")})</span>
                </div>
              )}

              {band === "abstain" ? (
                <div className="abstain-pivot">
                  <OctagonAlert size={36} style={{ color: "var(--abstain)", marginBottom: 16 }} />
                  <div style={{ fontSize: 17, fontWeight: 700, color: "var(--abstain)", marginBottom: 10 }}>The engine is declining to narrate this one</div>
                  <p style={{ fontSize: 14.5, color: "var(--ink-2)", maxWidth: 520, margin: "0 auto 20px", lineHeight: 1.7 }}>
                    {insight.confidence.action}
                  </p>
                  {insight.would_raise_confidence.length > 0 && (
                    <div style={{ textAlign: "left", maxWidth: 420, margin: "0 auto" }}>
                      <div className="section-label">What would change that</div>
                      <ul className="clean-list">
                        {insight.would_raise_confidence.map((m) => <li key={m}>{m}</li>)}
                      </ul>
                    </div>
                  )}
                </div>
              ) : (
                <div className="prose">
                  {narrative.text.split("\n\n").map((para, i) => <p key={i}>{para}</p>)}
                </div>
              )}

              {insight.would_raise_confidence.length > 0 && band !== "abstain" && (
                <div style={{ marginTop: 20, padding: 16, background: "var(--warning-bg)", border: `1px solid color-mix(in srgb, var(--warning) 25%, transparent)`, borderRadius: "var(--radius-sm)" }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--warning)", marginBottom: 8, display: "flex", alignItems: "center", gap: 6 }}>
                    <HelpCircle size={14} /> What would raise confidence further
                  </div>
                  <ul style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "var(--ink-2)", lineHeight: 1.6 }}>
                    {insight.would_raise_confidence.map((m) => <li key={m}>{m}</li>)}
                  </ul>
                </div>
              )}

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 24, paddingTop: 16, borderTop: "1px solid var(--hairline)" }}>
                {narrative.llm_called ? (
                  <span className="pill">
                    <span className="dot" style={{ background: narrative.guard.passed ? "var(--good)" : "var(--critical)" }} />
                    {narrative.guard.figures_checked} figures verified against evidence
                  </span>
                ) : (
                  <span className="pill" title="No LLM output was produced, so there was nothing for the numeric guard to check.">
                    <span className="dot" style={{ background: "var(--muted)" }} />
                    Guard not applicable — no LLM output to verify
                  </span>
                )}
                {narrative.guard.drafts_rejected > 0 && (
                  <span className="pill" style={{ color: "var(--warning)" }}>
                    <ShieldAlert size={12} /> {narrative.guard.drafts_rejected} draft{narrative.guard.drafts_rejected > 1 ? "s" : ""} rejected by the guard
                  </span>
                )}
                <span className="pill"><Bot size={12} /> {narrative.llm_called ? narrative.source : "Deterministic — LLM not called"}</span>
              </div>

              {band !== "abstain" && personas.length > 1 && (
                <div style={{ marginTop: 20 }}>
                  <button className="btn btn-ghost btn-sm" onClick={toggleCompare} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <Users size={13} /> See how this reads for other personas
                    {compareOpen ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
                  </button>
                  {compareOpen && (
                    <div className="grid grid-3" style={{ gap: 12, marginTop: 14 }}>
                      {personas.map((p) => {
                        const d = compareData[p.id];
                        return (
                          <div key={p.id} className="card" style={{ padding: 16, background: "var(--surface-2)" }}>
                            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
                              <span style={{ fontSize: 12.5, fontWeight: 700, color: "var(--ink)" }}>{p.label}</span>
                              {d && d !== "loading" && d !== "error" && (
                                <span className={`badge ${BAND_BADGE[d.band]}`} style={{ fontSize: 10 }}>{d.band}</span>
                              )}
                            </div>
                            {!d || d === "loading" ? (
                              <div className="note">Loading…</div>
                            ) : d === "error" ? (
                              <div className="note">Could not load.</div>
                            ) : d.band === "abstain" ? (
                              <div className="note" style={{ color: "var(--abstain)" }}>Abstains for this persona — insufficient evidence in scope.</div>
                            ) : (
                              <div style={{ fontSize: 12.5, color: "var(--ink-2)", lineHeight: 1.6 }}>
                                {d.text.split("\n\n")[0].slice(0, 220)}{d.text.length > 220 ? "…" : ""}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 20 }}>
                <span className="note">Did this help you make a decision?</span>
                <InlineFeedback week={week} persona={persona} kpi={insight.kpi} confidence={insight.confidence.score} impact={insight.gap ?? undefined} />
              </div>
            </section>

            {/* ---- 2. Evidence ---- */}
            <section id="evidence" className="investigate-section">
              <div className="section-label" style={{ marginBottom: 4 }}>02 — Evidence</div>
              <h2 style={{ fontSize: 21, fontWeight: 700, color: "var(--ink)", marginBottom: 6 }}>Where the number comes from</h2>
              <p className="note" style={{ marginBottom: 24 }}>
                Expected → Actual, decomposed by exact arithmetic where possible. Nothing here is estimated by the model.
              </p>

              {insight.expected !== null && insight.actual !== null && (
                <div className="card" style={{ marginBottom: 20 }}>
                  <Bridge expected={insight.expected} actual={insight.actual} causes={insight.causes} currency={cur}
                    onSelect={(c) => setExpandedCause((cur) => cur === c.factor ? null : c.factor)} />
                </div>
              )}

              <div className="cause-list">
                {insight.causes.map((c) => {
                  const open = expandedCause === c.factor;
                  return (
                    <div key={c.factor}>
                      <button className={`cause-row${open ? " expanded" : ""}`} onClick={() => setExpandedCause(open ? null : c.factor)}>
                        <span className="cause-indicator" style={{ background: c.amount < 0 ? "var(--neg)" : "var(--pos)", opacity: c.status === "unattributed" ? 0.3 : 1 }} />
                        <span className="cause-info">
                          <span className="cause-name">{c.label}</span>
                          <span className="cause-meta">Rung {c.rung} · {c.status}{c.owner ? ` · ${c.owner.replace(/_/g, " ")}` : ""}</span>
                        </span>
                        <span className="cause-amount" style={{ color: c.amount < 0 ? "var(--neg)" : "var(--pos)" }}>
                          {fmt.money(c.amount, "")}
                        </span>
                      </button>
                      {open && (
                        <div className="evidence-panel">
                          <dl className="kv-grid" style={{ marginBottom: 16, gridTemplateColumns: "140px 1fr" }}>
                            <dt>Coverage credit</dt><dd>{c.credit.toFixed(3)}</dd>
                            <dt>Instrumented drivers</dt><dd>{c.drivers.length ? c.drivers.join(", ") : "none instrumented"}</dd>
                            <dt>Scope</dt>
                            <dd>{c.scope ? Object.entries(c.scope).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join("/") : v}`).join(", ") : "portfolio"}</dd>
                          </dl>
                          <div className="section-label">Evidence object</div>
                          <div className="evidence-block" style={{ marginBottom: 16 }}>{c.evidence}</div>
                          <div className="note" style={{ marginBottom: 16 }}>{RUNG_METHODS[c.rung] ?? "—"}</div>
                          <InlineFeedback week={week} persona={persona} driver={c.factor} confidence={insight.confidence.score} impact={c.amount} />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {attribution && attribution.path.length > 0 && (
                <div style={{ marginTop: 14, padding: "10px 12px", display: "flex", alignItems: "center", gap: 8, background: "var(--surface-2)", borderRadius: "var(--radius-sm)", fontSize: 12, color: "var(--ink-2)" }}>
                  <MapPin size={13} style={{ flexShrink: 0 }} />
                  <span>Drill path: <strong>{attribution.path.map((s) => `${s.dimension}=${s.chosen}`).join(" → ")}</strong>
                  <span style={{ color: "var(--muted)" }}> · ranked by surprise, not size</span></span>
                </div>
              )}

              {insight.contradictions.length > 0 && (
                <div className="card" style={{ marginTop: 20, border: `1px solid color-mix(in srgb, var(--warning) 30%, transparent)`, background: "var(--warning-bg)" }}>
                  <div className="card-title" style={{ color: "var(--warning)", marginBottom: 10 }}><AlertTriangle size={16} /> Contradictory Evidence Detected</div>
                  <ul className="clean-list">{insight.contradictions.map((c) => <li key={c} style={{ color: "var(--ink-2)" }}>{c}</li>)}</ul>
                </div>
              )}

              {insight.no_counterfactual.length > 0 && (
                <div className="card" style={{ marginTop: 20 }}>
                  <div className="card-title" style={{ marginBottom: 10 }}><Telescope size={16} /> Uninstrumented Drivers</div>
                  <ul className="clean-list">{insight.no_counterfactual.map((s) => <li key={s}>{s}</li>)}</ul>
                </div>
              )}
            </section>

            {/* ---- 3. Confidence ---- */}
            <section id="confidence" className="investigate-section">
              <div className="section-label" style={{ marginBottom: 4 }}>03 — Confidence</div>
              <h2 style={{ fontSize: 21, fontWeight: 700, color: "var(--ink)", marginBottom: 6 }}>How sure the engine is, and why</h2>
              <p className="note" style={{ marginBottom: 24 }}>
                Coverage counts only what's tied to a named cause — the rest is the honest gap between what happened and what we can explain.
              </p>
              <div className="grid grid-2">
                <div className="card">
                  <div className="card-header">
                    <div className="card-title">Confidence components</div>
                    <span className={`badge ${BAND_BADGE[band]}`}>{band}</span>
                  </div>
                  <ConfidenceBars components={insight.confidence.components} weights={WEIGHTS} />
                </div>
                {split && (
                  <div className="card">
                    <div className="card-title" style={{ marginBottom: 4 }}>Deterministic vs LLM</div>
                    <div className="card-sub" style={{ marginBottom: 18 }}>Measured cold, not on cached data.</div>
                    <Pipeline split={split} />
                  </div>
                )}
              </div>
            </section>

            {/* ---- 4. Actions ---- */}
            <section id="actions" className="investigate-section">
              <div className="section-label" style={{ marginBottom: 4 }}>04 — Next Steps</div>
              <h2 style={{ fontSize: 21, fontWeight: 700, color: "var(--ink)", marginBottom: 6 }}>What to actually do about it</h2>
              <p className="note" style={{ marginBottom: 24 }}>
                Driver → lever → action → expected impact → owner → confidence → monitoring plan. Every impact number is computed from attribution, never written by the model.
              </p>
              {actionsLoading ? (
                <Loader text="Computing recommended actions..." />
              ) : actions && actions.recommendations.length > 0 ? (
                <div className="grid" style={{ gap: 14 }}>
                  {actions.recommendations.map((r) => (
                    <RecCard key={r.driver} rec={r} week={week} persona={persona} />
                  ))}
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-state-title">No recommendations</div>
                  <div className="empty-state-sub">Engine abstained or gap is below the £25k action threshold</div>
                </div>
              )}
            </section>
          </div>
        </div>
      )}
    </div>
  );
}
