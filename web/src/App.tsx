import { useEffect, useState } from "react";
import { api, fmt } from "./api";
import { Bridge, ConfidenceBars, SplitBar } from "./charts";
import type {
  Actions, Attribution, Cause, Freshness, Insight, Narrative, Persona, Split, Telemetry,
} from "./types";

const WEIGHTS: Record<string, number> = {
  coverage: 0.45, freshness: 0.15, history_depth: 0.15,
  method_strength: 0.15, contradiction: -0.2,
};

const BAND_COLOUR: Record<string, string> = {
  confident: "var(--good)", qualified: "var(--warning)", abstain: "var(--critical)",
};

export default function App() {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState("cfo");
  const [insight, setInsight] = useState<Insight | null>(null);
  const [narrative, setNarrative] = useState<Narrative | null>(null);
  const [actions, setActions] = useState<Actions | null>(null);
  const [attribution, setAttribution] = useState<Attribution | null>(null);
  const [freshness, setFreshness] = useState<Freshness[]>([]);
  const [split, setSplit] = useState<Split | null>(null);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [selected, setSelected] = useState<Cause | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);

  const week = insight?.week ?? "2026-W32";

  useEffect(() => {
    api.personas().then(setPersonas).catch((e) => setError(String(e.message)));
    api.freshness().then(setFreshness).catch(() => {});
    api.split().then(setSplit).catch(() => {});   // 503 while warming; harmless
  }, []);

  useEffect(() => {
    let live = true;
    setBusy(true);
    setError(null);
    Promise.all([
      api.insight(week, persona),
      api.narrative(week, persona),
      api.actions(week, persona),
      api.attribution(week, persona),
      api.telemetry(),
    ])
      .then(([i, n, a, at, t]) => {
        if (!live) return;
        setInsight(i); setNarrative(n); setActions(a); setAttribution(at); setTelemetry(t);
      })
      .catch((e) => live && setError(String(e.message)))
      .finally(() => live && setBusy(false));
    return () => { live = false; };
  }, [persona]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setSelected(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const cur = insight?.currency ?? "GBP";
  const band = insight?.confidence.band ?? "qualified";
  const activePersona = personas.find((p) => p.id === persona);

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          KPI Intelligence <span>{week} · Net Revenue</span>
        </div>
        <div className="spacer" />
        {freshness.map((f) => (
          <span className="pill" key={f.source} title={`${f.lag_hours}h old, ${f.sla_hours}h SLA`}>
            <span className="dot" style={{ background: f.status === "fresh" ? "var(--good)" : "var(--warning)" }} />
            {f.source} {f.status}
          </span>
        ))}
        <div className="seg" role="group" aria-label="Viewing as">
          {personas.map((p) => (
            <button key={p.id} aria-pressed={p.id === persona} onClick={() => setPersona(p.id)}>
              {p.label}
            </button>
          ))}
        </div>
      </header>

      {error && <p className="loading err">{error}</p>}
      {busy && !insight && <p className="loading">Computing — a cold assessment runs the full cascade…</p>}

      {insight && (
        <>
          <div className="tiles">
            <Tile label={`Gap vs expectation`} value={fmt.money(insight.gap, cur)}
                  foot={`expected ${fmt.abs(insight.expected ?? 0)}`} />
            <Tile label="Confidence" value={insight.confidence.score.toFixed(3)}
                  foot={insight.confidence.action} accent={BAND_COLOUR[band]} badge={band} />
            <Tile label="Coverage" value={fmt.pct(insight.confidence.coverage, 1)}
                  foot="share tied to a named cause" />
            <Tile label="Modelled recovery"
                  value={actions ? fmt.money(actions.modelled_recovery, cur) : "—"}
                  foot={actions?.modelled_recovery_share
                    ? `${fmt.pct(actions.modelled_recovery_share)} of the gap`
                    : ""} />
          </div>

          <div className="grid cols-2">
            <div className="grid" style={{ gap: 16 }}>
              <section className="card">
                <h2>What moved</h2>
                <p className="sub">
                  Expected to actual, decomposed. Entitlement applied as a row filter
                  before analysis — {activePersona?.regions.join(", ")}.
                </p>
                {insight.expected !== null && insight.actual !== null && (
                  <Bridge expected={insight.expected} actual={insight.actual}
                          causes={insight.causes} currency={cur} onSelect={setSelected} />
                )}
              </section>

              <section className="card">
                <h2>Causes</h2>
                <p className="sub">Ranked by contribution. Select one for its evidence.</p>
                {insight.causes.map((c) => (
                  <button className="cause" key={c.factor} onClick={() => setSelected(c)}>
                    <span className="bar" style={{
                      background: c.amount < 0 ? "var(--neg)" : "var(--pos)",
                      opacity: c.status === "unattributed" ? 0.35 : 1,
                    }} />
                    <span>
                      <span className="name">{c.label}</span>
                      <br />
                      <span className="meta">rung {c.rung} · {c.status}
                        {c.owner ? ` · ${c.owner.replace(/_/g, " ")}` : ""}</span>
                    </span>
                    <span className="amt" style={{ color: c.amount < 0 ? "var(--neg)" : "var(--pos)" }}>
                      {fmt.money(c.amount, "")}
                    </span>
                  </button>
                ))}
                {attribution && attribution.path.length > 0 && (
                  <p className="note" style={{ marginTop: 12 }}>
                    Drill located it at{" "}
                    <strong>{attribution.path.map((s) => `${s.dimension}=${s.chosen}`).join(" / ")}</strong>
                    {" "}— ranked by surprise, not size.
                  </p>
                )}
              </section>

              {actions && (
                <section className="card">
                  <h2>Recommended actions</h2>
                  <p className="sub">
                    Expected impact is computed from the attributed contribution, never written by the model.
                  </p>
                  {actions.recommendations.map((r) => (
                    <div className="action" key={r.driver}>
                      <div className="row">
                        <span className="lever">{r.lever}</span>
                        <span className="tag">{r.kind}</span>
                        <span className="impact" style={{ color: r.expected_impact ? "var(--pos)" : "var(--muted)" }}>
                          {r.expected_impact ? fmt.money(r.expected_impact, "") : "confidence"}
                        </span>
                      </div>
                      <p className="what">{r.action}</p>
                      <div className="who">
                        <span className="tag">{r.owner.replace(/_/g, " ")}</span>
                        <span className="tag">{r.horizon_weeks}w</span>
                        <span className="tag">conf {r.confidence.toFixed(2)}</span>
                      </div>
                      <ul className="plain" style={{ marginTop: 8 }}>
                        <li>{r.decision_rights}</li>
                        <li>Monitor {r.monitoring.metrics.join(", ")} — {r.monitoring.cadence},{" "}
                          {r.monitoring.horizon_days}d. {r.monitoring.guardrail}</li>
                        {r.assumptions.map((a) => <li key={a}>Assumes {a}</li>)}
                      </ul>
                    </div>
                  ))}
                </section>
              )}
            </div>

            <div className="grid" style={{ gap: 16, alignContent: "start" }}>
              {narrative && (
                <section className="card">
                  <h2>Narrative</h2>
                  <p className="sub">
                    {activePersona?.label}
                    {activePersona?.masked_columns.length
                      ? ` · ${activePersona.masked_columns.length} fields withheld` : ""}
                  </p>
                  <p className="prose">{narrative.text}</p>
                  <div style={{ marginTop: 14, display: "flex", gap: 7, flexWrap: "wrap" }}>
                    <span className="pill">
                      <span className="dot" style={{ background: narrative.guard.passed ? "var(--good)" : "var(--critical)" }} />
                      {narrative.guard.figures_checked} figures verified
                    </span>
                    {narrative.guard.drafts_rejected > 0 && (
                      <span className="pill">{narrative.guard.drafts_rejected} draft rejected</span>
                    )}
                    <span className="pill">{narrative.llm_called ? narrative.source : "LLM not called"}</span>
                  </div>
                  <p className="note" style={{ marginTop: 10 }}>
                    Every figure above was checked against the evidence object before display.
                  </p>
                </section>
              )}

              <section className="card">
                <h2>Confidence</h2>
                <p className="sub">
                  Weighted components. Coverage counts only what is tied to a named cause —
                  the decomposition itself explains 100% by construction.
                </p>
                <ConfidenceBars components={insight.confidence.components} weights={WEIGHTS} />
                {insight.would_raise_confidence.length > 0 && (
                  <>
                    <p className="sub" style={{ margin: "16px 0 8px" }}>What would raise it</p>
                    <ul className="plain">
                      {insight.would_raise_confidence.map((m) => <li key={m}>{m}</li>)}
                    </ul>
                  </>
                )}
              </section>

              {split && (
                <section className="card">
                  <h2>LLM vs deterministic</h2>
                  <p className="sub">Measured cold at warm-up, not on a warm cache.</p>
                  <SplitBar split={split} />
                  <p className="note" style={{ marginTop: 10 }}>{split.interpretation}</p>
                </section>
              )}

              {telemetry && (
                <section className="card">
                  <h2>Runtime cost</h2>
                  <p className="sub">{telemetry.llm.provider} · {telemetry.llm.model}</p>
                  <table className="data">
                    <tbody>
                      <Row k="Model calls" v={`${telemetry.llm.calls} (${telemetry.llm.cache_hits} cached)`} />
                      <Row k="Tokens in / out" v={`${telemetry.llm.input_tokens.toLocaleString()} / ${telemetry.llm.output_tokens.toLocaleString()}`} />
                      <Row k="Cost" v={`$${telemetry.llm.cost_usd.toFixed(4)}`} />
                      <Row k="Median latency" v={fmt.ms(telemetry.llm.p50_latency_ms)} />
                      <Row k="Analysis cache" v={`${fmt.pct(telemetry.analysis_cache.hit_rate, 0)} hit rate`} />
                    </tbody>
                  </table>
                  <p className="note" style={{ marginTop: 10 }}>
                    Cost at reference rates — the free tier charges nothing.
                  </p>
                </section>
              )}
            </div>
          </div>
        </>
      )}

      <div className="scrim" data-open={!!selected} onClick={() => setSelected(null)} />
      <aside className="drawer" data-open={!!selected} aria-hidden={!selected}
             aria-label="Evidence detail">
        {selected && (
          <>
            <header>
              <div style={{ flex: 1 }}>
                <h3>{selected.label}</h3>
                <p className="note" style={{ margin: "4px 0 0" }}>
                  {fmt.money(selected.amount, cur)} · rung {selected.rung}
                </p>
              </div>
              <button className="close" onClick={() => setSelected(null)} aria-label="Close">×</button>
            </header>
            <div className="body">
              <dl className="kv" style={{ marginBottom: 18 }}>
                <dt>Status</dt><dd>{selected.status}</dd>
                <dt>Credit to coverage</dt><dd>{selected.credit.toFixed(2)}</dd>
                <dt>Owner</dt><dd>{selected.owner?.replace(/_/g, " ") ?? "unassigned"}</dd>
                <dt>Drivers</dt>
                <dd>{selected.drivers.length ? selected.drivers.join(", ") : "none instrumented"}</dd>
                <dt>Scope</dt>
                <dd>{selected.scope ? Object.entries(selected.scope).map(([k, v]) =>
                  `${k}=${Array.isArray(v) ? v.join("/") : v}`).join(", ") : "portfolio"}</dd>
              </dl>

              <p className="sub" style={{ margin: "0 0 8px" }}>Evidence</p>
              <div className="evidence">{selected.evidence}</div>

              <p className="sub" style={{ margin: "18px 0 8px" }}>How this number was produced</p>
              <ul className="plain">
                <li>{RUNG_METHOD[selected.rung] ?? "—"}</li>
                {selected.status === "localised" && (
                  <li>Located by a control-group estimate; no instrumented driver names the cause.</li>
                )}
                {selected.status === "unattributed" && (
                  <li>No driver identified — this term counts zero toward coverage.</li>
                )}
              </ul>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}

const RUNG_METHOD: Record<number, string> = {
  1: "Rung 1 — LMDI over the revenue identity. Exact; contributions sum to the gap.",
  2: "Rung 2 — Bennet indicator splitting ASP into price and mix. Exact.",
  3: "Rung 3 — dimensional attribution ranked by Jensen-Shannon surprise. Exact.",
  4: "Rung 4 — difference-in-differences with two-way fixed effects. Carries assumptions.",
};

function Tile({ label, value, foot, accent, badge }: {
  label: string; value: string; foot?: string; accent?: string; badge?: string;
}) {
  return (
    <div className="tile">
      <div className="label">{label}</div>
      <div className="value" style={accent ? { color: accent } : undefined}>{value}</div>
      {badge && <span className="tag" style={{ marginTop: 6, display: "inline-block" }}>{badge}</span>}
      {foot && <div className="foot">{foot}</div>}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return <tr><td style={{ color: "var(--muted)" }}>{k}</td><td style={{ textAlign: "right" }}>{v}</td></tr>;
}
