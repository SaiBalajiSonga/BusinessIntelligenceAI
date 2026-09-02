import { useEffect, useState } from "react";
import { api, peek } from "../api";
import { BarChart3, Database, Users, Ruler, AlertTriangle, Lock } from "lucide-react";
import type { Contract, Freshness } from "../types";

const TAB_ICON: Record<string, typeof BarChart3> = {
  kpis: BarChart3, sources: Database, personas: Users, confidence: Ruler,
};

export default function Governance() {
  // The contract is a static document for a given deploy, so a revisit should
  // never wait on it again.
  const [contract, setContract] = useState<Contract | null>(() => peek.contract() ?? null);
  const [freshness, setFreshness] = useState<Freshness[]>(() => peek.freshness() ?? []);
  const [loading, setLoading] = useState(() => !peek.contract());
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"kpis" | "sources" | "personas" | "confidence">("kpis");

  useEffect(() => {
    Promise.all([api.contract(), api.freshness()])
      .then(([c, f]) => { setContract(c); setFreshness(f); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div className="loading-screen"><div className="spinner" /><div className="loading-text">Loading semantic contract…</div></div>
  );
  if (error) return <div className="error-banner"><AlertTriangle size={16} /> {error}</div>;
  if (!contract) return null;

  const kpis = Object.entries(contract.kpis ?? {});
  const sources = Object.entries(contract.sources ?? {});
  const personas = Object.entries(contract.personas as Record<string, { label: string; regions: string[]; masked_columns: string[] }> ?? {});
  const conf = contract.confidence as { weights: Record<string, number>; bands: Record<string, number> } | null;

  const UNIT_BADGE: Record<string, string> = {
    currency: "badge-pos",
    ratio: "badge-neutral",
    count: "badge-neutral",
  };

  const TIER_STYLE: Record<number, React.CSSProperties> = {
    1: { background: "var(--brand-subtle)", color: "var(--brand-text)" },
    2: { background: "var(--surface-3)", color: "var(--ink-2)" },
    3: { background: "var(--surface-2)", color: "var(--muted)" },
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-eyebrow">System of record</div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
          <h1 className="page-title">Governance</h1>
          <span className="badge badge-neutral" style={{ fontSize: 11 }}>
            v{contract.version} · as of {contract.as_of}
          </span>
          <span className="badge badge-neutral" style={{ fontSize: 11 }}>
            {contract.currency}
          </span>
        </div>
        <p className="page-sub">
          KPI semantic contract · Source lineage · Entitlement matrix · Confidence architecture
        </p>
      </div>

      {/* Tab bar */}
      <div className="seg" style={{ marginBottom: 20, display: "inline-flex" }}>
        {(["kpis", "sources", "personas", "confidence"] as const).map((tab) => {
          const TabIcon = TAB_ICON[tab];
          return (
            <button
              key={tab}
              aria-pressed={activeTab === tab}
              onClick={() => setActiveTab(tab)}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <TabIcon size={13} /> {tab === "kpis" ? "KPIs" : tab[0].toUpperCase() + tab.slice(1)}
            </button>
          );
        })}
      </div>

      {/* KPIs Tab */}
      {activeTab === "kpis" && (
        <div>
          <div className="card">
            <div className="card-header">
              <div>
                <div className="card-title">KPI Semantic Contract</div>
                <div className="card-sub">
                  {kpis.length} KPIs · Definitions, calculations, materiality thresholds, and lineage.
                  Everything the engine needs to compute and explain a movement — no business logic in Python.
                </div>
              </div>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>KPI</th>
                  <th>Tier</th>
                  <th>Unit</th>
                  <th>Min Δ</th>
                  <th>Min Z</th>
                  <th>Lineage</th>
                  <th>Restricted</th>
                </tr>
              </thead>
              <tbody>
                {kpis.map(([id, kpi]) => (
                  <tr key={id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{kpi.label}</div>
                      <div style={{ fontSize: 11, color: "var(--muted)", fontFamily: "monospace" }}>{id}</div>
                    </td>
                    <td>
                      <span style={{
                        fontSize: 11, fontWeight: 600, padding: "2px 6px", borderRadius: 4,
                        ...(TIER_STYLE[kpi.tier] ?? {}),
                      }}>
                        Tier {kpi.tier}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${UNIT_BADGE[kpi.unit] ?? "badge-neutral"}`}>
                        {kpi.unit}
                      </span>
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                      {kpi.materiality?.min_abs_delta?.toLocaleString("en-GB") ?? "—"}
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                      {kpi.materiality?.min_z ?? "—"}
                    </td>
                    <td style={{ fontSize: 12 }}>
                      {kpi.lineage?.join(", ") ?? "—"}
                    </td>
                    <td>
                      {kpi.restricted && (
                        <span className="badge badge-neg"><Lock size={10} /> restricted</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sources Tab */}
      {activeTab === "sources" && (
        <div className="grid grid-2" style={{ gap: 16 }}>
          {sources.map(([id, src]) => {
            const f = freshness.find((x) => x.source === id);
            return (
              <div key={id} className="card">
                <div className="card-header">
                  <div>
                    <div className="card-title">{id}</div>
                    <div style={{ fontFamily: "monospace", fontSize: 11, color: "var(--muted)", marginTop: 2 }}>
                      {src.lineage}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 6, flexDirection: "column", alignItems: "flex-end" }}>
                    <span className={`badge badge-${src.governance === "governed" ? "confident" : "qualified"}`}>
                      {src.governance}
                    </span>
                    {f && (
                      <span className={`badge badge-${f.status === "fresh" ? "fresh" : "stale"}`}>
                        {f.status}
                      </span>
                    )}
                  </div>
                </div>
                <dl className="kv-grid" style={{ fontSize: 12 }}>
                  <dt>Grain</dt>
                  <dd style={{ fontFamily: "monospace", fontSize: 11 }}>
                    [{src.native_grain?.join(", ")}]
                  </dd>
                  <dt>Cadence</dt>
                  <dd>{src.refresh_cadence_hours}h</dd>
                  <dt>SLA</dt>
                  <dd>{src.sla_hours}h</dd>
                  {src.known_lag_days && (
                    <>
                      <dt>Known lag</dt>
                      <dd>{src.known_lag_days}d (by design)</dd>
                    </>
                  )}
                  {f && (
                    <>
                      <dt>Current lag</dt>
                      <dd style={{ color: f.status === "stale" ? "var(--warning)" : "var(--good)" }}>
                        {f.lag_hours}h
                      </dd>
                      <dt>Freshness score</dt>
                      <dd>{(f.freshness_score * 100).toFixed(0)}%</dd>
                    </>
                  )}
                </dl>
                <div style={{
                  marginTop: 12, padding: "8px 10px",
                  background: "var(--surface-2)", borderRadius: "var(--radius-sm)",
                  fontSize: 11, color: "var(--muted)", fontFamily: "monospace",
                }}>
                  {src.path}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Personas Tab */}
      {activeTab === "personas" && (
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <div>
                <div className="card-title">Entitlement Matrix</div>
                <div className="card-sub">
                  Row filters are applied in SQL before any analysis — not as post-hoc text masking.
                </div>
              </div>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Persona</th>
                  <th>Regions Visible</th>
                  <th>Masked Columns</th>
                  <th>Max Detail</th>
                </tr>
              </thead>
              <tbody>
                {personas.map(([id, p]) => (
                  <tr key={id}>
                    <td>
                      <div style={{ fontWeight: 500 }}>{p.label}</div>
                      <div style={{ fontSize: 11, color: "var(--muted)", fontFamily: "monospace" }}>{id}</div>
                    </td>
                    <td>
                      <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                        {p.regions?.map((r) => (
                          <span key={r} className="tag" style={{ fontSize: 10 }}>{r}</span>
                        ))}
                      </div>
                    </td>
                    <td>
                      {p.masked_columns?.length > 0 ? (
                        <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                          {p.masked_columns.map((c) => (
                            <span key={c} className="badge badge-neg" style={{ fontSize: 10 }}><Lock size={9} /> {c}</span>
                          ))}
                        </div>
                      ) : (
                        <span className="badge badge-confident">Full access</span>
                      )}
                    </td>
                    <td style={{ fontFamily: "monospace", fontSize: 12 }}>
                      {(p as Record<string, unknown>).max_detail as string ?? "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{
            padding: "14px 18px",
            background: "var(--brand-subtle)",
            border: "1px solid var(--brand)",
            borderRadius: "var(--radius)",
            fontSize: 13,
            color: "var(--ink-2)",
            display: "flex", alignItems: "flex-start", gap: 10,
          }}>
            <Lock size={14} style={{ color: "var(--brand-text)", marginTop: 2, flexShrink: 0 }} />
            <span><strong style={{ color: "var(--ink)" }}>How entitlements are enforced:</strong>{" "}
            Each persona's region list is injected as a SQL <code>WHERE region IN (...)</code> clause before the first
            JOIN. The analysis never sees rows it shouldn't. Masked columns are excluded from the SELECT list.
            There is no post-hoc text filtering.</span>
          </div>
        </div>
      )}

      {/* Confidence Tab */}
      {activeTab === "confidence" && conf && (
        <div className="grid grid-2" style={{ gap: 16 }}>
          <div className="card">
            <div className="card-title" style={{ marginBottom: 14 }}>Confidence Component Weights</div>
            <div className="conf-bars">
              {Object.entries(conf.weights).map(([k, w]) => {
                const isNeg = w < 0;
                const wide = Math.abs(w) * 100;
                return (
                  <div key={k} className="conf-bar-row">
                    <span className="conf-bar-label" style={{ textTransform: "capitalize" }}>
                      {k.replace(/_/g, " ")}
                    </span>
                    <div className="conf-bar-track">
                      <div
                        className="conf-bar-fill"
                        style={{
                          width: `${wide}%`,
                          left: isNeg ? `${50 - wide / 2}%` : "0",
                          background: isNeg ? "var(--neg)" : "var(--pos)",
                        }}
                      />
                    </div>
                    <span className="conf-bar-val">{w > 0 ? "+" : ""}{w.toFixed(2)}</span>
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <div className="card-title" style={{ marginBottom: 14 }}>Confidence Bands</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {Object.entries(conf.bands).map(([band, threshold]) => (
                <div key={band} style={{
                  padding: "14px 16px",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border)",
                  background: "var(--surface-2)",
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                    <span className={`badge badge-${band}`} style={{ textTransform: "capitalize" }}>
                      {band}
                    </span>
                    <span style={{ fontFamily: "monospace", fontSize: 13, fontWeight: 600 }}>
                      ≥ {threshold}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)" }}>
                    {band === "confident"
                      ? "Engine narrates — LLM is called."
                      : band === "qualified"
                      ? "Engine narrates with caveats and alternative hypotheses."
                      : "Engine abstains — LLM is NOT called."}
                  </div>
                </div>
              ))}
              <div style={{
                padding: "14px 16px",
                borderRadius: "var(--radius-sm)",
                border: `1px solid color-mix(in srgb, var(--abstain) 30%, transparent)`,
                background: "var(--abstain-bg)",
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                  <span className="badge badge-abstain">abstain</span>
                  <span style={{ fontFamily: "monospace", fontSize: 13, fontWeight: 600 }}>
                    &lt; {Math.min(...Object.values(conf.bands))}
                  </span>
                </div>
                <div style={{ fontSize: 12, color: "var(--muted)" }}>
                  Engine refuses to narrate. Lists what data would raise confidence instead.
                  LLM is never called. Cost: zero.
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
