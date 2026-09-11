/**
 * Build-time configuration. `NEXT_PUBLIC_*` vars are inlined by Next, so these
 * must be read as full literal member expressions — no destructuring of
 * `process.env`.
 */

const rawBase = process.env.NEXT_PUBLIC_ARCHON_API ?? "http://localhost:8000";

/** Orchestrator origin, never with a trailing slash. */
export const API_BASE = rawBase.replace(/\/+$/, "");

/** When true, all network access is replaced by the in-browser fake in `src/mock`. */
export const IS_MOCK = process.env.NEXT_PUBLIC_ARCHON_MOCK === "1";

/** localStorage key holding the live-mode demo bearer token. */
export const TOKEN_STORAGE_KEY = "archon.demoToken";
