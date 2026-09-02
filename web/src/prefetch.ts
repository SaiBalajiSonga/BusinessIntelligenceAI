import { api, peek } from "./api";

/**
 * Warm the caches for pages the viewer has not opened yet.
 *
 * The request cache already makes going *back* to a page instant. This is
 * about the first visit: by the time someone clicks "Investigate", the
 * analysis behind it can already be in memory.
 *
 * Two constraints shape how this runs, and both come from the backend being a
 * serverless function rather than a warm server:
 *
 *  - It must never compete with the page in front of the viewer. Every one of
 *    these endpoints costs real CPU on the server, and on a cold container
 *    that CPU is the same CPU the current page is waiting on. So prefetching
 *    starts only once the browser reports itself idle, and after a delay long
 *    enough for the current page to have finished asking for its own data.
 *
 *  - Requests go one at a time. Firing them in parallel would hand the
 *    container several concurrent analyses to run, which under the GIL makes
 *    all of them slower — including whatever the viewer does next.
 *
 * Anything already cached is skipped, so this costs nothing on a revisit, and
 * failures are swallowed: a prefetch that does not arrive is not an error the
 * viewer should ever hear about.
 */

type Task = { done: () => boolean; run: () => Promise<unknown> };

/** The focal scenario Investigate opens on, and the contract the system page needs. */
function tasks(week: string, persona: string): Task[] {
  return [
    // Investigate's first scenario — the heaviest page, and the most likely
    // next click from the overview.
    { done: () => !!peek.insight(week, "cfo"), run: () => api.insight(week, "cfo") },
    { done: () => !!peek.narrative(week, "cfo"), run: () => api.narrative(week, "cfo") },
    { done: () => !!peek.attribution(week, "cfo"), run: () => api.attribution(week, "cfo") },
    { done: () => !!peek.actions(week, "cfo"), run: () => api.actions(week, "cfo") },
    // System & Learning.
    { done: () => !!peek.contract(), run: () => api.contract() },
    { done: () => !!peek.listFeedback(), run: () => api.listFeedback() },
    { done: () => !!peek.learning(week, persona), run: () => api.learning(week, persona) },
  ];
}

const whenIdle: (cb: () => void) => void =
  typeof window !== "undefined" && "requestIdleCallback" in window
    ? (cb) => (window as any).requestIdleCallback(cb, { timeout: 4000 })
    : (cb) => window.setTimeout(cb, 1200);

let started = false;

/**
 * Idempotent: the shell may mount more than once in development, and a second
 * pass would only re-walk an already-warm list.
 */
export function prefetchRoutes(week: string, persona: string, delayMs = 2500): () => void {
  if (started) return () => {};
  started = true;

  let cancelled = false;
  const timer = window.setTimeout(() => {
    whenIdle(async () => {
      for (const task of tasks(week, persona)) {
        if (cancelled) return;
        if (task.done()) continue;
        try {
          await task.run();
        } catch {
          /* a prefetch is best-effort by definition */
        }
      }
    });
  }, delayMs);

  return () => {
    cancelled = true;
    window.clearTimeout(timer);
    started = false;
  };
}
