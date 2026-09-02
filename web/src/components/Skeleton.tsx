/**
 * Loading placeholders shaped like the content they stand in for.
 *
 * The point is layout stability: these reserve the same space the real cards
 * occupy, so nothing jumps when the data lands. A centred spinner reserves
 * nothing and every arrival becomes a reflow.
 */

export function SkeletonLine({ width = "100%", height = 11 }: { width?: string | number; height?: number }) {
  return <div className="skeleton skeleton-line" style={{ width, height }} />;
}

/** Mirrors `.kpi-card`: label, value, delta, then the sparkline floor. */
export function SkeletonKpiCard({ index = 0 }: { index?: number }) {
  return (
    <div className="kpi-card reveal" style={{ ["--i" as string]: index, paddingBottom: 0 }}>
      <div className="kpi-card-head"><SkeletonLine width="55%" height={10} /></div>
      <SkeletonLine width="70%" height={30} />
      <div style={{ marginTop: 12 }}><SkeletonLine width="45%" height={11} /></div>
      <div className="kpi-card-spark">
        <div className="skeleton" style={{ height: "100%", borderRadius: 0 }} />
      </div>
    </div>
  );
}

export function SkeletonKpiGrid({ count = 6 }: { count?: number }) {
  return (
    <>
      <div className="kpi-hero reveal" style={{ marginBottom: 16 }}>
        <div className="kpi-hero-left">
          <SkeletonLine width="40%" height={11} />
          <div style={{ marginTop: 14 }}><SkeletonLine width="75%" height={46} /></div>
          <div style={{ marginTop: 18 }}><SkeletonLine width="60%" /></div>
        </div>
        <div className="skeleton" style={{ height: 130, borderRadius: "var(--radius)" }} />
      </div>
      <div className="kpi-grid">
        {Array.from({ length: count }, (_, i) => <SkeletonKpiCard key={i} index={i + 1} />)}
      </div>
    </>
  );
}

/**
 * Mirrors the Investigate layout: side rail plus the story block, so the
 * two-column frame is already in place when the narrative lands.
 */
export function SkeletonInvestigate() {
  return (
    <div className="investigate-layout">
      <div className="investigate-rail">
        {Array.from({ length: 4 }, (_, i) => (
          <div key={i} style={{ padding: "9px 12px" }}><SkeletonLine width="70%" height={12} /></div>
        ))}
      </div>
      <div className="investigate-main">
        <div className="hero-band" style={{ borderBottom: "none" }}>
          <SkeletonLine width={220} height={40} />
        </div>
        <div style={{ marginTop: 26 }}>
          {[92, 100, 86, 96, 64].map((w, i) => (
            <div key={i} style={{ marginBottom: 12 }}><SkeletonLine width={`${w}%`} height={13} /></div>
          ))}
        </div>
        <div style={{ marginTop: 32 }}>
          <div className="skeleton" style={{ height: 168, borderRadius: "var(--radius-lg)" }} />
        </div>
      </div>
    </div>
  );
}

/** A generic panel placeholder for the wider cards below the KPI block. */
export function SkeletonCard({ lines = 4, index = 0 }: { lines?: number; index?: number }) {
  return (
    <div className="card reveal" style={{ ["--i" as string]: index }}>
      <div className="skeleton skeleton-title" />
      {Array.from({ length: lines }, (_, i) => (
        <SkeletonLine key={i} width={i === lines - 1 ? "60%" : "100%"} />
      ))}
    </div>
  );
}
