import Loader from "../components/Loader";
import { useEffect, useState } from "react";
import { api, fmt } from "../api";
import type { Freshness, Movement, Telemetry } from "../types";

interface Props {
  week: string;
  persona: string;
}

export default function Overview({ week, persona }: Props) {
  const [movements, setMovements] = useState<Movement[]>([]);
  const [freshness, setFreshness] = useState<Freshness[]>([]);
  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      api.movements(week, persona),
      api.freshness(),
      api.telemetry(),
    ])
      .then(([m, f, t]) => {
        setMovements(m.movements ?? []);
        setFreshness(f);
        setTelemetry(t);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [week, persona]);

  if (loading) return (
    <Loader text="Computing KPI movements across all sources..." />
  );

  if (error) return (
    <div className="error-banner">⚠️ {error}</div>
  );

  const material = movements.filter((m) => m.material);
  const nonMaterial = movements.filter((m) => !m.material);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">KPI Overview</h1>
        <p className="page-sub">
          {week} · {movements.length} KPIs tracked · {material.length} material movement{material.length !== 1 ? "s" : ""} detected
        </p>
      </div>

      {/* Alert Banner */}
      {material.length > 0 && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          padding: "14px 18px",
          background: "var(--abstain-bg)",
          border: "1px solid rgba(239,68,68,.3)",
          borderRadius: "var(--radius)",
          marginBottom: 20,
        }}>
          <span style={{ fontSize: 20 }}>🚨</span>
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
                  ? `£${(Math.abs(m.actual) / 1e6).toFixed(2)}M`
                  : m.unit === "ratio"
                  ? `${(m.actual * 100).toFixed(1)}%`
                  : m.actual.toLocaleString("en-GB")}
              </div>
              <div className="kpi-tile-delta">
                <span className={isPos ? "delta-pos" : "delta-neg"}>
                  {isPos ? "▲" : "▼"} {Math.abs(pct * 100).toFixed(1)}%
                </span>
                <span style={{ color: "var(--muted)", fontSize: 11 }}>vs expected</span>
              </div>
              <div className="kpi-tile-foot">
                <span className="has-tooltip" data-tooltip="Z-score: Number of standard deviations away from the historical baseline">
                  Z = {m.z.toFixed(2)}
                </span> · {m.history_weeks}w history · {m.baseline_method}
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-2" style={{ marginTop: 20 }}>
        {/* Source Freshness */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Data Source Freshness</div>
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
                <div className="card-title">Runtime Economics</div>
                <div className="card-sub">{telemetry.llm.provider} · {telemetry.llm.model}</div>
              </div>
              <span className="badge badge-neutral">
                {(1 - telemetry.llm.calls / Math.max(telemetry.llm.calls + telemetry.analysis_cache.hits, 1) * 100).toFixed(0)}% cached
              </span>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              {[
                { label: "LLM Calls", value: String(telemetry.llm.calls), sub: `${telemetry.llm.cache_hits} cached` },
                { label: "Token Cost", value: `$${telemetry.llm.cost_usd.toFixed(4)}`, sub: "reference rate" },
                { label: "Tokens In/Out", value: `${(telemetry.llm.input_tokens/1000).toFixed(1)}k / ${(telemetry.llm.output_tokens/1000).toFixed(1)}k`, sub: "prompt / completion" },
                { label: "P50 Latency", value: fmt.ms(telemetry.llm.p50_latency_ms), sub: "LLM only", tooltip: "Median response time: 50% of requests are faster than this" },
                { label: "Analysis Cache", value: fmt.pct(telemetry.analysis_cache.hit_rate, 0), sub: "hit rate", tooltip: "Percentage of requests served instantly from memory without waking the LLM" },
                { label: "Cache Note", value: "7s cold", sub: "instant from cache" },
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
                  <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: "-0.02em", color: "var(--ink)", marginTop: 4 }}>{s.value}</div>
                  <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{s.sub}</div>
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
                <th>Z-score</th>
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
