/**
 * Shared across the entry point and the shell.
 *
 * The bootstrap request is fired from main.tsx before React mounts, and the
 * shell needs the same values — importing App.tsx from main.tsx just to read
 * them would pull the whole component tree in ahead of the render.
 */

/** The week the contract is written against and the engine analyses. */
export const FOCAL_WEEK = "2026-W32";

/** The persona the workspace opens as. */
export const DEFAULT_PERSONA = "cfo";
