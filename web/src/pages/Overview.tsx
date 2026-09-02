import Loader from "../components/Loader";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmt } from "../api";
import { Pipeline } from "../charts";
import PersonaSwitcher from "../components/PersonaSwitcher";
import { AlertTriangle, TrendingUp, TrendingDown, Workflow, ArrowRight } from "lucide-react";
import type { Freshness, Movement, Persona, Telemetry, Split } from "../types";

interface Props {
  week: string;
  persona: string;
  personas: Persona[];
  onPersonaChange: (id: string) => void;
}

export default function Overview({ week, persona, personas, onPersonaChange }: Props) {
  const [movements, setMovements] = useState<Movement[]>([]);
  const [freshness, setFreshness] = useState<Freshness[]>([]);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [split, setSplit] = useState<Split | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.movements(week, persona),
      api.freshness(),
      api.telemetry(),
      api.split().catch(() => null),
    ])
      .then(([m, f, t, sp]) => {
        setMovements(m.movements ?? []);
        setFreshness(f);
        setTelemetry(t);
        setSplit(sp);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [week, persona]);

  if (loading) return (
    <Loader text="Computing KPI movements across all sources..." />
  );

  if (error) return (
    <div className="error-banner"><AlertTriangle size={16} /> {error}</div>
  );

  const material = movements.filter((m) => m.material);
  const nonMaterial = movements.filter((m) => !m.material);

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
          <div style={{ marginLeft: "auto", fontSize: 12, color: "var(--muted)" }}>
            Both statistical (Z &gt; 2.5) and business (£150k) bars must clear
          </div>
        </div>
      )}

      {/* KPI Tiles */}
      <div className="tiles-grid">
        {movements.map((m) => {
          const pct = m.delta_pct ?? 0;
          const isPos = m.delta >= 0;
          return (
            <div key={m.kpi} className={`kpi-tile${m.material ? " material" : ""}`}>
              <div className="kpi-tile-label">
                {m.label}
                {m.material && (
                  <span 
                    className="badge badge-neg has-tooltip" 
                    style={{ marginLeft: 8 }}
                    data-tooltip="Exceeds statistical (Z > 2.5) and business (GBP 150k) thresholds"
                  >
                    material
                  </span>
                )}
              </div>
              <div className="kpi-tile-value" style={{ color: m.material ? "var(--neg)" : "var(--ink)" }}>
                {m.unit === "currency"
                  ? fmt.compact(m.actual)
                  : m.unit === "ratio"
                  ? `${(m.actual * 100).toFixed(1)}%`
                  : m.actual.toLocaleString("en-GB")}
              </div>
              <div className="kpi-tile-delta">
                <span className={isPos ? "delta-pos" : "delta-neg"} style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                  {isPos ? <TrendingUp size={14} /> : <TrendingDown size={14} />} {Math.abs(pct * 100).toFixed(1)}%
                </span>
                <span style={{ color: "var(--muted)", fontSize: 11 }}>vs expected</span>
              </div>

              <CompareBar actual={m.actual} expected={m.expected} isPos={isPos} />

              <div className="kpi-tile-foot">
                <span className="has-tooltip" data-tooltip="Anomaly Score: How unusual this movement is compared to historical patterns (Z-score)">
                  Anomaly: {m.z.toFixed(2)}
                </span> · {m.history_weeks}w history · {m.baseline_method}
              </div>
              {m.kpi === "net_revenue" && (
                <Link to="/investigation" className="kpi-tile-investigate">
                  Investigate this <ArrowRight size={12} />
                </Link>
              )}
            </div>
          );
        })}
      </div>

      <div className="grid grid-2" style={{ marginTop: 20 }}>
        {/* Source Freshness */}
        <div className="card">
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
          <div className="card">
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

/** Real actual-vs-expected comparison, no invented series — a bar growing from
 *  a fixed "expected" mark rather than a bare percentage, so a scan of the tile
 *  grid reads magnitude at a glance. */
function CompareBar({ actual, expected, isPos }: { actual: number; expected: number; isPos: boolean }) {
  if (!expected) return null;
  const ratio = actual / expected;
  const clamped = Math.max(0.5, Math.min(1.5, ratio));
  const width = ((clamped - 0.5) / 1.0) * 100;
  return (
    <div className="kpi-compare-track" title={`Actual ${fmt.abs(actual)} vs expected ${fmt.abs(expected)}`}>
      <div className="kpi-compare-marker" />
      <div className={`kpi-compare-fill ${isPos ? "pos" : "neg"}`} style={{ width: `${width}%` }} />
    </div>
  );
}
