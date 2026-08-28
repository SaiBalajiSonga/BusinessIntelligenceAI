import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";

interface CmdItem {
  icon: string;
  label: string;
  hint?: string;
  action: () => void;
}

interface Props {
  open: boolean;
  onClose: () => void;
}



const PERSONA_ITEMS = [
  { icon: "👔", label: "Switch to CFO", hint: "All regions", action: () => {} },
  { icon: "🗂️", label: "Switch to EU Category Manager", hint: "DE, FR, NL only", action: () => {} },
  { icon: "📈", label: "Switch to Data Analyst", hint: "Full detail", action: () => {} },
];

export default function CommandPalette({ open, onClose }: Props) {
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const NAV: CmdItem[] = [
    { icon: "📊", label: "KPI Overview",           hint: "Home",           action: () => navigate("/") },
    { icon: "🔍", label: "Root Cause Analysis",    hint: "Workspace",      action: () => navigate("/root-cause") },
    { icon: "⚡", label: "Action Playbook",         hint: "What-if levers", action: () => navigate("/actions") },
    { icon: "🤖", label: "Narrative Studio",        hint: "AI + Feedback",  action: () => navigate("/narrative") },
    { icon: "🏛️", label: "Governance",              hint: "Contract",       action: () => navigate("/governance") },
    { icon: "🔔", label: "Feedback & Learning",     hint: "Loop",           action: () => navigate("/feedback") },
  ];

  const all = [...NAV, ...PERSONA_ITEMS];
  const filtered = query
    ? all.filter((i) => i.label.toLowerCase().includes(query.toLowerCase()))
    : all;

  useEffect(() => {
    if (open) {
      setQuery("");
      setFocused(0);
      setTimeout(() => inputRef.current?.focus(), 60);
    }
  }, [open]);

  const run = useCallback((item: CmdItem) => {
    item.action();
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") { onClose(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); setFocused((f) => Math.min(f + 1, filtered.length - 1)); }
      if (e.key === "ArrowUp") { e.preventDefault(); setFocused((f) => Math.max(f - 1, 0)); }
      if (e.key === "Enter") { if (filtered[focused]) run(filtered[focused]); }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, filtered, focused, run, onClose]);

  if (!open) return null;

  const navItems = query ? filtered : NAV;
  const personaItems = query ? [] : PERSONA_ITEMS;

  return (
    <div className="cmd-overlay" onClick={onClose}>
      <div className="cmd-box" onClick={(e) => e.stopPropagation()}>
        <div className="cmd-input-wrap">
          <span className="cmd-search-icon">🔍</span>
          <input
            ref={inputRef}
            className="cmd-input"
            placeholder="Search pages, personas, scenarios…"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setFocused(0); }}
          />
          <kbd>ESC</kbd>
        </div>
        <div className="cmd-results">
          {navItems.length > 0 && (
            <>
              <div className="cmd-group-label">Navigate</div>
              {navItems.map((item, i) => (
                <button
                  key={item.label}
                  className={`cmd-item ${focused === i ? "focused" : ""}`}
                  onMouseEnter={() => setFocused(i)}
                  onClick={() => run(item)}
                >
                  <span className="cmd-item-icon">{item.icon}</span>
                  <span className="cmd-item-label">{item.label}</span>
                  {item.hint && <span className="cmd-item-hint">{item.hint}</span>}
                </button>
              ))}
            </>
          )}
          {personaItems.length > 0 && (
            <>
              <div className="cmd-group-label" style={{ marginTop: 8 }}>Switch Persona</div>
              {personaItems.map((item, i) => (
                <button
                  key={item.label}
                  className={`cmd-item ${focused === navItems.length + i ? "focused" : ""}`}
                  onMouseEnter={() => setFocused(navItems.length + i)}
                  onClick={() => run(item)}
                >
                  <span className="cmd-item-icon">{item.icon}</span>
                  <span className="cmd-item-label">{item.label}</span>
                  {item.hint && <span className="cmd-item-hint">{item.hint}</span>}
                </button>
              ))}
            </>
          )}
          {filtered.length === 0 && (
            <div style={{ padding: "24px", textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
              No results for "{query}"
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
