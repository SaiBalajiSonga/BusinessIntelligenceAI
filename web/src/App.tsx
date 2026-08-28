import { useEffect, useState, useCallback } from "react";
import { BrowserRouter, Routes, Route, NavLink, useLocation } from "react-router-dom";
import { api } from "./api";
import CommandPalette from "./components/CommandPalette";
import ToastContainer from "./components/Toast";
import Overview from "./pages/Overview";
import RootCause from "./pages/RootCause";
import ActionPlaybook from "./pages/Actions";
import NarrativeStudio from "./pages/NarrativeStudio";
import Governance from "./pages/Governance";
import FeedbackHub from "./pages/FeedbackHub";
import type { Freshness, Persona } from "./types";
import "./styles.css";

const FOCAL_WEEK = "2026-W32";

const NAV = [
  { to: "/",           icon: "📊", label: "KPI Overview",    badge: null },
  { to: "/root-cause", icon: "🔍", label: "Root Cause",      badge: "4 scenarios" },
  { to: "/actions",    icon: "⚡", label: "Action Playbook", badge: null },
  { to: "/narrative",  icon: "🤖", label: "Narrative Studio",badge: null },
  { to: "/governance", icon: "🏛️", label: "Governance",      badge: null },
  { to: "/feedback",   icon: "🔔", label: "Feedback & Learn", badge: null },
];

function Sidebar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const location = useLocation();

  return (
    <nav className={`sidebar${collapsed ? " collapsed" : ""}`} aria-label="Main navigation">
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">📡</div>
        {!collapsed && (
          <div>
            <div className="sidebar-brand-text">KPI Intelligence</div>
            <div style={{ fontSize: 10, color: "var(--muted)", marginTop: 1 }}>Enterprise · v0.1</div>
          </div>
        )}
      </div>

      <div className="sidebar-nav">
        {NAV.map((item) => {
          const active = item.to === "/"
            ? location.pathname === "/"
            : location.pathname.startsWith(item.to);
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={`nav-item${active ? " active" : ""}`}
              title={collapsed ? item.label : undefined}
            >
              <span className="nav-icon">{item.icon}</span>
              {!collapsed && <span className="nav-label">{item.label}</span>}
              {!collapsed && item.badge && (
                <span className="nav-badge">{item.badge}</span>
              )}
            </NavLink>
          );
        })}
      </div>

      <div className="sidebar-footer">
        <button className="sidebar-collapse-btn" onClick={onToggle} title={collapsed ? "Expand" : "Collapse"}>
          <span className="nav-icon">{collapsed ? "→" : "←"}</span>
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </nav>
  );
}

function TopBar({
  collapsed, week, persona, personas, onPersonaChange, freshness, theme, onThemeToggle, onCmdOpen,
}: {
  collapsed: boolean;
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
  const currentPage = NAV.find((n) =>
    n.to === "/" ? location.pathname === "/" : location.pathname.startsWith(n.to)
  );

  return (
    <header className={`topbar${collapsed ? " collapsed" : ""}`}>
      <div>
        <div className="topbar-title">{currentPage?.label ?? "KPI Intelligence"}</div>
      </div>
      <span className="topbar-week">{week}</span>

      {/* Freshness pills */}
      <div style={{ display: "flex", gap: 6 }}>
        {freshness.map((f) => (
          <span className="pill" key={f.source} title={`${f.lag_hours}h lag · ${f.sla_hours}h SLA`}>
            <span
              className="dot dot-pulse"
              style={{ background: f.status === "fresh" ? "var(--good)" : "var(--warning)" }}
            />
            {f.source}
          </span>
        ))}
      </div>

      <div className="topbar-spacer" />

      {/* Command palette trigger */}
      <button className="topbar-cmd-btn" onClick={onCmdOpen}>
        🔍 Search <kbd>⌘K</kbd>
      </button>

      {/* Theme toggle */}
      <button
        className="btn btn-ghost btn-icon"
        onClick={onThemeToggle}
        title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        style={{ fontSize: 16 }}
      >
        {theme === "dark" ? "☀️" : "🌙"}
      </button>

      {/* Persona switcher */}
      <div className="seg" role="group" aria-label="Persona">
        {personas.map((p) => (
          <button
            key={p.id}
            aria-pressed={p.id === persona}
            onClick={() => onPersonaChange(p.id)}
            title={`${p.regions.join(", ")}${p.masked_columns.length ? ` · ${p.masked_columns.length} masked` : ""}`}
          >
            {p.label}
          </button>
        ))}
      </div>
    </header>
  );
}

function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [cmdOpen, setCmdOpen] = useState(false);
  const [persona, setPersona] = useState("cfo");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [freshness, setFreshness] = useState<Freshness[]>([]);

  // Theme on <html>
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
  }, [theme]);

  // Global keyboard shortcut ⌘K / Ctrl+K
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

  // Fetch personas and freshness once
  useEffect(() => {
    api.personas().then(setPersonas).catch(() => {});
    api.freshness().then(setFreshness).catch(() => {});
    // Refresh freshness every 30s
    const id = setInterval(() => api.freshness().then(setFreshness).catch(() => {}), 30000);
    return () => clearInterval(id);
  }, []);

  const toggleTheme = useCallback(() => setTheme((t) => t === "dark" ? "light" : "dark"), []);

  return (
    <div className="app-shell">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((v) => !v)} />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <TopBar
          collapsed={collapsed}
          week={FOCAL_WEEK}
          persona={persona}
          personas={personas}
          onPersonaChange={setPersona}
          freshness={freshness}
          theme={theme}
          onThemeToggle={toggleTheme}
          onCmdOpen={() => setCmdOpen(true)}
        />

        <main className={`main-content${collapsed ? " collapsed" : ""}`}>
          <Routes>
            <Route path="/"           element={<Overview week={FOCAL_WEEK} persona={persona} />} />
            <Route path="/root-cause" element={<RootCause week={FOCAL_WEEK} persona={persona} />} />
            <Route path="/actions"    element={<ActionPlaybook week={FOCAL_WEEK} persona={persona} />} />
            <Route path="/narrative"  element={<NarrativeStudio week={FOCAL_WEEK} persona={persona} />} />
            <Route path="/governance" element={<Governance />} />
            <Route path="/feedback"   element={<FeedbackHub week={FOCAL_WEEK} persona={persona} />} />
          </Routes>
        </main>
      </div>

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
