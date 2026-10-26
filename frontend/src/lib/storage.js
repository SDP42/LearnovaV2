// Tiny wrappers so a blocked / full / private-mode localStorage never throws.
// Only for per-viewer conveniences (remembered defaults, view mode) — nothing
// that must persist reliably lives here.
export function readPref(key, fallback = null) {
  try {
    const v = localStorage.getItem(key);
    return v == null ? fallback : v;
  } catch {
    return fallback;
  }
}

export function writePref(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* storage unavailable */
  }
}
