// Thin wrapper over the Learnova REST API.
// Vite proxies /api to the FastAPI server in dev (see vite.config.js).
//
// Every protected call carries Clerk's session JWT. `setTokenGetter` is
// installed once from App.jsx with Clerk's `getToken`, so callers never have
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

// ── Public ────────────────────────────────────────────────────────────────
export async function health() {
  return json(await fetch(`${BASE}/api/health`));
}

export async function listThemes() {
  return json(await fetch(`${BASE}/api/themes`));
}

// ── Jobs ──────────────────────────────────────────────────────────────────
export async function uploadDocument(file, textbookMode = false) {
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
  return json(
    await fetch(`${BASE}/api/jobs/${id}/generate`, {
      method: "POST",
      headers: await authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(options),
    })
  );
}

export async function getDeck(id) {
  return json(await fetch(`${BASE}/api/jobs/${id}/deck`, { headers: await authHeaders() }));
}

// ── Saved deck library ────────────────────────────────────────────────────
export async function listMyDecks() {
  return json(await fetch(`${BASE}/api/decks`, { headers: await authHeaders() }));
}

export async function getDeckMarkdown(deckId) {
  return json(
    await fetch(`${BASE}/api/decks/${deckId}/markdown`, { headers: await authHeaders() })
  );
}

export async function deleteDeck(deckId) {
  return json(
    await fetch(`${BASE}/api/decks/${deckId}`, {
      method: "DELETE",
      headers: await authHeaders(),
    })
  );
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
