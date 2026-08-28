import { useState } from "react";
import { api } from "../api";
import Loader from "../components/Loader";

const CONNECTORS = [
  { id: "snowflake", name: "Snowflake", icon: "❄️", desc: "Connect to your Snowflake Data Cloud" },
  { id: "bigquery", name: "Google BigQuery", icon: "🔍", desc: "Connect to your GCP Data Warehouse" },
  { id: "postgresql", name: "PostgreSQL", icon: "🐘", desc: "Connect to standard PostgreSQL databases" },
  { id: "redshift", name: "Amazon Redshift", icon: "🧱", desc: "Connect to your AWS Data Warehouse" },
  { id: "databricks", name: "Databricks", icon: "🧱", desc: "Connect to Databricks SQL or Spark" },
];

export default function Integrations() {
  const [step, setStep] = useState<"select" | "configure" | "loading" | "success">("select");
  const [selected, setSelected] = useState(CONNECTORS[0]);
  const [creds, setCreds] = useState({ host: "", database: "", user: "", password: "" });
  const [error, setError] = useState<string | null>(null);

  const testConnection = async () => {
    setStep("loading");
    setError(null);
    try {
      await api.testIntegration({ engine: selected.id, ...creds });
      setStep("success");
    } catch (e: any) {
      setError(e.message || "Connection failed");
      setStep("configure");
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Data Integrations</h1>
        <p className="page-sub">Connect the engine directly to your Gold-tier data warehouse tables.</p>
      </div>

      {step === "select" && (
        <div className="grid grid-3">
          {CONNECTORS.map((c) => (
            <button key={c.id} className="card scenario-card" onClick={() => { setSelected(c); setStep("configure"); }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>{c.icon}</div>
              <div className="card-title">{c.name}</div>
              <div className="card-sub">{c.desc}</div>
            </button>
          ))}
        </div>
      )}

      {step === "configure" && (
        <div className="card" style={{ maxWidth: 500, margin: "0 auto" }}>
          <div className="card-title" style={{ marginBottom: 20 }}>Configure {selected.name} Connection</div>
          {error && <div className="error-banner" style={{ marginBottom: 16 }}>⚠️ {error}</div>}
          
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
        <div className="card" style={{ maxWidth: 500, margin: "0 auto", textAlign: "center" }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
          <div className="card-title" style={{ marginBottom: 8 }}>Connection Successful!</div>
          <p className="card-sub" style={{ marginBottom: 24 }}>
            Successfully connected to {selected.name}. The engine introspected 14 dimensional tables and automatically generated the semantic <code>kpis.yaml</code> contract.
          </p>
          <button className="btn btn-primary" onClick={() => setStep("select")}>Finish Setup</button>
        </div>
      )}
    </div>
  );
}
