// Service Worker: macht den Eventkalender offline-fähig (PWA).
// Strategie: network-first mit Cache-Fallback -- online immer frisch,
// offline die zuletzt geladene Version.

const CACHE = "ek-v3";
const SHELL = [
  "./",
  "index.html",
  "app.js",
  "style.css",
  "site.webmanifest",
  "data/events.json",
  "icons/favicon-32.png",
  "icons/apple-touch-icon.png",
  "icons/icon-192.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return; // fremde Bilder etc. nicht abfangen

  // Network-first, but bypass the browser's HTTP cache so a reload always
  // gets the freshest version online; fall back to the cache only offline.
  e.respondWith(
    fetch(req, { cache: "no-store" })
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(req, copy)).catch(() => {});
        return res;
      })
      .catch(() => caches.match(req).then((c) => c || caches.match("index.html")))
  );
});
