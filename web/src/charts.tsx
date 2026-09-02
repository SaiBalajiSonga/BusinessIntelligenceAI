import { useState } from "react";
import { fmt } from "./api";
import type { Cause, Split } from "./types";

/* Colour carries polarity here, not identity, so this is the diverging pair —
   blue and red as opposites — never a value ramp and never a status token. */

interface Row {
  label: string;
  from: number;
  to: number;
  delta: number | null; // null = a reference level (expected / actual)
  cause?: Cause;
}

function buildRows(expected: number, actual: number, causes: Cause[]): Row[] {
  const rows: Row[] = [{ label: "Expected", from: 0, to: expected, delta: null }];
  let running = expected;
  for (const c of [...causes].sort((a, b) => a.amount - b.amount)) {
    const next = running + c.amount;
    rows.push({ label: c.label, from: running, to: next, delta: c.amount, cause: c });
    running = next;
  }
  rows.push({ label: "Actual", from: 0, to: actual, delta: null });
  return rows;
}

export function Bridge({
  expected, actual, causes, currency, onSelect,
}: {
  expected: number; actual: number; causes: Cause[]; currency: string;
  onSelect: (c: Cause) => void;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const rows = buildRows(expected, actual, causes);

  const ROW = 34, GAP = 8, PAD_L = 132, PAD_R = 104, PAD_T = 8, AXIS = 30;
  const W = 860;
  const H = PAD_T + rows.length * (ROW + GAP) + AXIS;

  // The axis spans the cumulative range, not zero. A 600k step against a 7M
  // base is invisible on a zero-anchored scale — the whole bridge would read
  // as five identical full-width bars.
  const values = rows.flatMap((r) => (r.delta === null ? [r.to] : [r.from, r.to]));
  const lo = Math.min(...values), hi = Math.max(...values);
  const pad = (hi - lo) * 0.12;
  const min = lo - pad, max = hi + pad;
  const x = (v: number) => PAD_L + ((v - min) / (max - min)) * (W - PAD_L - PAD_R);

  const ticks = Array.from({ length: 5 }, (_, i) => min + ((max - min) * i) / 4);

  return (
    <figure style={{ margin: 0 }}>
      <div style={{ display: "flex", gap: 16, marginBottom: 10, fontSize: 11.5 }}>
        <Key swatch="var(--neg)" label="Reduced revenue" />
        <Key swatch="var(--pos)" label="Increased revenue" />
        <Key swatch="var(--axis)" label="Level" />
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} role="img" width="100%" style={{ height: "auto", display: "block" }}
           aria-label={`Bridge from an expected ${fmt.abs(expected)} to an actual ${fmt.abs(actual)} ${currency}, decomposed into ${causes.length} contributions.`}>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={x(t)} y1={PAD_T} x2={x(t)} y2={H - AXIS}
                  stroke="var(--grid)" strokeWidth="1" />
            <text x={x(t)} y={H - AXIS + 16} textAnchor="middle"
                  fontSize="10.5" fill="var(--muted)">
              {fmt.compact(t, "")}
            </text>
          </g>
        ))}

        {rows.map((r, i) => {
          const y = PAD_T + i * (ROW + GAP);
          const level = r.delta === null;
          const x1 = level ? x(min) : x(Math.min(r.from, r.to));
          const x2 = level ? x(r.to) : x(Math.max(r.from, r.to));
          // a 2px surface gap keeps adjoining segments legible without a border
          const w = Math.max(2, x2 - x1 - 2);
          const fill = level ? "var(--axis)" : r.delta! < 0 ? "var(--neg)" : "var(--pos)";
          const on = hover === i;

          return (
            <g key={i}
               onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}
               onClick={() => r.cause && onSelect(r.cause)}
               style={{ cursor: r.cause ? "pointer" : "default" }}>
              <rect x={PAD_L - 8} y={y - 3} width={W - PAD_L} height={ROW + 6}
                    fill={on ? "var(--surface-2)" : "transparent"} rx="5" />
              <text x={PAD_L - 16} y={y + ROW / 2 + 4} textAnchor="end"
                    fontSize="12" fill={level ? "var(--ink-2)" : "var(--ink)"}
                    fontWeight={level ? 400 : 550}>
                {r.label}
              </text>
              <rect x={x1} y={y + 6} width={w} height={ROW - 12} rx="4" fill={fill}
                    opacity={level ? 0.5 : on ? 1 : 0.88} />
              <text x={x2 + 10} y={y + ROW / 2 + 4} fontSize="11.5"
                    fill="var(--ink-2)" style={{ fontVariantNumeric: "tabular-nums" }}>
                {level ? fmt.abs(r.to) : fmt.money(r.delta, "")}
              </text>
            </g>
          );
        })}
      </svg>

      <figcaption className="note" style={{ marginTop: 6 }}>
        Contributions sum to the gap exactly — LMDI and the price/mix split leave no
        residual. Select a bar for its evidence.
      </figcaption>
    </figure>
  );
}

function Key({ swatch, label }: { swatch: string; label: string }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--ink-2)" }}>
      <span style={{ width: 10, height: 10, borderRadius: 3, background: swatch }} />
      {label}
    </span>
  );
}

/* ------------------------------------------------------------ confidence -- */

export function ConfidenceBars({
  components, weights,
}: { components: Record<string, number>; weights: Record<string, number> }) {
  const entries = Object.entries(components);
  const contribs = entries.map(([k, v]) => ({ k, v, c: (weights[k] ?? 0) * v }));
  const span = Math.max(...contribs.map((d) => Math.abs(d.c)), 0.05);

  return (
    <div style={{ display: "grid", gap: 9 }}>
      {contribs.map(({ k, v, c }) => {
        const wide = (Math.abs(c) / span) * 50;
        const neg = c < 0;
        return (
          <div key={k} style={{ display: "grid", gridTemplateColumns: "116px 1fr 54px", gap: 10, alignItems: "center" }}>
            <span style={{ fontSize: 12, color: "var(--ink-2)" }}>{k.replace(/_/g, " ")}</span>
            <div style={{ position: "relative", height: 14, background: "var(--surface-2)", borderRadius: 4 }}>
              <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "var(--axis)" }} />
              <div style={{
                position: "absolute", top: 2, bottom: 2, borderRadius: 3,
                background: neg ? "var(--neg)" : "var(--pos)",
                left: neg ? `${50 - wide}%` : "50%", width: `${wide}%`,
              }} />
            </div>
            <span style={{ fontSize: 11.5, textAlign: "right", color: "var(--muted)", fontVariantNumeric: "tabular-nums" }}>
              {v.toFixed(2)}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ---------------------------------------------------- engine pipeline -- */
/* The signature visual: makes "deterministic math first, LLM second" a thing
   you SEE, not a sentence you read. Every stage and every millisecond here is
   the real measured split — nothing is illustrative. */

const STAGE_ICON: Record<string, string> = {
  detect: "◆", reconcile: "▤", decompose: "▲", attribute: "◈",
  causal: "∿", confidence: "◐", narrate: "✎",
};

function iconFor(name: string): string {
  const key = name.toLowerCase();
  for (const k of Object.keys(STAGE_ICON)) if (key.includes(k)) return STAGE_ICON[k];
  return "○";
}

export function Pipeline({ split }: { split: Split }) {
  const stages = split.stages;
  const maxMs = Math.max(...stages.map((s) => s.ms), 1);

  return (
    <div className="pipeline">
      <div className="pipeline-row">
        {stages.map((s, i) => (
          <div className="pipeline-stage" key={s.name}>
            <div className="pipeline-node-wrap">
              <div
                className={`pipeline-node ${s.kind}`}
                style={{ ["--h" as string]: `${18 + (s.ms / maxMs) * 26}px` }}
                title={s.basis ?? s.name}
              >
                <span className="pipeline-node-icon">{iconFor(s.name)}</span>
              </div>
              {i < stages.length - 1 && (
                <div className={`pipeline-link ${s.kind === "llm" || stages[i + 1].kind === "llm" ? "llm" : "det"}`} />
              )}
            </div>
            <div className="pipeline-stage-name">{s.name}</div>
            <div className="pipeline-stage-ms">{fmt.ms(s.ms)}</div>
          </div>
        ))}
      </div>
      <div className="pipeline-foot">
        <span className="pipeline-foot-item">
          <span className="dot" style={{ background: "var(--s1)" }} /> Deterministic {fmt.pct(1 - split.llm_share, 1)}
        </span>
        <span className="pipeline-foot-item">
          <span className="dot" style={{ background: "var(--s2)" }} /> LLM {fmt.pct(split.llm_share, 1)}
        </span>
        <span className="pipeline-foot-item pipeline-foot-total">{fmt.ms(split.total_ms)} total</span>
      </div>
    </div>
  );
}

/* --------------------------------------------------------- processing -- */

export function SplitBar({ split }: { split: Split }) {
  const detPct = 1 - split.llm_share;
  return (
    <div>
      <div style={{ display: "flex", height: 30, borderRadius: 6, overflow: "hidden", gap: 2 }}>
        <div style={{ width: `${detPct * 100}%`, background: "var(--s1)" }} />
        <div style={{ width: `${split.llm_share * 100}%`, background: "var(--s2)", minWidth: 3 }} />
      </div>
      <div style={{ display: "flex", gap: 18, marginTop: 10, fontSize: 12 }}>
        <Key swatch="var(--s1)" label={`Deterministic ${fmt.pct(detPct, 1)} · ${fmt.ms(split.deterministic_ms)}`} />
        <Key swatch="var(--s2)" label={`LLM ${fmt.pct(split.llm_share, 1)} · ${fmt.ms(split.llm_ms)}`} />
      </div>
      <table className="data" style={{ marginTop: 14 }}>
        <thead>
          <tr><th>Stage</th><th style={{ textAlign: "right" }}>Time</th><th>Kind</th></tr>
        </thead>
        <tbody>
          {split.stages.map((s) => (
            <tr key={s.name}>
              <td>{s.name}</td>
              <td style={{ textAlign: "right" }}>{fmt.ms(s.ms)}</td>
              <td style={{ color: "var(--muted)" }}>{s.kind}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
