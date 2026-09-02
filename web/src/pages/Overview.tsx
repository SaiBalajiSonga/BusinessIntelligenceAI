import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmt, peek } from "../api";
import { Pipeline } from "../charts";
import PersonaSwitcher from "../components/PersonaSwitcher";
import Sparkline from "../components/Sparkline";
import { SkeletonKpiGrid } from "../components/Skeleton";
import { AlertTriangle, TrendingUp, TrendingDown, Workflow, ArrowRight } from "lucide-react";
import type { Freshness, Movement, Persona, Telemetry, Split } from "../types";

interface Props {
  week: string;
  persona: string;
  personas: Persona[];
  onPersonaChange: (id: string) => void;
}

/** Sparkline histories already in cache, so the lines come back with the
 *  tiles on a revisit rather than redrawing from empty. */
function seededSeries(movements: Movement[] | undefined, persona: string, week: string): Record<string, number[]> {
  const out: Record<string, number[]> = {};
  (movements ?? []).forEach((m) => {
    const s = peek.series(m.kpi, persona, week, 26);
    if (s) out[m.kpi] = s.points.map((p) => p.value);
  });
  return out;
}

/** Formats a KPI value for its declared unit. */
function kpiValue(m: Movement): string {
  if (m.unit === "currency") return fmt.compact(m.actual);
  if (m.unit === "ratio") return `${(m.actual * 100).toFixed(1)}%`;
  return m.actual.toLocaleString("en-GB", { maximumFractionDigits: 0 });
}

export default function Overview({ week, persona, personas, onPersonaChange }: Props) {
  // Seed from cache so returning to a page you have already opened renders
  // immediately. Without this the page tore itself down to a skeleton and
  // re-fetched numbers that, for a fixed week, cannot have changed.
  const cached = peek.movements(week, persona);

  const [movements, setMovements] = useState<Movement[]>(cached?.movements ?? []);
  const [freshness, setFreshness] = useState<Freshness[]>(() => peek.freshness() ?? []);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(() => peek.telemetry() ?? null);
  const [split, setSplit] = useState<Split | null>(() => peek.split() ?? null);
  const [series, setSeries] = useState<Record<string, number[]>>(() => seededSeries(cached?.movements, persona, week));
  const [loading, setLoading] = useState(!cached);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const known = peek.movements(week, persona);
    // Only blank the page when there is genuinely nothing to show for this
    // (week, persona); a revisit keeps the last view on screen while it
    // revalidates behind it.
    setLoading(!known);
    setError(null);
    if (known) {
      setMovements(known.movements ?? []);
      setSeries(seededSeries(known.movements, persona, week));
    }
    Promise.all([
      api.movements(week, persona),
      api.freshness(),
      api.telemetry(),
      api.split().catch(() => null),
    ])
      .then(([m, f, t, sp]) => {
        if (!live) return;
        const found = m.movements ?? [];
        setMovements(found);
        setFreshness(f);
        setTelemetry(t);
        setSplit(sp);

        // Histories load per-KPI after the tiles are already on screen, so a
        // slow series never delays the numbers themselves. Each card draws its
        // line as it arrives; one that fails just renders without a line.
        found.forEach((mv) => {
          api.series(mv.kpi, persona, week, 26)
            .then((s) => {
              if (!live) return;
              setSeries((prev) => ({ ...prev, [mv.kpi]: s.points.map((p) => p.value) }));
            })
            .catch(() => {});
        });
      })
      .catch((e) => live && setError(e.message))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [week, persona]);

  if (loading) return <SkeletonKpiGrid count={6} />;

  if (error) return (
    <div className="error-banner"><AlertTriangle size={16} /> {error}</div>
  );

  const material = movements.filter((m) => m.material);
  const nonMaterial = movements.filter((m) => !m.material);

  // The hero is the most consequential movement, not a hardcoded KPI: the
  // largest material one by money, falling back to the first tracked KPI so
  // the layout still holds on a quiet week.
  const hero =
    [...material].sort((a, b) => Math.abs(b.impact_gbp ?? 0) - Math.abs(a.impact_gbp ?? 0))[0]
    ?? movements[0];
  const rest = movements.filter((m) => m.kpi !== hero?.kpi);

  return (
    <div>
      <div className="page-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24, flexWrap: "wrap" }}>
        <div>
          <div className="page-eyebrow">Focal week {week}</div>
          <h1 className="page-title">KPI Overview</h1>
          <p className="page-sub">
            {movements.length} KPIs tracked · {material.length} material movement{material.length !== 1 ? "s" : ""} detected
          </p>
        </div>
        <div>
          <div className="section-label" style={{ marginBottom: 8, textAlign: "right" }}>Viewing as</div>
          <PersonaSwitcher personas={personas} persona={persona} onPersonaChange={onPersonaChange} />
        </div>
      </div>

      {/* Signature hero: the actual measured engine pipeline for this run */}
      {split && (
        <div className="card" style={{ marginBottom: 20 }}>
          <div className="card-header" style={{ marginBottom: 18 }}>
            <div>
              <div className="card-title"><Workflow size={16} /> How This Answer Was Produced</div>
              <div className="card-sub">{split.interpretation}</div>
            </div>
          </div>
          <Pipeline split={split} />
        </div>
      )}

      {/* Alert Banner */}
      {material.length > 0 && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "14px 18px",
          background: "var(--abstain-bg)",
          border: `1px solid color-mix(in srgb, var(--abstain) 30%, transparent)`,
          borderRadius: "var(--radius)",
          marginBottom: 20,
        }}>
          <AlertTriangle size={18} style={{ color: "var(--abstain)", flexShrink: 0 }} />
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, color: "var(--abstain)" }}>
              {material.length} material movement{material.length > 1 ? "s" : ""} require attention
            </div>
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
              {material.map((m) => m.label).join(" · ")}
            </div>
          </div>
          {/* The rule that produced the alert, as a chip rather than text
              stranded at the far edge of a wide banner. */}
          <span className="pill" style={{ marginLeft: "auto", flexShrink: 0 }}>
            Clears both bars — Z &gt; 2.5 and £150k
          </span>
        </div>
      )}

      {/* KPI block: one hero, then a grid whose last row always fills. */}
      <div className="kpi-grid">
        {hero && <HeroKpi m={hero} points={series[hero.kpi]} />}
        {rest.map((m, i) => (
          <KpiCard key={m.kpi} m={m} points={series[m.kpi]} index={i + 1} />
        ))}
      </div>

      <div className="grid grid-2" style={{ marginTop: 20 }}>
        {/* Source Freshness */}
        <div className="card reveal" style={{ ["--i" as string]: 7 }}>
          <div className="card-header">
            <div>
              <div className="card-title">Data Quality & SLA Compliance</div>
              <div className="card-sub">SLA compliance across all ingestion pipelines</div>
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {freshness.map((f) => (
              <div key={f.source} style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "10px 14px",
                background: "var(--surface-2)",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border)",
              }}>
                <span
                  className="dot dot-pulse"
                  style={{ background: f.status === "fresh" ? "var(--good)" : "var(--warning)" }}
                />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: "var(--ink)" }}>
                    {f.source}
                    <span className="tag" style={{ marginLeft: 8, textTransform: "none" }}>
                      {f.governance}
                    </span>
                  </div>
                  <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 2 }}>
                    {f.lag_hours}h lag · {f.sla_hours}h SLA · as of {f.latest_data}
                  </div>
                </div>
                <span className={`badge badge-${f.status === "fresh" ? "fresh" : "stale"}`}>
                  {f.status}
                </span>
                <div style={{ textAlign: "right", minWidth: 48 }}>
                  <div style={{ fontSize: 15, fontWeight: 700, color: "var(--ink)" }}>
                    {(f.freshness_score * 100).toFixed(0)}%
                  </div>
                  <div style={{ fontSize: 10, color: "var(--muted)" }}>score</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Runtime Telemetry */}
        {telemetry && (
          <div className="card reveal" style={{ ["--i" as string]: 8 }}>
            <div className="card-header">
              <div>
                <div className="card-title">System Diagnostics (Admin)</div>
                <div className="card-sub">{telemetry.llm.provider} · {telemetry.llm.model}</div>
              </div>
              <span className="badge badge-neutral">
                {fmt.pct(telemetry.analysis_cache.hit_rate, 0)} cached
              </span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              {[
                { label: "LLM Calls", value: String(telemetry.llm.calls), sub: `${telemetry.llm.live_calls} live, ${telemetry.llm.cache_hits} cached` },
                { label: "Token Cost", value: `$${telemetry.llm.cost_usd.toFixed(4)}`, sub: "reference rate" },
                { label: "Tokens In/Out", value: `${(telemetry.llm.input_tokens/1000).toFixed(1)}k / ${(telemetry.llm.output_tokens/1000).toFixed(1)}k`, sub: "prompt / completion" },
                { label: "P50 Latency", value: fmt.ms(telemetry.llm.p50_latency_ms), sub: "LLM only", tooltip: "Median response time: 50% of requests are faster than this" },
                { label: "Analysis Cache", value: fmt.pct(telemetry.analysis_cache.hit_rate, 0), sub: `${telemetry.analysis_cache.hits} hits / ${telemetry.analysis_cache.misses} misses`, tooltip: "Percentage of requests served instantly from memory without waking the LLM" },
                { label: "Cache Behaviour", value: telemetry.analysis_cache.note, sub: "", prose: true },
              ].map((s) => (
                <div key={s.label} style={{
                  padding: "12px 14px",
                  background: "var(--surface-2)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border)",
                }}>
                  <div
                    style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}
                    className={s.tooltip ? "has-tooltip" : ""}
                    data-tooltip={s.tooltip}
                  >
                    {s.label}
                  </div>
                  <div style={s.prose
                    ? { fontSize: 12.5, lineHeight: 1.5, color: "var(--ink-2)", marginTop: 6 }
                    : { fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em", color: "var(--ink)", marginTop: 4 }
                  }>{s.value}</div>
                  {s.sub && <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{s.sub}</div>}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Non-material KPIs */}
      {nonMaterial.length > 0 && (
        <div className="card" style={{ marginTop: 16 }}>
          <div className="card-header">
            <div>
              <div className="card-title">Monitored — No Material Alert</div>
              <div className="card-sub">Below statistical or business materiality threshold</div>
            </div>
          </div>
          <table className="data-table">
            <thead>
              <tr>
                <th>KPI</th>
                <th>Actual</th>
                <th>Expected</th>
                <th>Delta</th>
                <th>Anomaly Score</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {nonMaterial.map((m) => (
                <tr key={m.kpi}>
                  <td>{m.label}</td>
                  <td style={{ fontFamily: "monospace" }}>
                    {m.unit === "ratio" ? `${(m.actual*100).toFixed(1)}%` : m.actual.toLocaleString("en-GB", { maximumFractionDigits: 0 })}
                  </td>
                  <td style={{ color: "var(--muted)", fontFamily: "monospace" }}>
                    {m.unit === "ratio" ? `${(m.expected*100).toFixed(1)}%` : m.expected.toLocaleString("en-GB", { maximumFractionDigits: 0 })}
                  </td>
                  <td style={{ color: m.delta >= 0 ? "var(--pos)" : "var(--neg)" }}>
                    {m.delta >= 0 ? "+" : ""}{(m.delta_pct * 100).toFixed(1)}%
                  </td>
                  <td style={{ fontFamily: "monospace" }}>{m.z.toFixed(2)}</td>
                  <td style={{ fontSize: 12, color: "var(--muted)" }}>{m.not_flagged_because.join("; ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** Shared delta line: direction, size, and what it is measured against. */
function DeltaLine({ m }: { m: Movement }) {
  const isPos = m.delta >= 0;
  return (
    <div className="kpi-card-delta">
      <span className={isPos ? "delta-pos" : "delta-neg"} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
        {isPos ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
        {Math.abs((m.delta_pct ?? 0) * 100).toFixed(1)}%
      </span>
      <span style={{ color: "var(--muted)", fontWeight: 500 }}>vs expected</span>
    </div>
  );
}

/**
 * The lead movement, given the space its consequence warrants.
 *
 * The sparkline carries the expectation as a dashed rule, so the gap the rest
 * of the page is about is visible here rather than only described.
 */
function HeroKpi({ m, points }: { m: Movement; points?: number[] }) {
  const tone = m.material ? "neg" : m.delta >= 0 ? "pos" : "neutral";
  return (
    <div className="kpi-hero reveal">
      <div className="kpi-hero-left">
        <div className="kpi-card-head" style={{ marginBottom: 2 }}>
          <span className="kpi-card-label">{m.label}</span>
          {m.material && (
            <span className="badge badge-neg has-tooltip"
              data-tooltip="Exceeds statistical (Z > 2.5) and business (GBP 150k) thresholds">
              material
            </span>
          )}
        </div>
        <div className="kpi-hero-value" style={{ color: m.material ? "var(--neg)" : "var(--ink)" }}>
          {kpiValue(m)}
        </div>
        <DeltaLine m={m} />
        <div className="kpi-card-meta" style={{ marginTop: 14 }}>
          Anomaly {m.z.toFixed(2)} · {m.history_weeks}w history · {m.baseline_method}
        </div>
        <Link to="/investigation" className="kpi-tile-investigate" style={{ marginTop: 16 }}>
          Investigate this <ArrowRight size={12} />
        </Link>
      </div>

      <div className="kpi-hero-spark">
        {points
          ? <Sparkline points={points} tone={tone} height={150} expected={m.expected} />
          : <div className="skeleton" style={{ width: "100%", height: 150, borderRadius: "var(--radius)" }} />}
      </div>
    </div>
  );
}

function KpiCard({ m, points, index }: { m: Movement; points?: number[]; index: number }) {
  const tone = m.material ? "neg" : m.delta >= 0 ? "pos" : "neutral";
  return (
    <div className={`kpi-card reveal${m.material ? " is-material" : ""}`} style={{ ["--i" as string]: index }}>
      <div className="kpi-card-head">
        <span className="kpi-card-label">{m.label}</span>
        {m.material && (
          <span className="badge badge-neg has-tooltip" style={{ marginLeft: "auto" }}
            data-tooltip="Exceeds statistical (Z > 2.5) and business (GBP 150k) thresholds">
            material
          </span>
        )}
      </div>

      <div className="kpi-card-value" style={{ color: m.material ? "var(--neg)" : "var(--ink)" }}>
        {kpiValue(m)}
      </div>
      <DeltaLine m={m} />
      <div className="kpi-card-meta">
        Anomaly {m.z.toFixed(2)} · {m.history_weeks}w history
      </div>

      <div className="kpi-card-spark">
        {points
          ? <Sparkline points={points} tone={tone} height={46} expected={m.expected} />
          : <div className="skeleton" style={{ height: "100%", borderRadius: 0 }} />}
      </div>
    </div>
  );
}
