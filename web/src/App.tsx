import { useEffect, useState, useCallback } from "react";
import { BrowserRouter, Routes, Route, NavLink, useLocation } from "react-router-dom";
import { api } from "./api";
import { prefetchRoutes } from "./prefetch";
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

  const isActive = (to: string) =>
    to === "/" ? location.pathname === "/" : location.pathname.startsWith(to);

  return (
    <header className="topbar">
      {/* One row: brand, nav, controls. The previous two-row bar spent
          ~110px of vertical space before any content began. */}
      <div className="topbar-row">
        <div className="topbar-brand">
          <div className="brand-mark"><Activity size={16} /></div>
          <div className="sidebar-brand-text">KPI Intelligence</div>
        </div>

        <nav className="nav-tabs topbar-nav-inline">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className={`nav-tab${isActive(item.to) ? " active" : ""}`}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="topbar-spacer" />

        <span className="topbar-week">{week}</span>

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

      {mobileOpen && (
        <nav className="topbar-mobile-nav">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className={`nav-tab${isActive(item.to) ? " active" : ""}`}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}

/**
 * Start from the viewer's own setting: a saved choice if they have made one,
 * otherwise whatever the OS asks for. Hardcoding dark meant a light-mode
 * machine got a dark flash on every single load.
 */
function initialTheme(): "dark" | "light" {
  try {
    const saved = localStorage.getItem("kpi-theme");
    if (saved === "dark" || saved === "light") return saved;
    return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  } catch {
    return "dark";      // private mode, or storage blocked
  }
}

/**
 * Governance and the learning loop, as one page.
 *
 * These were two page components stacked in a div, so the route rendered two
 * eyebrows and two page-sized titles — it read as two documents glued
 * together rather than one place. They are genuinely one subject: what the
 * system knows, and how it learns. So the route owns the title, and each half
 * becomes a section under it.
 */
function SystemPage({ persona, personas, onPersonaChange }: {
  persona: string;
  personas: Persona[];
  onPersonaChange: (id: string) => void;
}) {
  return (
    <div>
      <div className="page-header">
        <div className="page-eyebrow">System of record</div>
        <h1 className="page-title">System &amp; Learning</h1>
        <p className="page-sub">
          The governed contract every number is computed from, and the feedback loop that
          recalibrates it.
        </p>
      </div>

      <section className="page-section">
        <h2 className="section-heading">Governance</h2>
        <p className="section-heading-sub">
          KPI semantic contract · Source lineage · Entitlement matrix · Confidence architecture
        </p>
        <Governance hideHeader />
      </section>

      <section className="page-section">
        <h2 className="section-heading">Feedback &amp; Learning</h2>
        <p className="section-heading-sub">
          Analyst verdicts · Isotonic calibration · Driver prior updates · Business annotations
        </p>
        <FeedbackHub
          week={FOCAL_WEEK} persona={persona} personas={personas}
          onPersonaChange={onPersonaChange} hideHeader
        />
      </section>
    </div>
  );
}

function AppShell() {
  const [theme, setTheme] = useState<"dark" | "light">(initialTheme);
  const [cmdOpen, setCmdOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [persona, setPersona] = useState("cfo");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [freshness, setFreshness] = useState<Freshness[]>([]);
  const location = useLocation();

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("kpi-theme", theme); } catch { /* storage blocked */ }
  }, [theme]);
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

  // Warm the other routes once the browser is idle and the current page has
  // had time to load its own data. See prefetch.ts for why this waits and why
  // it goes one request at a time.
  useEffect(() => prefetchRoutes(FOCAL_WEEK, persona), [persona]);

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
        {/* Keyed on the path so a route change replays the entrance — without
            it React reuses the DOM and the new page simply blinks into place. */}
        <div className="content-frame page-enter" key={location.pathname}>
          <Routes>
            <Route path="/" element={<Overview week={FOCAL_WEEK} persona={persona} personas={personas} onPersonaChange={setPersona} />} />
            <Route path="/investigation" element={<Investigate week={FOCAL_WEEK} persona={persona} />} />
            <Route path="/actions" element={<ActionPlaybook week={FOCAL_WEEK} persona={persona} personas={personas} onPersonaChange={setPersona} />} />
            <Route path="/governance" element={<Governance />} />
            <Route path="/feedback" element={<FeedbackHub week={FOCAL_WEEK} persona={persona} personas={personas} onPersonaChange={setPersona} />} />
            <Route path="/system" element={<SystemPage persona={persona} personas={personas} onPersonaChange={setPersona} />} />
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
