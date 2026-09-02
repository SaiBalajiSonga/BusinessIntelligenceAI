import { useState } from "react";
import { api } from "../api";
import Loader from "../components/Loader";
import { Cloud, Search, Database, Server, Component, AlertTriangle, CheckCircle2 } from "lucide-react";

const CONNECTORS = [
  { id: "snowflake", name: "Snowflake", icon: <Cloud size={32} color="var(--brand)" />, desc: "Connect to your Snowflake Data Cloud" },
  { id: "bigquery", name: "Google BigQuery", icon: <Search size={32} color="#4285F4" />, desc: "Connect to your GCP Data Warehouse" },
  { id: "postgresql", name: "PostgreSQL", icon: <Database size={32} color="#336791" />, desc: "Connect to standard PostgreSQL databases" },
  { id: "redshift", name: "Amazon Redshift", icon: <Server size={32} color="#FF9900" />, desc: "Connect to your AWS Data Warehouse" },
  { id: "databricks", name: "Databricks", icon: <Component size={32} color="#FF3621" />, desc: "Connect to Databricks SQL or Spark" },
];

export default function Integrations() {
  const [step, setStep] = useState<"select" | "configure" | "loading" | "success">("select");
  const [selected, setSelected] = useState(CONNECTORS[0]);
  const [creds, setCreds] = useState({ host: "", database: "", user: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const testConnection = async () => {
    setStep("loading");
    setError(null);
    try {
      const res = await api.testIntegration({ engine: selected.id, ...creds });
      setResult(res);
      setStep("success");
    } catch (e: any) {
      setError(e.message || "Connection failed");
      setStep("configure");
    }
  };

  return (
    <div>
      <div className="page-header">
        <div className="page-eyebrow">Data connections</div>
        <h1 className="page-title">Data Integrations</h1>
        <p className="page-sub">Connect the engine directly to your Gold-tier data warehouse tables.</p>
      </div>

      {step === "select" && (
        <div className="grid grid-2-1" style={{ gap: 24, alignItems: "start" }}>
          <div>
            <div className="card-title" style={{ marginBottom: 16 }}>Available Connectors</div>
            <div className="grid grid-2">
              {CONNECTORS.map((c) => (
                <button key={c.id} className="card scenario-card" onClick={() => { setSelected(c); setStep("configure"); }}>
                  <div style={{ fontSize: 32, marginBottom: 12 }}>{c.icon}</div>
                  <div className="card-title">{c.name}</div>
                  <div className="card-sub">{c.desc}</div>
                </button>
              ))}
            </div>
          </div>
          
          <div className="card" style={{ background: "var(--surface-2)" }}>
            <div className="card-title" style={{ marginBottom: 12 }}>Connection Requirements</div>
            <p className="note" style={{ marginBottom: 16 }}>
              The engine requires read-only access to standard star-schema tables in your warehouse.
            </p>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", marginBottom: 8 }}>Required Tables (Retail):</div>
            <ul className="clean-list" style={{ marginBottom: 20 }}>
              <li><code style={{ fontSize: 12 }}>fct_sales</code> (POS Orders)</li>
              <li><code style={{ fontSize: 12 }}>fct_traffic</code> (Web Sessions)</li>
              <li><code style={{ fontSize: 12 }}>fct_inventory</code> (Stock & SLA)</li>
              <li><code style={{ fontSize: 12 }}>fct_marketing_weekly</code> (Ad Spend)</li>
            </ul>
            
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--ink)", marginBottom: 8 }}>How it works:</div>
            <ol style={{ margin: 0, paddingLeft: 20, fontSize: 13, color: "var(--ink-2)", lineHeight: 1.6 }}>
              <li style={{ paddingBottom: 6 }}>Select your Data Warehouse provider.</li>
              <li style={{ paddingBottom: 6 }}>Provide read-only credentials or a service account token.</li>
              <li style={{ paddingBottom: 6 }}>The engine will use <strong>DuckDB</strong> to natively query your cloud warehouse without pulling data into memory.</li>
              <li>Your KPIs will be calculated on-the-fly based on your <code>kpis.yaml</code> contract.</li>
            </ol>
          </div>
        </div>
      )}

      {step === "configure" && (
        <div className="card" style={{ maxWidth: 500, margin: "0 auto" }}>
          <div className="card-title" style={{ marginBottom: 20 }}>Configure {selected.name} Connection</div>
          {error && <div className="error-banner" style={{ marginBottom: 16 }}><AlertTriangle size={16} /> {error}</div>}
          
          <div className="form-field">
            <label className="form-label">Host URL</label>
            <input className="form-input" placeholder="e.g. xyz123.eu-west-1.snowflakecomputing.com" value={creds.host} onChange={e => setCreds({...creds, host: e.target.value})} />
          </div>
          <div className="form-field">
            <label className="form-label">Database Name</label>
            <input className="form-input" placeholder="e.g. PRODUCTION_DB" value={creds.database} onChange={e => setCreds({...creds, database: e.target.value})} />
          </div>
          <div className="form-field">
            <label className="form-label">Username / Role</label>
            <input className="form-input" placeholder="e.g. KPI_ENGINE_ROLE" value={creds.user} onChange={e => setCreds({...creds, user: e.target.value})} />
          </div>
          <div className="form-field">
            <label className="form-label">Password / Token</label>
            <input className="form-input" type="password" value={creds.password} onChange={e => setCreds({...creds, password: e.target.value})} />
          </div>

          <div style={{ display: "flex", gap: 12, marginTop: 24, justifyContent: "flex-end" }}>
            <button className="btn btn-ghost" onClick={() => setStep("select")}>Cancel</button>
            <button className="btn btn-primary" onClick={testConnection}>Test & Connect</button>
          </div>
        </div>
      )}

      {step === "loading" && (
        <Loader text="Connecting to Data Warehouse & Introspecting Schema..." />
      )}

      {step === "success" && (
        <div className="card" style={{ maxWidth: 520, margin: "0 auto", textAlign: "center" }}>
          <CheckCircle2 size={44} style={{ color: "var(--confident)", marginBottom: 16 }} />
          <div className="card-title" style={{ marginBottom: 8, justifyContent: "center" }}>Connection Successful</div>
          <p className="card-sub" style={{ marginBottom: 20 }}>
            {(result?.message as string) ?? `Connected to ${selected.name}.`}
          </p>
          {result && (
            <dl className="kv-grid" style={{ textAlign: "left", marginBottom: 24, gridTemplateColumns: "auto 1fr" }}>
              {Object.entries(result)
                .filter(([k]) => k !== "message")
                .map(([k, v]) => (
                  <div key={k} style={{ display: "contents" }}>
                    <dt>{k.replace(/_/g, " ")}</dt>
                    <dd>{Array.isArray(v) ? v.join(", ") : String(v)}</dd>
                  </div>
                ))}
            </dl>
          )}
          <button className="btn btn-primary" onClick={() => { setStep("select"); setResult(null); }}>Finish Setup</button>
        </div>
      )}
    </div>
  );
}
