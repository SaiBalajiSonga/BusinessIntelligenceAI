import { useEffect, useState, useCallback } from "react";
import { BrowserRouter, Routes, Route, NavLink, useLocation } from "react-router-dom";
import { api } from "./api";
import CommandPalette from "./components/CommandPalette";
import ToastContainer from "./components/Toast";
import Integrations from "./pages/Integrations";
import Overview from "./pages/Overview";
import Investigate from "./pages/Investigate";
import ActionPlaybook from "./pages/Actions";
import Governance from "./pages/Governance";
import FeedbackHub from "./pages/FeedbackHub";
import { Activity, Search, Sun, Moon, Menu, X } from "lucide-react";
import type { Freshness, Persona } from "./types";
import "./styles.css";

const FOCAL_WEEK = "2026-W32";

const NAV = [
  { to: "/", label: "Overview" },
  { to: "/investigation", label: "Investigate" },
  { to: "/system", label: "System & Learning" },
  { to: "/integrations", label: "Data Connections" },
];

function TopNav({
  week, theme, onThemeToggle, onCmdOpen,
  mobileOpen, onMobileToggle,
}: {
  week: string;
  freshness: Freshness[];
  theme: "dark" | "light";
  onThemeToggle: () => void;
  onCmdOpen: () => void;
  mobileOpen: boolean;
  onMobileToggle: () => void;
}) {
  const location = useLocation();

  return (
    <header className="topbar" style={{ display: 'flex', flexDirection: 'column', height: 'auto', padding: 0 }}>
      {/* Upper bar: Brand & Controls */}
      <div className="topbar-row" style={{ display: 'flex', alignItems: 'center', width: '100%', padding: '14px 32px', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexShrink: 0 }}>
          <div className="brand-mark"><Activity size={16} /></div>
          <div className="sidebar-brand-text" style={{ fontSize: '15px' }}>KPI Intelligence</div>
        </div>

        <span className="topbar-week">{week}</span>

        <div className="topbar-spacer" />

        <button className="topbar-cmd-btn" onClick={onCmdOpen}>
          <Search size={14} /> <span className="cmd-btn-label">Search</span> <kbd>⌘K</kbd>
        </button>

        <button className="btn btn-ghost btn-icon" onClick={onThemeToggle} aria-label="Toggle theme">
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>

        <button className="btn btn-ghost btn-icon mobile-nav-toggle" onClick={onMobileToggle} aria-label="Toggle navigation">
          {mobileOpen ? <X size={18} /> : <Menu size={18} />}
        </button>
      </div>

      {/* Lower bar: Navigation Tabs */}
      <nav className="nav-tabs" style={{ padding: '0 32px' }}>
        {NAV.map(item => {
          const active = item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to);
          return (
            <NavLink key={item.to} to={item.to} className={`nav-tab${active ? " active" : ""}`}>
              {item.label}
            </NavLink>
          );
        })}
      </nav>

      {/* Mobile menu */}
      {mobileOpen && (
        <nav style={{ display: 'flex', flexDirection: 'column', padding: '8px 20px 16px', borderTop: '1px solid var(--border)' }}>
          {NAV.map(item => {
            const active = item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to);
            return (
              <NavLink key={item.to} to={item.to} className={`nav-tab${active ? " active" : ""}`} style={{ padding: '12px 4px', borderBottom: 'none' }}>
                {item.label}
              </NavLink>
            );
          })}
        </nav>
      )}
    </header>
  );
}

function AppShell() {
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [cmdOpen, setCmdOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [persona, setPersona] = useState("cfo");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [freshness, setFreshness] = useState<Freshness[]>([]);
  const location = useLocation();

  useEffect(() => { document.documentElement.setAttribute("data-theme", theme); }, [theme]);
  useEffect(() => { setMobileOpen(false); }, [location.pathname]);

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
    <div className="app-shell">
      <TopNav
        week={FOCAL_WEEK}
        freshness={freshness}
        theme={theme}
        onThemeToggle={toggleTheme}
        onCmdOpen={() => setCmdOpen(true)}
        mobileOpen={mobileOpen}
        onMobileToggle={() => setMobileOpen((v) => !v)}
      />

      <main className="main-content">
        <div className="content-frame">
          <Routes>
            <Route path="/" element={<Overview week={FOCAL_WEEK} persona={persona} personas={personas} onPersonaChange={setPersona} />} />
            <Route path="/investigation" element={<Investigate week={FOCAL_WEEK} persona={persona} />} />
            <Route path="/actions" element={<ActionPlaybook week={FOCAL_WEEK} persona={persona} personas={personas} onPersonaChange={setPersona} />} />
            <Route path="/governance" element={<Governance />} />
            <Route path="/feedback" element={<FeedbackHub week={FOCAL_WEEK} persona={persona} personas={personas} onPersonaChange={setPersona} />} />
            <Route path="/system" element={
              <div style={{ display: "flex", flexDirection: "column", gap: "56px" }}>
                <Governance />
                <FeedbackHub week={FOCAL_WEEK} persona={persona} personas={personas} onPersonaChange={setPersona} />
              </div>
            } />
            <Route path="/integrations" element={<Integrations />} />
          </Routes>
        </div>
      </main>

      <CommandPalette
        open={cmdOpen}
        onClose={() => setCmdOpen(false)}
        personas={personas}
        onPersonaChange={setPersona}
      />
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
