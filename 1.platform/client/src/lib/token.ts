import { TOKEN_STORAGE_KEY } from "./env";

/** Reads the live-mode demo token. Returns `null` on the server or if unset. */
export function readDemoToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(TOKEN_STORAGE_KEY);
    return value && value.trim().length > 0 ? value.trim() : null;
  } catch {
    return null;
  }
}

export function writeDemoToken(token: string): void {
  if (typeof window === "undefined") return;
  try {
    const trimmed = token.trim();
    if (trimmed.length === 0) {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY);
    } else {
      window.localStorage.setItem(TOKEN_STORAGE_KEY, trimmed);
    }
    window.dispatchEvent(new Event("archon:token-changed"));
  } catch {
    /* storage disabled — live mode simply stays unavailable */
  }
}
