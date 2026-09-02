import { useId, useMemo } from "react";

/**
 * A KPI's measured weekly history.
 *
 * Every point is a real value from `/v1/series` — the same series the baseline
 * is fitted on. There is no smoothing, no interpolation and no invented tail:
 * if the warehouse holds eight weeks, eight weeks are drawn. With fewer than
 * two points there is no line to draw, so this renders nothing rather than a
 * flat stub that would imply a stable history.
 *
 * The drawing stretches to whatever width the card ends up at via a fixed
 * viewBox and `preserveAspectRatio="none"`, which avoids measuring the DOM.
 * The trade-off is that the coordinate system scales non-uniformly, so
 * anything that must stay round — the last-point marker — is positioned as
 * HTML over the top rather than drawn as an SVG circle, which would smear
 * into an ellipse.
 */

interface Props {
  points: number[];
  /** Drives the stroke and fill. */
  tone?: "pos" | "neg" | "brand" | "neutral";
  height?: number;
  /** Marks where the expectation sat, so the gap is shown rather than stated. */
  expected?: number | null;
  showDot?: boolean;
  animate?: boolean;
  className?: string;
}

const TONE_VAR: Record<string, string> = {
  pos: "var(--pos)",
  neg: "var(--neg)",
  brand: "var(--brand)",
  neutral: "var(--muted)",
};

export default function Sparkline({
  points, tone = "neutral", height = 46, expected = null,
  showDot = true, animate = true, className = "",
}: Props) {
  const gradientId = useId();
  const stroke = TONE_VAR[tone] ?? TONE_VAR.neutral;

  const geometry = useMemo(() => {
    if (points.length < 2) return null;

    const W = 100;
    const H = 100;
    const pad = 10;

    const candidates = expected == null ? points : [...points, expected];
    const lo = Math.min(...candidates);
    const hi = Math.max(...candidates);
    const span = hi - lo || Math.abs(hi) || 1;   // a flat series still needs a mid-line

    const y = (v: number) => H - pad - ((v - lo) / span) * (H - pad * 2);
    const x = (i: number) => (i / (points.length - 1)) * W;

    const coords = points.map((v, i) => [x(i), y(v)] as const);
    const line = coords.map(([px, py], i) => `${i ? "L" : "M"}${px.toFixed(2)},${py.toFixed(2)}`).join("");
    const last = coords[coords.length - 1];

    return {
      line,
      area: `${line}L${W},${H}L0,${H}Z`,
      expectedY: expected == null ? null : y(expected),
      // Percentages for the HTML marker laid over the stretched drawing.
      dotLeft: last[0],
      dotTop: last[1],
      // Only needs to exceed the true path length for the draw-on to start hidden.
      length: Math.round(W * 2),
    };
  }, [points, expected]);

  if (!geometry) return null;

  return (
    <div className={`spark-wrap ${className}`} style={{ height }}>
      <svg
        className="spark"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        style={{ height }}
        aria-hidden="true"
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity="0.24" />
            <stop offset="100%" stopColor={stroke} stopOpacity="0" />
          </linearGradient>
        </defs>

        <path d={geometry.area} fill={`url(#${gradientId})`} />

        {geometry.expectedY !== null && (
          <line
            x1="0" x2="100" y1={geometry.expectedY} y2={geometry.expectedY}
            stroke="var(--muted)" strokeWidth="1"
            strokeDasharray="3 3" vectorEffect="non-scaling-stroke"
            opacity="0.65"
          />
        )}

        <path
          d={geometry.line}
          className={`spark-line${animate ? " animate" : ""}`}
          stroke={stroke}
          vectorEffect="non-scaling-stroke"
          style={animate ? {
            ["--dash" as string]: geometry.length,
            strokeDasharray: geometry.length,
          } : undefined}
        />
      </svg>

      {showDot && (
        <span
          className="spark-dot"
          style={{
            left: `${geometry.dotLeft}%`,
            top: `${geometry.dotTop}%`,
            background: stroke,
          }}
        />
      )}
    </div>
  );
}
