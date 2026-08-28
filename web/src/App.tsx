import { useEffect, useState, useCallback } from "react";
import { BrowserRouter, Routes, Route, NavLink, useLocation } from "react-router-dom";
import { api } from "./api";
import CommandPalette from "./components/CommandPalette";
import ToastContainer from "./components/Toast";
import Overview from "./pages/Overview";
import DeepDive from "./pages/DeepDive";
import Governance from "./pages/Governance";
import FeedbackHub from "./pages/FeedbackHub";
import type { Freshness, Persona } from "./types";
import "./styles.css";

const FOCAL_WEEK = "2026-W32";

const NAV = [
  { to: "/", label: "Dashboard" },
  { to: "/investigation", label: "KPI Investigation" },
  { to: "/system", label: "System & Learning" },
  { to: "/integrations", label: "Data Connections" },
];

function TopNav({
  week, persona, personas, onPersonaChange, freshness, theme, onThemeToggle, onCmdOpen,
}: {
  week: string;
  persona: string;
  personas: Persona[];
  onPersonaChange: (p: string) => void;
  freshness: Freshness[];
  theme: "dark" | "light";
  onThemeToggle: () => void;
  onCmdOpen: () => void;
}) {
  const location = useLocation();

  return (
    <header className="topbar" style={{ display: 'flex', flexDirection: 'column', height: 'auto', padding: 0, borderBottom: '1px solid var(--border)' }}>
      {/* Upper bar: Brand & Controls */}
      <div style={{ display: 'flex', alignItems: 'center', width: '100%', padding: '16px 32px', gap: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div className="sidebar-brand-icon" style={{ boxShadow: 'none' }}>📡</div>
          <div className="sidebar-brand-text" style={{ fontSize: '16px' }}>KPI Intelligence</div>
        </div>

        <span className="topbar-week">{week}</span>

        <div className="topbar-spacer" />

        <div className="seg" role="group" aria-label="Persona">
          {personas.map((p) => (
            <button
              key={p.id}
              aria-pressed={p.id === persona}
              onClick={() => onPersonaChange(p.id)}
              title={`${p.regions.join(", ")}`}
            >
              {p.label}
            </button>
          ))}
        </div>

        <button className="topbar-cmd-btn" onClick={onCmdOpen}>
          🔍 Search <kbd>⌘K</kbd>
        </button>

        <button className="btn btn-ghost btn-icon" onClick={onThemeToggle} style={{ fontSize: 16 }}>
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
      </div>

      {/* Lower bar: Navigation Tabs */}
      <div style={{ display: 'flex', padding: '0 32px', gap: '32px' }}>
        {NAV.map(item => {
          const active = item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to);
          return (
            <NavLink
              key={item.to}
              to={item.to}
              style={{
                padding: '12px 0',
                fontSize: '14px',
                fontWeight: 600,
                color: active ? 'var(--brand)' : 'var(--ink-2)',
                borderBottom: active ? '2px solid var(--brand)' : '2px solid transparent',
                textDecoration: 'none',
                transition: 'all 0.2s ease',
                marginBottom: '-1px'
              }}
            >
              {item.label}
            </NavLink>
          );
        })}
      </div>
    </header>
  );
}

function AppShell() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [cmdOpen, setCmdOpen] = useState(false);
  const [persona, setPersona] = useState("cfo");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [freshness, setFreshness] = useState<Freshness[]>([]);

  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); }, [theme]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdOpen((v) => !v);
      }
      if (e.key === "Escape") setCmdOpen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    api.personas().then(setPersonas).catch(() => {});
    api.freshness().then(setFreshness).catch(() => {});
  }, []);

  const toggleTheme = useCallback(() => setTheme((t) => t === "dark" ? "light" : "dark"), []);

  return (
    <div className="app-shell" style={{ flexDirection: 'column' }}>
      <TopNav
        week={FOCAL_WEEK}
        persona={persona}
        personas={personas}
        onPersonaChange={setPersona}
        freshness={freshness}
        theme={theme}
        onThemeToggle={toggleTheme}
        onCmdOpen={() => setCmdOpen(true)}
      />

      <main style={{ flex: 1, overflowY: 'auto', padding: '48px 48px 80px', background: 'var(--page)' }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
          <Routes>
            <Route path="/" element={<Overview week={FOCAL_WEEK} persona={persona} />} />
            <Route path="/investigation" element={<DeepDive week={FOCAL_WEEK} persona={persona} />} />
            <Route path="/system" element={
              <div style={{ display: "flex", flexDirection: "column", gap: "64px" }}>
                <Governance />
                <FeedbackHub week={FOCAL_WEEK} persona={persona} />
              </div>
            } />
          </Routes>
        </div>
      </main>

      <CommandPalette open={cmdOpen} onClose={() => setCmdOpen(false)} />
      <ToastContainer />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}
