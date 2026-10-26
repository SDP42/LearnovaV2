// Thin wrapper over the Learnova REST API.
// Vite proxies /api to the FastAPI server in dev (see vite.config.js).
//
// Every protected call carries the phone-login session token. `setTokenGetter`
// is installed once from App.jsx with the auth context's `getToken`, so callers never have
// to thread a token through by hand.

const BASE = "";

let getToken = async () => null;

export function setTokenGetter(fn) {
  getToken = fn;
}

async function authHeaders(extra = {}) {
  const token = await getToken();
  return token ? { ...extra, Authorization: `Bearer ${token}` } : extra;
}

async function json(response) {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* body was not JSON */
    }
    if (response.status === 401) detail = `Not signed in (${detail})`;
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

// ── Stale-while-revalidate cache (memory + sessionStorage, ~5 min TTL) ────
// Cached data is returned instantly; once older than the TTL it is refreshed
// in the background so the next call sees fresh data.
const TTL = 5 * 60 * 1000;
const mem = new Map();
const inflight = new Map();
const SS = "learnova-cache:";
function cacheGet(key) {
  if (mem.has(key)) return mem.get(key);
  try {
    const raw = sessionStorage.getItem(SS + key);
    if (raw) {
      const e = JSON.parse(raw);
      mem.set(key, e);
      return e;
    }
  } catch {
    /* storage unavailable */
  }
  return null;
}
function cacheSet(key, data) {
  const e = { t: Date.now(), data };
  mem.set(key, e);
  try {
    sessionStorage.setItem(SS + key, JSON.stringify(e));
  } catch {
    /* quota / disabled */
  }
}
/** Drop every cached key starting with one of the prefixes (all keys if none). */
export function invalidateCache(...prefixes) {
  const hit = (k) => !prefixes.length || prefixes.some((p) => k.startsWith(p));
  for (const [k, e] of [...mem]) {
    if (!hit(k)) continue;
    if (k.startsWith("blob:") && e.data) URL.revokeObjectURL(e.data);
    mem.delete(k);
  }
  try {
    for (const k of Object.keys(sessionStorage)) if (k.startsWith(SS) && hit(k.slice(SS.length))) sessionStorage.removeItem(k);
  } catch {
    /* ignore */
  }
}
const invalidateDeck = (id) => invalidateCache(`deck:${id}`, `analysis:${id}`, `blob:${id}`, "decks");
async function swr(key, fetcher, persist = true) {
  const hit = cacheGet(key);
  const refresh = () => {
    if (!inflight.has(key))
      inflight.set(
        key,
        fetcher()
          .then((d) => {
            persist ? cacheSet(key, d) : mem.set(key, { t: Date.now(), data: d });
            return d;
          })
          .finally(() => inflight.delete(key))
      );
    return inflight.get(key);
  };
  if (!hit) return refresh();
  if (Date.now() - hit.t > TTL) refresh().catch(() => {});
  return hit.data;
}

// ── Phone + OTP auth ──────────────────────────────────────────────────────
const post = async (url, body, token) =>
  json(
    await fetch(`${BASE}${url}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify(body),
    })
  );
export const requestOtp = (phone) => post("/api/auth/otp/request", { phone });
export const verifyOtp = (phone, code) => post("/api/auth/otp/verify", { phone, code });
export async function authMe(token) {
  return json(await fetch(`${BASE}/api/auth/me`, { headers: { Authorization: `Bearer ${token}` } }));
}
export async function saveProfile(profile) {
  return json(
    await fetch(`${BASE}/api/auth/profile`, {
      method: "PUT",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(profile),
    })
  );
}
export async function authLogout() {
  return json(await fetch(`${BASE}/api/auth/logout`, { method: "POST", headers: await authHeaders() }));
}

export async function deleteAccount() {
  return json(await fetch(`${BASE}/api/auth/account`, { method: "DELETE", headers: await authHeaders() }));
}
export async function logoutAll() {
  return json(await fetch(`${BASE}/api/auth/logout-all`, { method: "POST", headers: await authHeaders() }));
}

// First-party analytics + client error tracking (fire-and-forget, never throws).
export function track(name, props = {}) {
  authHeaders({ "Content-Type": "application/json" })
    .then((headers) =>
      fetch(`${BASE}/api/events`, { method: "POST", headers, body: JSON.stringify({ name, path: location.pathname, props }), keepalive: true })
    )
    .catch(() => {});
}
export function reportError(message, stack = "", source = "client") {
  authHeaders({ "Content-Type": "application/json" })
    .then((headers) =>
      fetch(`${BASE}/api/errors`, { method: "POST", headers, body: JSON.stringify({ message: String(message), stack: String(stack), path: location.pathname, source }), keepalive: true })
    )
    .catch(() => {});
}

// ── Public ────────────────────────────────────────────────────────────────
export async function health() {
  return json(await fetch(`${BASE}/api/health`));
}

export async function listThemes() {
  return json(await fetch(`${BASE}/api/themes`));
}

export async function getConfig() {
  return json(await fetch(`${BASE}/api/config`));
}

// ── Jobs ──────────────────────────────────────────────────────────────────
export async function uploadDocument(file, textbookMode = false) {
  invalidateCache();
  const form = new FormData();
  form.append("file", file);
  form.append("textbook_mode", String(textbookMode));
  return json(
    await fetch(`${BASE}/api/jobs`, {
      method: "POST",
      headers: await authHeaders(),
      body: form,
    })
  );
}

export async function createTypedJob(text, title) {
  invalidateCache();
  return json(
    await fetch(`${BASE}/api/jobs/typed`, {
      method: "POST",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ text, title }),
    })
  );
}

export async function getJob(id) {
  return json(await fetch(`${BASE}/api/jobs/${id}`, { headers: await authHeaders() }));
}

export async function getMarkdown(id) {
  return json(
    await fetch(`${BASE}/api/jobs/${id}/markdown`, { headers: await authHeaders() })
  );
}

export async function saveMarkdown(id, markdown) {
  return json(
    await fetch(`${BASE}/api/jobs/${id}/markdown`, {
      method: "PUT",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ markdown }),
    })
  );
}

export async function startGenerate(id, options) {
  invalidateDeck(id);
  return json(
    await fetch(`${BASE}/api/jobs/${id}/generate`, {
      method: "POST",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(options),
    })
  );
}

export function getDeck(id) {
  return swr(`deck:${id}`, async () => {
    // A fresh generation is a live job; a deck opened from the library is not.
    const h = await authHeaders();
    const jobResp = await fetch(`${BASE}/api/jobs/${id}/deck`, { headers: h });
    if (jobResp.ok) return jobResp.json();
    return json(await fetch(`${BASE}/api/decks/${id}/deck`, { headers: h }));
  });
}

/** Before/after analysis for a deck; rejects with an Error whose .status is 404 when none exists. */
export function getAnalysis(id) {
  return swr(`analysis:${id}`, async () => {
    const h = await authHeaders();
    let r = await fetch(`${BASE}/api/decks/${id}/analysis`, { headers: h });
    if (!r.ok) r = await fetch(`${BASE}/api/jobs/${id}/analysis`, { headers: h });
    if (r.status === 404) throw Object.assign(new Error("No analysis for this deck"), { status: 404 });
    return json(r);
  });
}

// ── Saved deck library ────────────────────────────────────────────────────
export function listMyDecks() {
  return swr("decks", async () => json(await fetch(`${BASE}/api/decks`, { headers: await authHeaders() })));
}

export async function getDeckMarkdown(deckId) {
  return json(
    await fetch(`${BASE}/api/decks/${deckId}/markdown`, { headers: await authHeaders() })
  );
}

export async function deleteDeck(deckId) {
  const r = await json(
    await fetch(`${BASE}/api/decks/${deckId}`, {
      method: "DELETE",
      headers: await authHeaders(),
    })
  );
  invalidateDeck(deckId);
  return r;
}

// ── Deck editor ───────────────────────────────────────────────────────────
export async function getEditableSlides(deckId) {
  return json(
    await fetch(`${BASE}/api/decks/${deckId}/editable`, { headers: await authHeaders() })
  );
}

export async function saveDeckSlides(deckId, slides, note = "edited") {
  return json(
    await fetch(`${BASE}/api/decks/${deckId}/slides`, {
      method: "PUT",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ slides, note }),
    })
  ).finally(() => invalidateDeck(deckId));
}

export async function restoreDeckVersion(deckId, v) {
  return json(
    await fetch(`${BASE}/api/decks/${deckId}/versions/${v}/restore`, {
      method: "POST",
      headers: await authHeaders(),
    })
  ).finally(() => invalidateDeck(deckId));
}

export async function slideImageUrl(deckId, slide) {
  const r = await fetch(`${BASE}/api/decks/${deckId}/images/${slide}`, {
    headers: await authHeaders(),
  });
  if (!r.ok) throw new Error(`No figure (${r.status})`);
  return URL.createObjectURL(await r.blob());
}

export async function saveSlideImage(deckId, slide, blob) {
  const r = await fetch(`${BASE}/api/decks/${deckId}/images/${slide}`, {
    method: "PUT",
    headers: await authHeaders({ "Content-Type": blob.type || "image/png" }),
    body: blob,
  });
  invalidateDeck(deckId);
  return json(r);
}

/**
 * Downloads must carry the Authorization header, so a plain <a href> will not
 * work — fetch the bytes, then hand the browser a temporary object URL.
 */
export async function downloadArtifact(path, filename) {
  const response = await fetch(`${BASE}${path}`, { headers: await authHeaders() });
  if (!response.ok) {
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

// ── Assistant ─────────────────────────────────────────────────────────────
export async function assistantQuery(text, sessionId = "app") {
  return json(
    await fetch(`${BASE}/api/assistant/query`, {
      method: "POST",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ text, session_id: sessionId }),
    })
  );
}

export async function assistantRegistry() {
  return json(
    await fetch(`${BASE}/api/assistant/registry`, { headers: await authHeaders() })
  );
}

// ── Gallery ───────────────────────────────────────────────────────────────
export async function galleryList({ subject, category, q, ready, limit = 120, offset = 0 } = {}) {
  const p = new URLSearchParams();
  if (subject) p.set("subject", subject);
  if (category) p.set("category", category);
  if (q) p.set("q", q);
  if (ready) p.set("ready", "true");
  p.set("limit", limit);
  p.set("offset", offset);
  return json(await fetch(`${BASE}/api/gallery?${p}`));
}

export async function galleryEntry(slug) {
  return json(await fetch(`${BASE}/api/gallery/${slug}`));
}

export async function galleryDeck(slug) {
  return json(await fetch(`${BASE}/api/gallery/${slug}/deck`));
}

export const galleryDownloadPath = (slug, artifact) => `/api/gallery/${slug}/download/${artifact}`;

export async function galleryUse(slug) {
  return json(
    await fetch(`${BASE}/api/gallery/${slug}/use`, {
      method: "POST",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ slug }),
    })
  );
}

export const jobDownloadPath = (id, artifact) => `/api/jobs/${id}/download/${artifact}`;
export const deckDownloadPath = (id, artifact) => `/api/decks/${id}/download/${artifact}`;

/**
 * Fetch an artifact (with the Authorization header) and return an object URL,
 * for use as an <iframe src>. Caller must URL.revokeObjectURL() when done.
 */
export async function artifactObjectUrl(path) {
  const response = await fetch(`${BASE}${path}`, { headers: await authHeaders() });
  if (!response.ok) throw new Error(`Could not load preview (${response.status})`);
  return URL.createObjectURL(await response.blob());
}

/**
 * Object URL for a deck artifact by id, trying the live-job path then the
 * saved-library path. Cached per deck id (revoked on invalidation), so callers
 * must NOT revoke it.
 */
export function deckArtifactUrl(id, artifact) {
  return swr(
    `blob:${id}:${artifact}`,
    async () => {
      const h = await authHeaders();
      for (const path of [`/api/jobs/${id}/download/${artifact}`, `/api/decks/${id}/download/${artifact}`]) {
        const r = await fetch(`${BASE}${path}`, { headers: h });
        if (r.ok) return URL.createObjectURL(await r.blob());
      }
      throw new Error("Could not load the presentation");
    },
    false
  );
}

// ── Deck thumbnails (auth-required PNG → cached blob URL) ─────────────────
/** Resolves to an object URL for the deck's thumbnail. Cached; never revoke. */
export function getDeckThumb(id) {
  return swr(
    `blob:${id}:thumb`,
    async () => {
      const r = await fetch(`${BASE}/api/decks/${id}/thumb`, { headers: await authHeaders() });
      if (!r.ok) throw new Error(`No thumbnail (${r.status})`);
      return URL.createObjectURL(await r.blob());
    },
    false
  );
}

// ── AI assist ─────────────────────────────────────────────────────────────
export async function assistStatus() {
  return json(await fetch(`${BASE}/api/assist/status`, { headers: await authHeaders() }));
}
/** → {text, llm, hints[]} */
export async function assistPrompt(text) {
  return json(
    await fetch(`${BASE}/api/assist/prompt`, {
      method: "POST",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ text }),
    })
  );
}
/** → {title, bullets}; rejects with an Error whose .status is the HTTP status (503 = AI not configured). */
export async function assistSlide({ title, bullets, instruction, audience }) {
  const r = await fetch(`${BASE}/api/assist/slide`, {
    method: "POST",
    headers: await authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ title, bullets, instruction, audience }),
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw Object.assign(new Error(typeof detail === "string" ? detail : "Request failed"), { status: r.status });
  }
  return r.json();
}

// ── Deck tutor (persona chat grounded in one deck) ────────────────────────
export const tutorPersonas = () => swr("tutor:personas", async () => json(await fetch(`${BASE}/api/tutor/personas`, { headers: await authHeaders() })));
/** → {answer, sources:[{slide,title}], mode, persona, quiz?} */
export async function tutorChat(deckId, message, persona, history = []) {
  return json(
    await fetch(`${BASE}/api/decks/${deckId}/chat`, {
      method: "POST",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({ message, persona, history }),
    })
  );
}
