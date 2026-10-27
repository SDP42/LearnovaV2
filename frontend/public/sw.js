// Learnova service worker: the app shell works offline; API calls always go to the network.
const SHELL = "learnova-shell-v1";
const PRECACHE = ["/", "/manifest.webmanifest", "/learnova-mark.svg", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)))).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api/")) return;
  if (req.mode === "navigate") {
    // pages: network first, fall back to the cached shell when offline
    event.respondWith(fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(SHELL).then((c) => c.put("/", copy));
      return res;
    }).catch(() => caches.match("/")));
    return;
  }
  if (url.pathname.startsWith("/assets/")) {
    // hashed build files never change: cache first
    event.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((res) => {
      const copy = res.clone();
      caches.open(SHELL).then((c) => c.put(req, copy));
      return res;
    })));
  }
});
