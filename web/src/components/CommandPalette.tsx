import { useState, useEffect, useCallback, useRef } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { LayoutDashboard, Search, Zap, Bot, Landmark, Bell, Users } from "lucide-react";
import type { Persona } from "../types";

interface CmdItem {
  icon: ReactNode;
  label: string;
  hint?: string;
  action: () => void;
}

interface Props {
  open: boolean;
  onClose: () => void;
  personas: Persona[];
  onPersonaChange: (id: string) => void;
}

export default function CommandPalette({ open, onClose, personas, onPersonaChange }: Props) {
  const [query, setQuery] = useState("");
  const [focused, setFocused] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const NAV: CmdItem[] = [
    { icon: <LayoutDashboard size={15} />, label: "KPI Overview",        hint: "Home",           action: () => navigate("/") },
    { icon: <Bot size={15} />,             label: "The Story",           hint: "Narrative",      action: () => navigate("/investigation#story") },
    { icon: <Search size={15} />,          label: "The Evidence",        hint: "Root cause",      action: () => navigate("/investigation#evidence") },
    { icon: <Zap size={15} />,             label: "Next Steps",          hint: "Jump to actions", action: () => navigate("/investigation#actions") },
    { icon: <Zap size={15} />,             label: "Full Action Playbook", hint: "Standalone view", action: () => navigate("/actions") },
    { icon: <Landmark size={15} />,        label: "Governance",          hint: "Contract",       action: () => navigate("/governance") },
    { icon: <Bell size={15} />,            label: "Feedback & Learning", hint: "Loop",           action: () => navigate("/feedback") },
  ];

  const PERSONA_ITEMS: CmdItem[] = personas.map((p) => ({
    icon: <Users size={15} />,
    label: `Switch to ${p.label}`,
    hint: p.regions.join(", "),
    action: () => onPersonaChange(p.id),
  }));

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
          <Search size={18} />
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
