// Service Worker: macht den Mund zu Mund Kalender offline-fähig (PWA).
// Strategie: network-first mit Cache-Fallback -- online immer frisch,
// offline die zuletzt geladene Version.

const CACHE = "ek-v8";
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
  // Splash-Assets vorab cachen, damit der Ladescreen zuverlässig erscheint.
  "splash/title0-top.webp", "splash/title0-bottom.webp",
  "splash/title1-top.webp", "splash/title1-bottom.webp",
  "splash/title2-top.webp", "splash/title2-bottom.webp",
  "splash/title3-top.webp", "splash/title3-bottom.webp",
  "splash/mouth0.webp", "splash/mouth1.webp", "splash/mouth2.webp",
  "splash/mouth3.webp", "splash/mouth4.webp", "splash/mouth5.webp",
  "splash/mouth6.webp", "splash/mouth7.webp", "splash/mouth8.webp",
  "splash/mouth9.webp", "splash/mouth10.webp", "splash/mouth11.webp",
  "splash/mouth12.webp", "splash/mouth13.webp", "splash/mouth14.webp",
  "splash/mouth15.webp", "splash/mouth16.webp",
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
