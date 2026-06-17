"use strict";

// Loads the generated feed (data/events.json) and renders it grouped by
// day, with category + genre filters, search, favourites, a detail modal,
// calendar export and sharing. No build step, no framework.

const GENRE_ORDER = ["Kultur", "Polit", "Queer", "Kink"];
// Reihenfolge der Kategorie-Chips im Header (überall gleich).
const CATEGORY_ORDER = ["Theater", "Kino", "Konzert", "Party", "Vortrag",
  "Ausstellung", "Workshop", "Protest", "Essen", "Sonstiges"];
// Reihenfolge der Kategorie-Kästen, wenn nach Kategorie/Genre sortiert wird.
const SORT_CATEGORY_ORDER = ["Vortrag", "Ausstellung", "Workshop", "Protest",
  "Essen", "Theater", "Kino", "Konzert", "Party", "Sonstiges"];
// Die zwölf Berliner Bezirke (für die Reihenfolge im Filter).
const BEZIRK_ORDER = [
  "Mitte", "Friedrichshain-Kreuzberg", "Pankow",
  "Charlottenburg-Wilmersdorf", "Spandau", "Steglitz-Zehlendorf",
  "Tempelhof-Schöneberg", "Neukölln", "Treptow-Köpenick",
  "Marzahn-Hellersdorf", "Lichtenberg", "Reinickendorf",
];
const BEZIRK_UNKNOWN = "Unbekannt";
const FAV_KEY = "ek_favorites";
const THEME_KEY = "ek_theme";
const SOURCES_KEY = "ek_disabled_sources";
const BEZIRKE_KEY = "ek_disabled_bezirke";
const VIEW_KEY = "ek_view";
const SORT_KEY = "ek_sort";  // "time" | "category" | "genre"
// Tage in die Zukunft, die der Feed zeigt (muss zu aggregate.py passen).
// Wird gebraucht, um laufende Ausstellungen an jedem Tag einzublenden.
const HORIZON_DAYS = 14;
// Formspree-Endpoint für Quellen-Vorschläge.
const WISH_ENDPOINT = "https://formspree.io/f/xjgdlbnl";

// Quellenname für Events, die Nutzer*innen selbst hinzufügen.
const MINE_SOURCE = "Eigene Events";
// Firebase Realtime Database (Speicher für selbst eingetragene Events).
// Solange leer, ist das Hinzufügen eigener Events deaktiviert.
const FIREBASE_DB_URL =
  "https://eventkalender-80e69-default-rtdb.europe-west1.firebasedatabase.app";

const state = {
  events: [],
  userEvents: [],
  allSources: [],
  activeTags: new Set(),
  activeGenres: new Set(),
  query: "",
  onlyFav: false,
  favorites: loadFavorites(),
  disabledSources: loadDisabledSources(),
  disabledKdCats: loadSet("ek_disabled_kdcats"),
  disabledBezirke: loadSet(BEZIRKE_KEY),
  viewMode: (localStorage.getItem(VIEW_KEY) === "map") ? "map" : "list",
  sortMode: (["time", "category", "genre"].includes(localStorage.getItem(SORT_KEY)))
    ? localStorage.getItem(SORT_KEY) : "category",
  mapDay: null,
};

const KD_SOURCE = "kulturdaten.berlin";
const KD_LABELS = {
  Music: "Musik", Stages: "Bühne", Dance: "Tanz", Festivals: "Festivals",
  Exhibitions: "Ausstellungen", Art: "Kunst",
};

const els = {
  feed: document.getElementById("feed"),
  status: document.getElementById("status"),
  splash: document.getElementById("splash"),
  search: document.getElementById("search"),
  tagFilter: document.getElementById("tag-filter"),
  genreFilter: document.getElementById("genre-filter"),
  favToggle: document.getElementById("fav-toggle"),
  footer: document.getElementById("footer-note"),
  dayTabs: document.getElementById("day-tabs"),
  searchToggle: document.getElementById("search-toggle"),
  catExpand: document.getElementById("cat-expand"),
  modalBackdrop: document.getElementById("modal-backdrop"),
  modal: document.getElementById("modal"),
  modalContent: document.getElementById("modal-content"),
  modalClose: document.getElementById("modal-close"),
  settingsOpen: document.getElementById("settings-open"),
  settingsBackdrop: document.getElementById("settings-backdrop"),
  settingsClose: document.getElementById("settings-close"),
  themeOptions: document.getElementById("theme-options"),
  sortOptions: document.getElementById("sort-options"),
  sourceToggles: document.getElementById("source-toggles"),
  kdcatSection: document.getElementById("kdcat-section"),
  kdcatToggles: document.getElementById("kdcat-toggles"),
  bezirkToggles: document.getElementById("bezirk-toggles"),
  wishText: document.getElementById("wish-text"),
  wishSend: document.getElementById("wish-send"),
  installBtn: document.getElementById("install-btn"),
  installHelp: document.getElementById("install-help"),
  viewList: document.getElementById("view-list"),
  viewMap: document.getElementById("view-map"),
  mapView: document.getElementById("map-view"),
  mineForm: document.getElementById("mine-form"),
  mineTitle: document.getElementById("mine-title"),
  mineDate: document.getElementById("mine-date"),
  mineTime: document.getElementById("mine-time"),
  mineLocation: document.getElementById("mine-location"),
  mineAddress: document.getElementById("mine-address"),
  mineCategory: document.getElementById("mine-category"),
  mineGenre: document.getElementById("mine-genre"),
  mineDesc: document.getElementById("mine-desc"),
  mineLink: document.getElementById("mine-link"),
  mineSend: document.getElementById("mine-send"),
  mineHint: document.getElementById("mine-hint"),
};

const DAY_FMT = new Intl.DateTimeFormat("de-DE", {
  weekday: "long", day: "numeric", month: "long", year: "numeric",
});
const TIME_FMT = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
const CARD_DATE_FMT = new Intl.DateTimeFormat("de-DE", {
  weekday: "short", day: "numeric", month: "numeric",
});
// End date of a multi-day run (e.g. exhibitions): "bis 09.08.2026".
const END_FMT = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit", month: "2-digit", year: "numeric",
});
const TAB_DOW_FMT = new Intl.DateTimeFormat("de-DE", { weekday: "short" });
const TAB_DATE_FMT = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric" });

let dayObserver = null;
let searchDebounce = null;
let settingsRenderPending = false;
let deferredInstallPrompt = null;

// While the settings overlay is open the feed is hidden behind it, so a full
// re-render on every source/Bezirk toggle is wasted work -> defer it to close.
function scheduleRender() {
  if (els.settingsBackdrop && !els.settingsBackdrop.hasAttribute("hidden")) {
    settingsRenderPending = true;
  } else {
    render();
  }
}

// Android-Chrome: Install-Dialog für später merken.
window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
});

// Offline-Fähigkeit (PWA) + automatische Updates.
if ("serviceWorker" in navigator) {
  const hadController = !!navigator.serviceWorker.controller;
  // Wenn ein neuer Service Worker übernimmt (neue Version veröffentlicht),
  // die Seite einmal neu laden -- sonst hängt die alte Version, bis die App
  // komplett geschlossen wird.
  let swReloaded = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (hadController && !swReloaded) { swReloaded = true; location.reload(); }
  });
  window.addEventListener("load", async () => {
    try {
      const reg = await navigator.serviceWorker.register("sw.js",
        { updateViaCache: "none" });
      // Beim Zurückkehren in die App nach Updates suchen.
      document.addEventListener("visibilitychange", () => {
        if (!document.hidden) reg.update().catch(() => {});
      });
    } catch { /* ignore */ }
  });
}

// Ladebildschirm ausblenden (sanft) -- aufgerufen sobald der Feed steht,
// aber immer erst nach mindestens 2 Sekunden Anzeigedauer.
let splashHiding = false;
const SPLASH_MIN_MS = 2000;
function hideSplash() {
  const s = els.splash;
  if (!s || splashHiding) return;
  splashHiding = true;
  const elapsed = Date.now() - (window.__splashStart || Date.now());
  setTimeout(() => {
    s.classList.add("hide");
    setTimeout(() => s.remove(), 600);
  }, Math.max(0, SPLASH_MIN_MS - elapsed));
}
// Notbremse: nie länger als 9s hängen bleiben, falls etwas klemmt.
setTimeout(hideSplash, 9000);

init();

// iOS-PWA & Tab-Wechsel: beim Sichtbarwerden / Online-Gehen den Feed neu laden,
// damit man nicht erst die App komplett schließen muss.
let lastFeedLoad = 0;
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) refreshFeed();
});
window.addEventListener("online", () => refreshFeed(true));

async function refreshFeed(force = false) {
  if (!state.baseEvents) return;            // initial load not done yet
  if (!force && Date.now() - lastFeedLoad < 30000) return;
  try {
    const res = await fetch("data/events.json", { cache: "no-store" });
    if (!res.ok) return;
    const data = await res.json();
    state.baseEvents = Array.isArray(data.events) ? data.events : [];
    state.allSources = Array.isArray(data.sources)
      ? data.sources.map((s) => s && s.source).filter(Boolean) : [];
    updateMeta(data);
    await loadUserEvents();
    mergeEvents();
    render();
    lastFeedLoad = Date.now();
  } catch { /* offline -> keep what we have */ }
}

async function init() {
  try {
    const res = await fetch("data/events.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.baseEvents = Array.isArray(data.events) ? data.events : [];
    // All configured sources (from the report), so even sources with zero
    // current events still show up in the Quellen list.
    state.allSources = Array.isArray(data.sources)
      ? data.sources.map((s) => s && s.source).filter(Boolean) : [];
    updateMeta(data);
    await loadUserEvents();
    mergeEvents();
    applyViewMode();
    buildGenreFilter();
    buildTagFilter();
    render();
    openSharedEvent();
    lastFeedLoad = Date.now();
  } catch (err) {
    els.status.textContent =
      "Konnte den Veranstaltungs-Feed nicht laden. (" + err.message + ")";
  } finally {
    hideSplash();
  }

  els.search.addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    // Debounce: re-render at most ~every 160ms while typing (590 cards).
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      if (q === state.query) return;
      state.query = q;
      render();
    }, 160);
  });

  els.searchToggle.addEventListener("click", () => {
    const open = els.search.hasAttribute("hidden");
    els.search.toggleAttribute("hidden", !open);
    els.dayTabs.toggleAttribute("hidden", open); // Tabs weichen der Suche
    if (open) {
      els.search.focus();
    } else {
      els.search.value = "";
      state.query = "";
      render();
    }
    els.searchToggle.setAttribute("aria-expanded", String(open));
  });

  // Kategorien auf-/zuklappen (Scroll-Zeile <-> alle anzeigen).
  els.catExpand.addEventListener("click", () => {
    const expanded = els.tagFilter.classList.toggle("expanded");
    els.catExpand.setAttribute("aria-expanded", String(expanded));
  });

  els.favToggle.addEventListener("click", () => {
    state.onlyFav = !state.onlyFav;
    els.favToggle.setAttribute("aria-pressed", String(state.onlyFav));
    render();
  });

  // Ansicht umschalten: Liste <-> Karte.
  els.viewList.addEventListener("click", () => setViewMode("list"));
  els.viewMap.addEventListener("click", () => setViewMode("map"));

  // Eigenes Event hinzufügen.
  if (els.mineForm) {
    els.mineForm.addEventListener("submit", submitOwnEvent);
  }

  // Modal close handlers.
  els.modalClose.addEventListener("click", closeModal);
  els.modalBackdrop.addEventListener("click", (e) => {
    if (e.target === els.modalBackdrop) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeModal(); closeSettings(); }
  });
  // Browser back/forward and externally opened #e/<id> links open/close the
  // matching event without a page reload.
  window.addEventListener("hashchange", routeFromHash);

  setupSettings();
}

// ---------------- Settings ----------------

function setupSettings() {
  els.settingsOpen.addEventListener("click", openSettings);
  els.settingsClose.addEventListener("click", closeSettings);
  els.settingsBackdrop.addEventListener("click", (e) => {
    if (e.target === els.settingsBackdrop) closeSettings();
  });

  // Theme buttons.
  const current = localStorage.getItem(THEME_KEY) || "buergi";
  for (const btn of els.themeOptions.querySelectorAll(".theme-btn")) {
    btn.classList.toggle("active", btn.dataset.theme === current);
    btn.addEventListener("click", () => setTheme(btn.dataset.theme));
  }

  // Sort buttons (Uhrzeit / Kategorie / Genre).
  for (const btn of els.sortOptions.querySelectorAll(".sort-btn")) {
    btn.classList.toggle("active", btn.dataset.sort === state.sortMode);
    btn.addEventListener("click", () => setSortMode(btn.dataset.sort));
  }

  // "Als App hinzufügen": Android-Chrome bietet den nativen Dialog,
  // sonst (iPhone) zeigen wir die Anleitung.
  els.installBtn.addEventListener("click", async () => {
    if (deferredInstallPrompt) {
      deferredInstallPrompt.prompt();
      deferredInstallPrompt = null;
    }
    els.installHelp.toggleAttribute("hidden");
  });

  // Source wishes -> form service (no login). Set WISH_ENDPOINT below.
  els.wishSend.addEventListener("click", async () => {
    const text = (els.wishText.value || "").trim();
    if (!text) { els.wishText.focus(); return; }
    if (!WISH_ENDPOINT) { toast("Versand noch nicht eingerichtet"); return; }
    els.wishSend.disabled = true;
    try {
      const res = await fetch(WISH_ENDPOINT, {
        method: "POST",
        headers: { "Accept": "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ vorschlag: text }),
      });
      if (res.ok) { els.wishText.value = ""; toast("Danke! Vorschlag gesendet."); }
      else { toast("Konnte nicht senden."); }
    } catch { toast("Konnte nicht senden."); }
    els.wishSend.disabled = false;
  });
}

const THEME_COLORS = {
  buergi: "#f3e9d8", punk: "#0b0a0d", diy: "#d8d3c6", hyperpop: "#ffe0fb",
};

function setSortMode(mode) {
  state.sortMode = mode;
  try { localStorage.setItem(SORT_KEY, mode); } catch { /* ignore */ }
  for (const btn of els.sortOptions.querySelectorAll(".sort-btn")) {
    btn.classList.toggle("active", btn.dataset.sort === mode);
  }
  render();
}

function setTheme(theme) {
  if (theme === "buergi") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta && THEME_COLORS[theme]) meta.setAttribute("content", THEME_COLORS[theme]);
  for (const btn of els.themeOptions.querySelectorAll(".theme-btn")) {
    btn.classList.toggle("active", btn.dataset.theme === theme);
  }
}

function buildSourceToggles() {
  // Count only events that would land in the feed given every OTHER filter,
  // so the badge matches what's actually shown -- not the grand total.
  const counts = new Map();
  // Seed with every configured source so sources with zero current events
  // (e.g. Klub Verboten when nothing is on) still appear in the list.
  for (const src of state.allSources) counts.set(src, 0);
  for (const e of state.events) {
    if (!e.source_name) continue;
    if (!counts.has(e.source_name)) counts.set(e.source_name, 0);
    if (matches(e, { source: true })) {
      counts.set(e.source_name, counts.get(e.source_name) + 1);
    }
  }
  // Dominant genre per source (for grouping + colouring the counter).
  const tally = new Map();
  for (const e of state.events) {
    if (!e.source_name || !e.genre) continue;
    let g = tally.get(e.source_name);
    if (!g) { g = {}; tally.set(e.source_name, g); }
    g[e.genre] = (g[e.genre] || 0) + 1;
  }
  const srcGenre = new Map();
  for (const [src, g] of tally) {
    srcGenre.set(src, Object.entries(g).sort((a, b) => b[1] - a[1])[0][0]);
  }
  const genreRank = (src) => {
    const i = GENRE_ORDER.indexOf(srcGenre.get(src));
    return i < 0 ? GENRE_ORDER.length : i;
  };

  // "Eigene Events" stays on top; rest grouped by genre, then by count.
  if (!counts.has(MINE_SOURCE)) counts.set(MINE_SOURCE, 0);
  const sources = [...counts.keys()].sort((a, b) => {
    if (a === MINE_SOURCE) return -1;
    if (b === MINE_SOURCE) return 1;
    return genreRank(a) - genreRank(b) ||
      (counts.get(b) - counts.get(a)) || a.localeCompare(b, "de");
  });

  els.sourceToggles.innerHTML = "";
  for (const src of sources) {
    const label = document.createElement("label");
    label.className = "source-toggle";
    if (src === MINE_SOURCE) label.classList.add("source-toggle--mine");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !state.disabledSources.has(src);
    cb.addEventListener("change", () => {
      if (cb.checked) state.disabledSources.delete(src);
      else state.disabledSources.add(src);
      saveDisabledSources();
      scheduleRender();
    });
    label.appendChild(cb);
    const txt = document.createElement("span");
    txt.textContent = src;
    label.appendChild(txt);
    const badge = document.createElement("span");
    const g = srcGenre.get(src);
    badge.className = "source-count" + (g ? " " + genreClass(g) : "");
    badge.textContent = counts.get(src);
    label.appendChild(badge);
    els.sourceToggles.appendChild(label);
  }
}

function buildBezirkToggles() {
  const counts = new Map();
  for (const e of state.events) {
    const b = bezirkOf(e);
    if (!counts.has(b)) counts.set(b, 0);
    if (matches(e, { bezirk: true })) counts.set(b, counts.get(b) + 1);
  }
  // Known boroughs in their fixed order, then "Unbekannt" last.
  const present = BEZIRK_ORDER.filter((b) => counts.has(b));
  if (counts.has(BEZIRK_UNKNOWN)) present.push(BEZIRK_UNKNOWN);

  els.bezirkToggles.innerHTML = "";
  for (const b of present) {
    const label = document.createElement("label");
    label.className = "source-toggle";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !state.disabledBezirke.has(b);
    cb.addEventListener("change", () => {
      if (cb.checked) state.disabledBezirke.delete(b);
      else state.disabledBezirke.add(b);
      saveSet(BEZIRKE_KEY, state.disabledBezirke);
      scheduleRender();
    });
    label.appendChild(cb);
    const txt = document.createElement("span");
    txt.textContent = b;
    label.appendChild(txt);
    const badge = document.createElement("span");
    badge.className = "source-count";
    badge.textContent = counts.get(b);
    label.appendChild(badge);
    els.bezirkToggles.appendChild(label);
  }
}

function buildKdcatToggles() {
  const cats = [...new Set(
    state.events.filter((e) => e.source_name === KD_SOURCE)
      .map((e) => e.subcategory).filter(Boolean)
  )].sort();
  if (!cats.length) { els.kdcatSection.setAttribute("hidden", ""); return; }
  els.kdcatSection.removeAttribute("hidden");
  els.kdcatToggles.innerHTML = "";
  for (const cat of cats) {
    const label = document.createElement("label");
    label.className = "source-toggle";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !state.disabledKdCats.has(cat);
    cb.addEventListener("change", () => {
      if (cb.checked) state.disabledKdCats.delete(cat);
      else state.disabledKdCats.add(cat);
      saveSet("ek_disabled_kdcats", state.disabledKdCats);
      scheduleRender();
    });
    label.appendChild(cb);
    label.appendChild(document.createTextNode(KD_LABELS[cat] || cat));
    els.kdcatToggles.appendChild(label);
  }
}

function openSettings() {
  buildSourceToggles();
  buildBezirkToggles();
  buildKdcatToggles();
  els.settingsBackdrop.removeAttribute("hidden");
  document.body.style.overflow = "hidden";
}
function closeSettings() {
  els.settingsBackdrop.setAttribute("hidden", "");
  if (els.modalBackdrop.hasAttribute("hidden")) document.body.style.overflow = "";
  if (settingsRenderPending) {
    settingsRenderPending = false;
    render();
  }
}

function loadDisabledSources() {
  try { return new Set(JSON.parse(localStorage.getItem(SOURCES_KEY) || "[]")); }
  catch { return new Set(); }
}
function saveDisabledSources() {
  try { localStorage.setItem(SOURCES_KEY, JSON.stringify([...state.disabledSources])); }
  catch { /* ignore */ }
}
function loadSet(key) {
  try { return new Set(JSON.parse(localStorage.getItem(key) || "[]")); }
  catch { return new Set(); }
}
function saveSet(key, set) {
  try { localStorage.setItem(key, JSON.stringify([...set])); }
  catch { /* ignore */ }
}

function updateMeta(data) {
  if (data.generated_at) {
    const when = new Date(data.generated_at);
    els.footer.textContent =
      "Zuletzt aktualisiert: " + when.toLocaleString("de-DE") + " · Mund zu Mund Kalender";
  }
}

// ---------------- Filters ----------------

function buildGenreFilter() {
  const present = new Set(state.events.map((e) => e.genre).filter(Boolean));
  const genres = GENRE_ORDER.filter((g) => present.has(g));
  els.genreFilter.innerHTML = "";
  for (const genre of genres) {
    const chip = document.createElement("button");
    chip.className = "genre-chip " + genreClass(genre);
    chip.textContent = genre;
    chip.addEventListener("click", () => {
      toggleSet(state.activeGenres, genre);
      chip.classList.toggle("active");
      render();
    });
    els.genreFilter.appendChild(chip);
  }
}

function allTags() {
  const present = new Set();
  for (const ev of state.events) for (const tag of ev.tags || []) present.add(tag);
  // Fixed order; any unknown tag goes to the end.
  const ordered = CATEGORY_ORDER.filter((c) => present.has(c));
  for (const t of present) if (!CATEGORY_ORDER.includes(t)) ordered.push(t);
  return ordered;
}

function buildTagFilter() {
  els.tagFilter.innerHTML = "";
  for (const tag of allTags()) {
    const chip = document.createElement("button");
    chip.className = "tag-chip";
    chip.textContent = tag;
    chip.addEventListener("click", () => {
      toggleSet(state.activeTags, tag);
      chip.classList.toggle("active");
      render();
    });
    els.tagFilter.appendChild(chip);
  }
}

function bezirkOf(ev) { return ev.bezirk || BEZIRK_UNKNOWN; }

// ``ignore`` lets callers skip one dimension, so the count next to a source
// or a Bezirk reflects "how many would land in the feed" independent of that
// dimension's own toggle.
function matches(ev, ignore = {}) {
  // Category (OR within categories).
  if (state.activeTags.size > 0) {
    if (!(ev.tags || []).some((t) => state.activeTags.has(t))) return false;
  }
  // Genre (OR within genres).
  if (state.activeGenres.size > 0) {
    if (!state.activeGenres.has(ev.genre)) return false;
  }
  // Disabled sources (Einstellungen).
  if (!ignore.source && state.disabledSources.has(ev.source_name)) return false;
  // Bezirk filter (Einstellungen).
  if (!ignore.bezirk && state.disabledBezirke.has(bezirkOf(ev))) return false;
  // kulturdaten: einzelne Unterkategorien abschaltbar.
  if (ev.source_name === KD_SOURCE && ev.subcategory &&
      state.disabledKdCats.has(ev.subcategory)) return false;
  // Favourites only.
  if (state.onlyFav && !state.favorites.has(eventId(ev))) return false;
  // Text search.
  if (state.query) {
    const haystack = [ev.title, ev.location, ev.address, ev.description,
      ev.source_name, ev.genre, ev.bezirk, (ev.tags || []).join(" ")]
      .filter(Boolean).join(" ").toLowerCase();
    if (!haystack.includes(state.query)) return false;
  }
  return true;
}

// ---------------- Rendering ----------------

function dayKey(d) {
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate());
}

function dayStart(d) {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function isExhibition(ev) {
  return (ev.tags || []).includes("Ausstellung");
}

// JS getDay() (0=Sonntag) -> Schlüssel in event.opening_hours.
const WEEKDAY_KEYS = ["so", "mo", "di", "mi", "do", "fr", "sa"];

// Öffnungszeit eines Hauses an einem Tag: String ("10–18"), null (geschlossen)
// oder undefined (keine Öffnungszeiten bekannt).
function hoursForDay(ev, date) {
  const oh = ev.opening_hours;
  if (!oh || !date) return undefined;
  return oh[WEEKDAY_KEYS[date.getDay()]];
}

// Lesbare Wochenübersicht der Öffnungszeiten (für die Detailansicht):
// aufeinanderfolgende Tage mit gleichen Zeiten zu Bereichen zusammenfassen,
// z. B. "Mo geschlossen · Di–Mi 10–18 Uhr · Do 10–20 Uhr · Fr–So 10–18 Uhr".
function formatOpeningHours(oh) {
  const order = [["mo", "Mo"], ["di", "Di"], ["mi", "Mi"], ["do", "Do"],
    ["fr", "Fr"], ["sa", "Sa"], ["so", "So"]];
  const segs = [];
  let i = 0;
  while (i < order.length) {
    const val = oh[order[i][0]];
    let j = i;
    while (j + 1 < order.length && oh[order[j + 1][0]] === val) j++;
    const range = i === j ? order[i][1] : `${order[i][1]}–${order[j][1]}`;
    segs.push(val ? `${range} ${val} Uhr` : `${range} geschlossen`);
    i = j + 1;
  }
  return segs.join(" · ");
}

function render() {
  const visible = state.events.filter((e) => matches(e));

  const today = dayStart(new Date());
  const horizon = dayStart(new Date());
  horizon.setDate(horizon.getDate() + HORIZON_DAYS);

  const groups = new Map();
  const ensureDay = (key, date) => {
    if (!groups.has(key)) groups.set(key, { date: new Date(date), events: [] });
    return groups.get(key);
  };

  for (const ev of visible) {
    // Ausstellungen laufen über einen Zeitraum -> an jedem Tag ihres Laufs
    // (von start bis end, begrenzt auf [heute, Horizont]) einblenden.
    if (isExhibition(ev)) {
      const oh = ev.opening_hours;
      let cur = dayStart(new Date(ev.start));
      if (cur < today) cur = new Date(today);
      let last = ev.end ? dayStart(new Date(ev.end)) : new Date(horizon);
      if (last > horizon) last = new Date(horizon);
      for (; cur <= last; cur.setDate(cur.getDate() + 1)) {
        // Geschlossene Wochentage auslassen (nur wenn Öffnungszeiten bekannt).
        if (oh && !oh[WEEKDAY_KEYS[cur.getDay()]]) continue;
        ensureDay(dayKey(cur), cur).events.push(ev);
      }
      continue;
    }
    // Nach LOKALEM Datum gruppieren (sonst landen 00:00-Events über UTC
    // auf einem anderen Tag -> Tag erscheint doppelt).
    const d = new Date(ev.start);
    ensureDay(dayKey(d), d).events.push(ev);
  }
  const sortedKeys = [...groups.keys()].sort();

  if (visible.length === 0) {
    els.dayTabs.innerHTML = "";
    if (state.viewMode === "map") {
      // Keep the (initialised) map alive, just clear it and show a note.
      sizeMap();
      const map = ensureMap();
      if (map) setTimeout(() => map.invalidateSize(), 0);
      clearMapMarkers();
      showMapNote(0, 0);
    } else {
      els.feed.innerHTML = '<p class="status">Keine Veranstaltungen gefunden.</p>';
    }
    return;
  }

  buildDayTabs(sortedKeys, groups);

  if (state.viewMode === "map") {
    renderMap(sortedKeys, groups);
  } else {
    renderList(sortedKeys, groups);
  }
}

// Categories that flood the feed (one card per film/exhibition per day) are
// bundled into a single collapsible block per day, unless the user is actively
// looking for them (search, favourites-only, or the category chip is selected).
const COLLAPSE_CATS = {
  Ausstellung: { label: "Ausstellungen", one: "Ausstellung", many: "Ausstellungen" },
  Kino: { label: "Kino", one: "Film", many: "Filme" },
};

function shouldCollapse(cat) {
  if (!COLLAPSE_CATS[cat]) return false;
  if (state.query || state.onlyFav) return false;
  if (state.activeTags.has(cat)) return false;  // chip selected -> show them all
  return true;
}

// Time mode: how many Kino/Ausstellung cards show before the "+ N weitere".
const COLLAPSE_PREVIEW = 3;
// Kategorie-/Genre-Sortierung: ab mehr als 8 Events in einer Kategorie nur
// 4 zeigen, Rest einklappen (gilt dort jetzt für ALLE Kategorien).
const SORT_COLLAPSE_OVER = 8;
const SORT_COLLAPSE_SHOW = 4;

// Append a category's cards into `container`. With `preview` set, only that
// many cards show; the rest hide behind a "+ N weitere …" toggle (built lazily
// on first open). `preview` falsy (0) => show all.
function appendCategoryCards(container, cat, list, day, preview) {
  const grid = document.createElement("div");
  grid.className = "cards";
  container.appendChild(grid);

  if (!preview || list.length <= preview) {
    for (const ev of list) grid.appendChild(renderCard(ev, day));
    return;
  }

  const head = list.slice(0, preview);
  const rest = list.slice(preview);
  for (const ev of head) grid.appendChild(renderCard(ev, day));

  const meta = COLLAPSE_CATS[cat];
  const noun = meta ? " " + (rest.length === 1 ? meta.one : meta.many) : "";
  const det = document.createElement("details");
  det.className = "cat-collapse";
  const sum = document.createElement("summary");
  sum.className = "cat-collapse-summary";
  sum.textContent = `+ ${rest.length} weitere${noun}`;
  det.appendChild(sum);

  const inner = document.createElement("div");
  inner.className = "cards cat-collapse-cards";
  det.appendChild(inner);

  let built = false;
  det.addEventListener("toggle", () => {
    if (det.open && !built) {
      built = true;
      for (const ev of rest) inner.appendChild(renderCard(ev, day));
    }
  });
  container.appendChild(det);
}

// Time mode: a labelled box (Kino/Ausstellungen) at the end of the day.
function renderCollapsedCategory(cat, list, day) {
  const meta = COLLAPSE_CATS[cat];
  const section = document.createElement("section");
  section.className = "cat-section";

  const head = document.createElement("div");
  head.className = "cat-section-head";
  const title = document.createElement("span");
  title.className = "cat-section-title";
  title.textContent = meta.label;
  const count = document.createElement("span");
  count.className = "cat-section-count";
  count.textContent = list.length + " " + (list.length === 1 ? meta.one : meta.many);
  head.append(title, count);
  section.appendChild(head);

  appendCategoryCards(section, cat, list, day, COLLAPSE_PREVIEW);
  return section;
}

function renderList(sortedKeys, groups) {
  const frag = document.createDocumentFragment();
  for (const key of sortedKeys) {
    const { date, events } = groups.get(key);
    const group = document.createElement("section");
    group.className = "day-group";
    group.id = `day-${key}`;

    const heading = document.createElement("h2");
    heading.className = "day-heading";
    heading.dataset.key = key;
    heading.textContent = DAY_FMT.format(date);
    group.appendChild(heading);

    if (state.sortMode === "category") renderDayByCategory(events, group, date);
    else if (state.sortMode === "genre") renderDayByGenre(events, group, date);
    else renderDayByTime(events, group, date);

    frag.appendChild(group);
  }

  els.feed.innerHTML = "";
  els.feed.appendChild(frag);

  setupScrollSpy(sortedKeys);
}

// Sort "Uhrzeit": cards in time order; Kino/Ausstellungen bundled per day.
function renderDayByTime(events, group, day) {
  // Split off the collapsible categories; everything else stays a card.
  const normal = [];
  const collapsed = new Map();
  for (const ev of events) {
    const cat = (ev.tags || [])[0];
    if (cat && shouldCollapse(cat)) {
      if (!collapsed.has(cat)) collapsed.set(cat, []);
      collapsed.get(cat).push(ev);
    } else {
      normal.push(ev);
    }
  }

  const cards = document.createElement("div");
  cards.className = "cards";
  for (const ev of normal) cards.appendChild(renderCard(ev, day));
  group.appendChild(cards);

  // Collapsible blocks (Kino, Ausstellungen) go at the end of the day.
  for (const cat of Object.keys(COLLAPSE_CATS)) {
    const list = collapsed.get(cat);
    if (list && list.length) group.appendChild(renderCollapsedCategory(cat, list, day));
  }
}

// Ausstellungen behalten die Reihenfolge der Quelle; alles andere nach Uhrzeit.
function orderForCat(cat, list) {
  return cat === "Ausstellung" ? list.slice() : list.slice().sort(byStart);
}

// Sort "Kategorie": one open (collapsible) box per category, cards by time.
function renderDayByCategory(events, group, day) {
  const byCat = groupBy(events, (ev) => (ev.tags || [])[0] || "Sonstiges");
  for (const cat of orderedKeys(byCat.keys(), SORT_CATEGORY_ORDER)) {
    const list = orderForCat(cat, byCat.get(cat));
    const box = buildSortBox(cat, list.length);
    appendCategoryCards(box, cat, list, day,
      list.length > SORT_COLLAPSE_OVER ? SORT_COLLAPSE_SHOW : 0);
    group.appendChild(box);
  }
}

// Sort "Genre": one open box per genre, inside it a sub-box per category.
function renderDayByGenre(events, group, day) {
  const byGenre = groupBy(events, (ev) => ev.genre || "Ohne Genre");
  for (const genre of orderedKeys(byGenre.keys(), GENRE_ORDER)) {
    const gEvents = byGenre.get(genre);
    const box = buildSortBox(genre, gEvents.length, genreClass(genre));
    const byCat = groupBy(gEvents, (ev) => (ev.tags || [])[0] || "Sonstiges");
    for (const cat of orderedKeys(byCat.keys(), SORT_CATEGORY_ORDER)) {
      const list = orderForCat(cat, byCat.get(cat));
      const sub = buildSortBox(cat, list.length, "sort-subbox");
      appendCategoryCards(sub, cat, list, day,
        list.length > SORT_COLLAPSE_OVER ? SORT_COLLAPSE_SHOW : 0);
      box.appendChild(sub);
    }
    group.appendChild(box);
  }
}

// An open-by-default, collapsible box (<details open>) with a title + count.
function buildSortBox(label, count, cls) {
  const det = document.createElement("details");
  det.className = "sort-box" + (cls ? " " + cls : "");
  det.open = true;
  const sum = document.createElement("summary");
  sum.className = "sort-box-head";
  const t = document.createElement("span");
  t.className = "sort-box-title";
  t.textContent = label;
  const c = document.createElement("span");
  c.className = "sort-box-count";
  c.textContent = count;
  sum.append(t, c);
  det.appendChild(sum);
  return det;
}

function groupBy(items, keyFn) {
  const map = new Map();
  for (const it of items) {
    const k = keyFn(it);
    if (!map.has(k)) map.set(k, []);
    map.get(k).push(it);
  }
  return map;
}

// Keys in the given fixed order first, then any leftover keys alphabetically.
function orderedKeys(keys, order) {
  const present = new Set(keys);
  const out = order.filter((k) => present.has(k));
  for (const k of [...present].sort((a, b) => a.localeCompare(b, "de"))) {
    if (!order.includes(k)) out.push(k);
  }
  return out;
}

function byStart(a, b) {
  return new Date(a.start) - new Date(b.start);
}

function renderCard(ev, day) {
  const card = document.createElement("div");
  card.className = "card" + (ev.user_submitted ? " card--mine" : "");
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.addEventListener("click", () => openModal(ev, day));
  card.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openModal(ev, day); }
  });

  // Favourite heart.
  const fav = document.createElement("button");
  fav.className = "card-fav" + (isFav(ev) ? " is-fav" : "");
  fav.textContent = isFav(ev) ? "♥" : "♡";
  fav.setAttribute("aria-label", "Merken");
  fav.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleFav(ev);
    const on = isFav(ev);
    fav.classList.toggle("is-fav", on);
    fav.textContent = on ? "♥" : "♡";
    if (state.onlyFav) render();
  });
  card.appendChild(fav);

  if (ev.image_url) {
    const img = document.createElement("img");
    img.className = "card-image";
    img.src = ev.image_url;
    img.alt = ev.title || "";
    img.loading = "lazy";
    img.addEventListener("error", () => img.remove());
    card.appendChild(img);
  }

  const body = document.createElement("div");
  body.className = "card-body";

  const time = document.createElement("div");
  time.className = "card-time";
  // Ausstellungen: das jeweilige Tagesdatum + die Öffnungszeit dieses Tages.
  if (isExhibition(ev) && day) {
    const oh = hoursForDay(ev, day);
    time.textContent = CARD_DATE_FMT.format(day) + (oh ? " · " + oh + " Uhr" : "");
  } else {
    time.textContent = formatTime(ev);
  }
  body.appendChild(time);

  const title = document.createElement("h3");
  title.className = "card-title";
  title.textContent = ev.title || "Ohne Titel";
  body.appendChild(title);

  // Cinema cards list the cinemas in the screenings block instead.
  if (ev.location && !(ev.showings && ev.showings.length)) {
    const loc = document.createElement("div");
    loc.className = "card-location";
    loc.textContent = "📍 " + ev.location;
    body.appendChild(loc);
  }
  const cardShowings = renderShowings(ev);
  if (cardShowings) body.appendChild(cardShowings);
  if (ev.description) {
    const desc = document.createElement("p");
    desc.className = "card-desc";
    desc.textContent = ev.description;
    body.appendChild(desc);
  }
  const tagWrap = document.createElement("div");
  tagWrap.className = "card-tags";
  if (ev.user_submitted) {
    const mine = document.createElement("span");
    mine.className = "card-tag mine-badge";
    mine.textContent = "★ Eigenes Event";
    tagWrap.appendChild(mine);
  }
  if (ev.genre) {
    const g = document.createElement("span");
    g.className = "card-tag genre-badge " + genreClass(ev.genre);
    g.textContent = ev.genre;
    tagWrap.appendChild(g);
  }
  for (const tag of ev.tags || []) {
    const t = document.createElement("span");
    t.className = "card-tag";
    t.textContent = tag;
    tagWrap.appendChild(t);
    // Music genre right behind the "Konzert" tag (e.g. Konzert · Jazz).
    if (tag === "Konzert" && ev.music_genre) {
      const mg = document.createElement("span");
      mg.className = "card-tag music-tag";
      mg.textContent = ev.music_genre;
      tagWrap.appendChild(mg);
    }
  }
  if (tagWrap.children.length) body.appendChild(tagWrap);

  if (ev.source_name) {
    const src = document.createElement("div");
    src.className = "card-source";
    src.textContent = "Quelle: " + ev.source_name;
    body.appendChild(src);
  }

  card.appendChild(body);
  return card;
}

// ---------------- Detail modal ----------------

// Opening an event is a navigation: openModal only sets the URL hash
// (#e/<id>); the router (routeFromHash) does the actual rendering. That gives
// every event a shareable "subpage" and lets the browser back button close it.
let modalPushed = false;
// The day a card was opened from, so the modal can show "jeweiliges Datum +
// Uhrzeit" for exhibitions (which appear on many days). Null when deep-linked.
let pendingModalDay = null;

function openModal(ev, day) {
  pendingModalDay = day || null;
  const target = "#e/" + eventSlug(ev);
  if (location.hash === target) { showModal(ev, pendingModalDay); return; }
  modalPushed = true;
  location.hash = target;  // -> hashchange -> routeFromHash -> showModal
}

function showModal(ev, day) {
  const c = els.modalContent;
  c.innerHTML = "";

  if (ev.image_url) {
    const img = document.createElement("img");
    img.className = "modal-image";
    img.src = ev.image_url;
    img.alt = ev.title || "";
    img.addEventListener("error", () => img.remove());
    c.appendChild(img);
  }

  const body = document.createElement("div");
  body.className = "modal-body";

  // Time line. Exhibitions show the day the card was opened from plus that
  // day's opening hours; other events the usual date + time.
  let timeText;
  if (isExhibition(ev)) {
    if (day) {
      const oh = hoursForDay(ev, day);
      timeText = CARD_DATE_FMT.format(day) + (oh ? " · " + oh + " Uhr" : "");
    } else {
      timeText = "";  // deep link without a day -> covered by the lines below
    }
  } else {
    timeText = formatTime(ev);
  }
  if (timeText) {
    const time = document.createElement("div");
    time.className = "modal-time";
    time.textContent = timeText;
    body.appendChild(time);
  }

  const title = document.createElement("h2");
  title.className = "modal-title";
  title.textContent = ev.title || "Ohne Titel";
  body.appendChild(title);

  // Exhibitions: until when the show runs + the venue's weekly opening hours.
  if (isExhibition(ev) && ev.end) {
    const runs = document.createElement("div");
    runs.className = "modal-runsuntil";
    runs.textContent = "läuft bis " + END_FMT.format(new Date(ev.end));
    body.appendChild(runs);
  }
  if (ev.opening_hours) {
    const hours = document.createElement("div");
    hours.className = "modal-hours";
    hours.textContent = "Öffnungszeiten: " + formatOpeningHours(ev.opening_hours);
    body.appendChild(hours);
  }

  // Cinema events list the screenings first, then the (always-open) map of all
  // involved cinemas; other events just get the location map.
  const modalShowings = renderShowings(ev);
  if (modalShowings) body.appendChild(modalShowings);
  const locMap = renderLocationMap(ev);
  if (locMap) body.appendChild(locMap);

  // Genre first, then categories -- same order as on the cards.
  const meta = document.createElement("div");
  meta.className = "card-tags";
  if (ev.genre) {
    const g = document.createElement("span");
    g.className = "card-tag genre-badge " + genreClass(ev.genre);
    g.textContent = ev.genre;
    meta.appendChild(g);
  }
  for (const tag of ev.tags || []) {
    const t = document.createElement("span");
    t.className = "card-tag";
    t.textContent = tag;
    meta.appendChild(t);
    if (tag === "Konzert" && ev.music_genre) {
      const mg = document.createElement("span");
      mg.className = "card-tag music-tag";
      mg.textContent = ev.music_genre;
      meta.appendChild(mg);
    }
  }
  body.appendChild(meta);

  if (ev.description) {
    const desc = document.createElement("p");
    desc.className = "modal-desc";
    desc.textContent = ev.description;
    body.appendChild(desc);
  }

  // Actions.
  const actions = document.createElement("div");
  actions.className = "modal-actions";

  const favBtn = document.createElement("button");
  favBtn.className = "btn";
  const setFavLabel = () => { favBtn.textContent = (isFav(ev) ? "♥ Gemerkt" : "♡ Merken"); };
  setFavLabel();
  favBtn.addEventListener("click", () => { toggleFav(ev); setFavLabel(); render(); });
  actions.appendChild(favBtn);

  const calBtn = document.createElement("button");
  calBtn.className = "btn";
  calBtn.innerHTML =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" ' +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round" aria-hidden="true">' +
    '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>' +
    '<line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>' +
    '<line x1="3" y1="10" x2="21" y2="10"/></svg><span>In den Kalender</span>';
  calBtn.addEventListener("click", () => downloadICS(ev));
  actions.appendChild(calBtn);

  const shareBtn = document.createElement("button");
  shareBtn.className = "btn";
  shareBtn.innerHTML =
    '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" ' +
    'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
    'stroke-linejoin="round" aria-hidden="true">' +
    '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/>' +
    '<circle cx="18" cy="19" r="3"/>' +
    '<line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/>' +
    '<line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg><span>Teilen</span>';
  shareBtn.addEventListener("click", () => shareEvent(ev));
  actions.appendChild(shareBtn);

  // Eigene Events lassen sich (für alle) wieder löschen.
  if (ev.user_submitted && ev._id && FIREBASE_DB_URL) {
    const del = document.createElement("button");
    del.className = "btn btn--danger";
    del.innerHTML =
      '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
      'stroke-linejoin="round" aria-hidden="true">' +
      '<polyline points="3 6 5 6 21 6"/>' +
      '<path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>' +
      '<path d="M10 11v6"/><path d="M14 11v6"/>' +
      '<path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>' +
      '<span>Event löschen</span>';
    del.addEventListener("click", () => deleteOwnEvent(ev));
    actions.appendChild(del);
  }

  if (ev.source_url) {
    const link = document.createElement("a");
    link.className = "btn btn--primary";
    link.href = ev.source_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.innerHTML =
      '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" ' +
      'stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>' +
      '<polyline points="15 3 21 3 21 9"/>' +
      '<line x1="10" y1="14" x2="21" y2="3"/></svg><span>Zur Veranstaltung</span>';
    actions.appendChild(link);
  }
  body.appendChild(actions);

  if (ev.source_name) {
    const src = document.createElement("div");
    src.className = "card-source";
    src.textContent = "Quelle: " + ev.source_name;
    body.appendChild(src);
  }

  c.appendChild(body);
  els.modalBackdrop.removeAttribute("hidden");
  els.modal.scrollTop = 0;
  document.body.style.overflow = "hidden";
}

let modalMaps = [];

// The location block in the detail view: the location name(s) and an always-open
// embedded map (all cinemas for a multi-cinema film), with a "copy address"
// button (a choice menu when there's more than one address).
function renderLocationMap(ev) {
  const points = [];
  if (ev.showings && ev.showings.length) {
    const seen = new Set();
    for (const s of ev.showings) {
      if (s.address && !seen.has(s.cinema)) {
        seen.add(s.cinema);
        points.push({ name: s.cinema, address: s.address });
      }
    }
  } else if (ev.location || ev.address) {
    points.push({
      name: ev.location || ev.address,
      address: ev.address || (ev.location ? ev.location + ", Berlin" : ""),
      lat: ev.lat, lng: ev.lng,
    });
  }
  if (!points.length) return null;

  const box = document.createElement("div");
  box.className = "loc-map";
  const head = document.createElement("div");
  head.className = "loc-map-head";
  head.textContent = "📍 " + points.map((p) => p.name).filter(Boolean).join(" · ");
  if (points.length === 1 && ev.bezirk) {
    const b = document.createElement("span");
    b.className = "modal-bezirk";
    b.textContent = " (" + ev.bezirk + ")";
    head.appendChild(b);
  }
  box.appendChild(head);

  const panel = document.createElement("div");
  panel.className = "modal-map-panel";
  box.appendChild(panel);
  openMultiMap(panel, points, ev);
  return box;
}

async function copyAddress(addr) {
  try { await navigator.clipboard.writeText(addr || ""); toast("Adresse kopiert"); }
  catch { toast("Konnte nicht kopieren"); }
}

function showCopyMenu(anchor, points) {
  const existing = anchor.parentElement.querySelector(".copy-menu");
  if (existing) { existing.remove(); return; }
  const menu = document.createElement("div");
  menu.className = "copy-menu";
  for (const p of points) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "copy-menu-item";
    item.textContent = p.name;
    item.addEventListener("click", (e) => {
      e.stopPropagation();
      copyAddress(p.address);
      menu.remove();
    });
    menu.appendChild(item);
  }
  anchor.parentElement.appendChild(menu);
}

async function openMultiMap(panel, points, ev) {
  const mapDiv = document.createElement("div");
  mapDiv.className = "modal-map";
  panel.appendChild(mapDiv);

  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "map-copy-btn";
  if (points.length > 1) {
    copy.textContent = "Adresse kopieren ▾";
    copy.addEventListener("click", (e) => { e.stopPropagation(); showCopyMenu(copy, points); });
  } else {
    copy.textContent = "Adresse kopieren";
    copy.addEventListener("click", (e) => { e.stopPropagation(); copyAddress(points[0].address); });
  }
  panel.appendChild(copy);

  const resolved = [];
  for (const p of points) {
    let lat = p.lat, lng = p.lng;
    if (typeof lat !== "number" || typeof lng !== "number") {
      const geo = await geocodeClient(p.address || "");
      if (geo) { lat = geo.lat; lng = geo.lng; }
    }
    if (typeof lat === "number" && typeof lng === "number") resolved.push({ ...p, lat, lng });
  }
  if (typeof L === "undefined" || !resolved.length) {
    mapDiv.innerHTML = '<p class="status">Karte nicht verfügbar.</p>';
    return;
  }
  // dragging/tap off so a vertical swipe scrolls the modal instead of panning
  // the map; the location is fixed anyway and zoom stays on the +/- buttons.
  const m = L.map(mapDiv, {
    scrollWheelZoom: false, dragging: false, tap: false,
    attributionControl: true,
  });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
    { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(m);
  const latlngs = [];
  for (const r of resolved) {
    L.circleMarker([r.lat, r.lng], {
      radius: 9, color: "#fff", weight: 2,
      fillColor: genreColor(ev.genre), fillOpacity: 0.95,
    }).addTo(m).bindTooltip(r.name || r.address, { direction: "top" });
    latlngs.push([r.lat, r.lng]);
  }
  if (latlngs.length === 1) m.setView(latlngs[0], 15);
  else m.fitBounds(latlngs, { padding: [34, 34], maxZoom: 15 });
  modalMaps.push(m);
  setTimeout(() => m.invalidateSize(), 60);
}

// Triggered by the ✕ button, the backdrop and Escape: leave the event route.
// When we navigated here in-app we go back (so we don't pile up history
// entries); a directly opened/shared link just gets its hash stripped.
function closeModal() {
  if (!location.hash.startsWith("#e/")) { hideModal(); return; }
  if (modalPushed) {
    modalPushed = false;
    history.back();  // -> hashchange -> routeFromHash -> hideModal
  } else {
    history.replaceState(null, "", location.pathname + location.search);
    hideModal();
  }
}

// Actually hide the modal UI and tear down its maps. Driven by the router.
function hideModal() {
  els.modalBackdrop.setAttribute("hidden", "");
  if (els.settingsBackdrop.hasAttribute("hidden")) document.body.style.overflow = "";
  for (const m of modalMaps) m.remove();
  modalMaps = [];
}

// ---------------- Favourites ----------------

function eventId(ev) {
  return (ev.source_url || "") + "|" + (ev.start || "") + "|" + (ev.title || "");
}
function isFav(ev) { return state.favorites.has(eventId(ev)); }
function toggleFav(ev) {
  const id = eventId(ev);
  if (state.favorites.has(id)) state.favorites.delete(id);
  else state.favorites.add(id);
  saveFavorites();
}
function loadFavorites() {
  try { return new Set(JSON.parse(localStorage.getItem(FAV_KEY) || "[]")); }
  catch { return new Set(); }
}
function saveFavorites() {
  try { localStorage.setItem(FAV_KEY, JSON.stringify([...state.favorites])); }
  catch { /* ignore */ }
}

// ---------------- Calendar export (.ics) ----------------

function downloadICS(ev) {
  const start = new Date(ev.start);
  const lines = [
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Mund zu Mund Kalender//DE",
    "BEGIN:VEVENT",
    "UID:" + icsEsc(eventId(ev)),
    "DTSTAMP:" + icsStamp(new Date()),
  ];
  if (ev.time_known === false) {
    lines.push("DTSTART;VALUE=DATE:" + icsDay(start));
  } else {
    const end = ev.end ? new Date(ev.end) : new Date(start.getTime() + 2 * 3600 * 1000);
    lines.push("DTSTART:" + icsLocal(start), "DTEND:" + icsLocal(end));
  }
  lines.push("SUMMARY:" + icsEsc(ev.title || "Veranstaltung"));
  if (ev.location) lines.push("LOCATION:" + icsEsc(ev.location));
  const desc = [ev.description, ev.source_url].filter(Boolean).join("\n\n");
  if (desc) lines.push("DESCRIPTION:" + icsEsc(desc));
  if (ev.source_url) lines.push("URL:" + ev.source_url);
  lines.push("END:VEVENT", "END:VCALENDAR");

  const blob = new Blob([lines.join("\r\n")], { type: "text/calendar;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = (ev.title || "event").replace(/[^\wäöü]+/gi, "_").slice(0, 40) + ".ics";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

function pad(n) { return String(n).padStart(2, "0"); }
function icsDay(d) { return d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()); }
function icsLocal(d) { return icsDay(d) + "T" + pad(d.getHours()) + pad(d.getMinutes()) + "00"; }
function icsStamp(d) {
  return d.getUTCFullYear() + pad(d.getUTCMonth() + 1) + pad(d.getUTCDate()) + "T" +
    pad(d.getUTCHours()) + pad(d.getUTCMinutes()) + pad(d.getUTCSeconds()) + "Z";
}
function icsEsc(s) {
  return String(s).replace(/\\/g, "\\\\").replace(/;/g, "\\;")
    .replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
}

// ---------------- Share / deep links ----------------

// Short, stable id for an event's shareable URL (a hash of its full id, so it
// stays readable and doesn't leak the whole source URL into the link).
function eventSlug(ev) {
  return shortHash(eventId(ev));
}

function shortHash(str) {
  let h1 = 0xdeadbeef, h2 = 0x41c6ce57;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return (h2 >>> 0).toString(36) + (h1 >>> 0).toString(36);
}

// Deep link back to THIS site, opening the event's detail view.
function eventShareUrl(ev) {
  return location.origin + location.pathname + "#e/" + eventSlug(ev);
}

async function shareEvent(ev) {
  const url = eventShareUrl(ev);
  const text = ev.title + " · " + formatTime(ev) + (ev.location ? " · " + ev.location : "");
  if (navigator.share) {
    try { await navigator.share({ title: ev.title, text, url }); } catch { /* cancelled */ }
  } else {
    try { await navigator.clipboard.writeText(text + " — " + url); toast("Link kopiert"); }
    catch { prompt("Link kopieren:", url); }
  }
}

// Open/close the modal to match the current URL hash (#e/<slug>). Called on
// load, on hashchange and when the browser back/forward button is used.
function routeFromHash() {
  const m = location.hash.match(/^#e\/(.+)$/);
  if (!m) { hideModal(); return; }
  const slug = decodeURIComponent(m[1]);
  const ev = state.events.find((e) => eventSlug(e) === slug);
  if (ev) {
    showModal(ev, pendingModalDay);
    pendingModalDay = null;  // consumed; back/forward etc. have no day
  } else {
    history.replaceState(null, "", location.pathname + location.search);
    hideModal();
    toast("Diese Veranstaltung ist nicht mehr im Kalender.");
  }
}

// On load: honour an #e/<slug> hash, and translate legacy ?event=<id> links.
function openSharedEvent() {
  const legacy = new URLSearchParams(location.search).get("event");
  if (legacy) {
    const ev = state.events.find((e) => eventId(e) === legacy);
    history.replaceState(
      null, "", location.pathname + (ev ? "#e/" + eventSlug(ev) : ""));
    if (!ev) toast("Diese Veranstaltung ist nicht mehr im Kalender.");
  }
  routeFromHash();
}

// ---------------- Eigene Events (Firebase) ----------------

function mergeEvents() {
  const base = state.baseEvents || [];
  state.events = base.concat(state.userEvents);
}

// Read user-submitted events that everyone shares (Firebase Realtime DB).
async function loadUserEvents() {
  state.userEvents = [];
  if (!FIREBASE_DB_URL) return;
  try {
    const res = await fetch(FIREBASE_DB_URL.replace(/\/$/, "") + "/events.json",
      { cache: "no-cache" });
    if (!res.ok) return;
    const data = await res.json();
    if (!data || typeof data !== "object") return;
    const now = new Date();
    const horizon = new Date(now.getTime() + 60 * 86400 * 1000);
    for (const [id, raw] of Object.entries(data)) {
      if (!raw || !raw.title || !raw.start) continue;
      const start = new Date(raw.start);
      if (isNaN(start) || start > horizon) continue;
      // Hide events that are clearly over (allow same-day until midnight).
      const dayEnd = new Date(start); dayEnd.setHours(23, 59, 59, 999);
      if (dayEnd < now) continue;
      state.userEvents.push({
        title: String(raw.title),
        start: raw.start,
        end: raw.end || null,
        location: raw.location || null,
        address: raw.address || null,
        description: raw.description || null,
        image_url: null,
        source_url: raw.link || eventShareBase() + "#mine-" + id,
        source_name: MINE_SOURCE,
        tags: raw.category ? [raw.category] : [],
        time_known: raw.time_known !== false,
        genre: raw.genre || null,
        bezirk: raw.bezirk || null,
        lat: typeof raw.lat === "number" ? raw.lat : null,
        lng: typeof raw.lng === "number" ? raw.lng : null,
        user_submitted: true,
        _id: id,
      });
    }
  } catch { /* offline or not configured -> just skip */ }
}

function eventShareBase() { return location.origin + location.pathname; }

async function submitOwnEvent(e) {
  e.preventDefault();
  if (!FIREBASE_DB_URL) {
    toast("Eigene Events sind noch nicht eingerichtet.");
    return;
  }
  const title = (els.mineTitle.value || "").trim();
  const date = els.mineDate.value;
  const time = els.mineTime.value;
  if (!title || !date) { toast("Bitte Titel und Datum angeben."); return; }

  const start = time ? `${date}T${time}` : `${date}T00:00`;
  els.mineSend.disabled = true;
  els.mineSend.textContent = "Sende …";

  const payload = {
    title: title.slice(0, 140),
    start,
    time_known: Boolean(time),
    location: (els.mineLocation.value || "").trim().slice(0, 120) || null,
    address: (els.mineAddress.value || "").trim().slice(0, 160) || null,
    description: (els.mineDesc.value || "").trim().slice(0, 1000) || null,
    link: (els.mineLink.value || "").trim().slice(0, 300) || null,
    category: els.mineCategory.value || null,
    genre: els.mineGenre.value || null,
    created_at: new Date().toISOString(),
  };

  // Best-effort geocoding so the event also shows up on the map / Bezirk filter.
  const geoQuery = payload.address || payload.location;
  if (geoQuery) {
    const geo = await geocodeClient(geoQuery);
    if (geo) {
      payload.lat = geo.lat; payload.lng = geo.lng;
      payload.bezirk = geo.bezirk;
      if (!payload.address && geo.address) payload.address = geo.address;
    }
  }

  try {
    // No custom Content-Type header -> stays a CORS "simple request" (no
    // preflight). Firebase parses the JSON body regardless.
    const res = await fetch(FIREBASE_DB_URL.replace(/\/$/, "") + "/events.json", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error("HTTP " + res.status);
    toast("Danke! Dein Event ist jetzt für alle sichtbar.");
    els.mineForm.reset();
    await loadUserEvents();
    mergeEvents();
    buildGenreFilter();
    buildTagFilter();
    render();
  } catch {
    toast("Konnte nicht senden. Bitte später erneut versuchen.");
  }
  els.mineSend.disabled = false;
  els.mineSend.textContent = "Event hinzufügen";
}

// Delete a user-submitted event for everyone (removes it from Firebase).
async function deleteOwnEvent(ev) {
  if (!FIREBASE_DB_URL || !ev._id) return;
  if (!confirm("Dieses Event wirklich für alle löschen?")) return;
  try {
    const res = await fetch(
      FIREBASE_DB_URL.replace(/\/$/, "") + "/events/" +
      encodeURIComponent(ev._id) + ".json", { method: "DELETE" });
    if (!res.ok) throw new Error("HTTP " + res.status);
    closeModal();
    state.userEvents = state.userEvents.filter((e) => e._id !== ev._id);
    mergeEvents();
    buildGenreFilter();
    buildTagFilter();
    render();
    toast("Event gelöscht.");
  } catch {
    toast("Konnte nicht löschen. Bitte später erneut versuchen.");
  }
}

// Lightweight client-side geocoder (OpenStreetMap/Nominatim) for user events.
async function geocodeClient(query) {
  try {
    const url = "https://nominatim.openstreetmap.org/search?format=jsonv2" +
      "&addressdetails=1&limit=1&countrycodes=de&q=" +
      encodeURIComponent(query.toLowerCase().includes("berlin") ? query : query + ", Berlin");
    const res = await fetch(url, { headers: { "Accept": "application/json" } });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data.length) return null;
    const hit = data[0];
    const a = hit.address || {};
    const road = a.road || a.pedestrian;
    const addrParts = [
      road ? road + (a.house_number ? " " + a.house_number : "") : null,
      [a.postcode, a.suburb || a.city_district || a.borough].filter(Boolean).join(" "),
    ].filter(Boolean);
    return {
      lat: parseFloat(hit.lat),
      lng: parseFloat(hit.lon),
      address: addrParts.join(", ") || null,
      bezirk: bezirkFromAddress(a),
    };
  } catch { return null; }
}

// Compact Ortsteil -> Bezirk lookup (mirror of scrapers/geocode.py for the
// boroughs user events are most likely to fall into).
const ORTSTEIL_TO_BEZIRK = {
  "mitte": "Mitte", "moabit": "Mitte", "tiergarten": "Mitte",
  "wedding": "Mitte", "gesundbrunnen": "Mitte", "hansaviertel": "Mitte",
  "friedrichshain": "Friedrichshain-Kreuzberg", "kreuzberg": "Friedrichshain-Kreuzberg",
  "prenzlauer berg": "Pankow", "weißensee": "Pankow", "pankow": "Pankow",
  "niederschönhausen": "Pankow", "buch": "Pankow",
  "charlottenburg": "Charlottenburg-Wilmersdorf", "wilmersdorf": "Charlottenburg-Wilmersdorf",
  "westend": "Charlottenburg-Wilmersdorf", "halensee": "Charlottenburg-Wilmersdorf",
  "grunewald": "Charlottenburg-Wilmersdorf", "schmargendorf": "Charlottenburg-Wilmersdorf",
  "spandau": "Spandau", "haselhorst": "Spandau", "siemensstadt": "Spandau",
  "steglitz": "Steglitz-Zehlendorf", "lichterfelde": "Steglitz-Zehlendorf",
  "lankwitz": "Steglitz-Zehlendorf", "zehlendorf": "Steglitz-Zehlendorf", "dahlem": "Steglitz-Zehlendorf",
  "schöneberg": "Tempelhof-Schöneberg", "friedenau": "Tempelhof-Schöneberg",
  "tempelhof": "Tempelhof-Schöneberg", "mariendorf": "Tempelhof-Schöneberg",
  "lichtenrade": "Tempelhof-Schöneberg",
  "neukölln": "Neukölln", "britz": "Neukölln", "buckow": "Neukölln",
  "rudow": "Neukölln", "gropiusstadt": "Neukölln",
  "alt-treptow": "Treptow-Köpenick", "treptow": "Treptow-Köpenick",
  "baumschulenweg": "Treptow-Köpenick", "johannisthal": "Treptow-Köpenick",
  "adlershof": "Treptow-Köpenick", "köpenick": "Treptow-Köpenick",
  "oberschöneweide": "Treptow-Köpenick", "niederschöneweide": "Treptow-Köpenick",
  "marzahn": "Marzahn-Hellersdorf", "hellersdorf": "Marzahn-Hellersdorf",
  "biesdorf": "Marzahn-Hellersdorf", "kaulsdorf": "Marzahn-Hellersdorf",
  "lichtenberg": "Lichtenberg", "friedrichsfelde": "Lichtenberg",
  "karlshorst": "Lichtenberg", "rummelsburg": "Lichtenberg", "fennpfuhl": "Lichtenberg",
  "hohenschönhausen": "Lichtenberg", "alt-hohenschönhausen": "Lichtenberg",
  "reinickendorf": "Reinickendorf", "tegel": "Reinickendorf", "wittenau": "Reinickendorf",
  "frohnau": "Reinickendorf", "hermsdorf": "Reinickendorf", "märkisches viertel": "Reinickendorf",
};

function bezirkFromAddress(a) {
  for (const key of ["borough", "city_district", "suburb", "quarter", "neighbourhood"]) {
    const val = (a[key] || "").toLowerCase();
    if (!val) continue;
    if (BEZIRK_ORDER.map((b) => b.toLowerCase()).includes(val)) {
      return BEZIRK_ORDER.find((b) => b.toLowerCase() === val);
    }
    if (ORTSTEIL_TO_BEZIRK[val]) return ORTSTEIL_TO_BEZIRK[val];
  }
  return null;
}

// ---------------- Ansicht: Liste / Karte ----------------

function applyViewMode() {
  const map = state.viewMode === "map";
  els.viewList.classList.toggle("active", !map);
  els.viewMap.classList.toggle("active", map);
  els.viewList.setAttribute("aria-pressed", String(!map));
  els.viewMap.setAttribute("aria-pressed", String(map));
  els.feed.toggleAttribute("hidden", map);
  els.mapView.toggleAttribute("hidden", !map);
  // Map view fills the screen and locks page scrolling.
  document.documentElement.classList.toggle("map-active", map);
  if (map && dayIO) {
    dayIO.disconnect();
    lastActiveKey = null;
  }
}

function setViewMode(mode) {
  if (mode === state.viewMode) return;
  state.viewMode = mode;
  try { localStorage.setItem(VIEW_KEY, mode); } catch { /* ignore */ }
  applyViewMode();
  render();
}

let leafletMap = null;
let mapMarkers = [];
let mapDayEvents = [];
let mapMoveBound = false;

// Fill the space between the sticky header and the viewport bottom.
function sizeMap() {
  const header = document.querySelector(".site-header");
  const top = header ? header.getBoundingClientRect().bottom : 0;
  els.mapView.style.height = Math.max(280, window.innerHeight - top) + "px";
}

window.addEventListener("resize", () => {
  if (state.viewMode === "map" && leafletMap) {
    sizeMap();
    leafletMap.invalidateSize();
  }
});

function clearMapMarkers() {
  if (!leafletMap) return;
  for (const m of mapMarkers) leafletMap.removeLayer(m);
  mapMarkers = [];
}

function ensureMap() {
  if (leafletMap || typeof L === "undefined") return leafletMap;
  leafletMap = L.map(els.mapView, { zoomControl: true, attributionControl: true })
    .setView([52.52, 13.405], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap",
  }).addTo(leafletMap);
  return leafletMap;
}

function renderMap(sortedKeys, groups) {
  if (typeof L === "undefined") {
    els.mapView.innerHTML =
      '<p class="status">Karte konnte nicht geladen werden (offline?).</p>';
    return;
  }
  // Pick the day to show: keep current selection if still present, else today,
  // else the first available day.
  if (!groups.has(state.mapDay)) {
    const today = dayKey(new Date());
    state.mapDay = groups.has(today) ? today : sortedKeys[0];
  }
  setActiveTab(state.mapDay);

  sizeMap();
  const map = ensureMap();
  setTimeout(() => map.invalidateSize(), 0);

  const events = (groups.get(state.mapDay) || { events: [] }).events;
  mapDayEvents = events.filter(
    (e) => typeof e.lat === "number" && typeof e.lng === "number");
  showMapNote(mapDayEvents.length, events.length);

  // Redraw markers whenever the view changes (the ≤10 rule is bounds-based).
  if (!mapMoveBound) {
    map.on("moveend zoomend", drawMarkers);
    mapMoveBound = true;
  }

  const pts = mapDayEvents.map((e) => [e.lat, e.lng]);
  if (pts.length === 1) map.setView(pts[0], 14);
  else if (pts.length > 1) map.fitBounds(pts, { padding: [40, 40], maxZoom: 15 });
  drawMarkers();
}

// At most 10 points visible -> show each as an expanded chip containing its
// tag, outlined in the genre colour. Otherwise plain coloured dots (no label).
const CHIP_THRESHOLD = 10;

function drawMarkers() {
  if (!leafletMap || state.viewMode !== "map") return;
  clearMapMarkers();
  const bounds = leafletMap.getBounds();
  const inBounds = mapDayEvents.filter((e) => bounds.contains([e.lat, e.lng]));
  const asChips = inBounds.length > 0 && inBounds.length <= CHIP_THRESHOLD;
  const now = new Date();
  const isToday = state.mapDay === dayKey(now);

  for (const ev of mapDayEvents) {
    const past = isToday && ev.time_known !== false && new Date(ev.start) < now;
    const here = bounds.contains([ev.lat, ev.lng]);
    const marker = (asChips && here) ? chipMarker(ev, past) : dotMarker(ev, past);
    marker.on("click", () => openModal(ev));
    marker.addTo(leafletMap);
    mapMarkers.push(marker);
  }
}

function dotMarker(ev, past) {
  return L.circleMarker([ev.lat, ev.lng], {
    radius: ev.user_submitted ? 9 : 7,
    color: ev.user_submitted ? "#ff7a00" : "#fff",
    weight: ev.user_submitted ? 3 : 2,
    fillColor: past ? "#9aa0a6" : genreColor(ev.genre),
    fillOpacity: past ? 0.45 : 0.95,
  });
}

function chipMarker(ev, past) {
  const color = past ? "#9aa0a6" : genreColor(ev.genre);
  const tags = (ev.tags || []).filter(Boolean);
  const label = (tags.length ? tags : [ev.genre]).filter(Boolean).join(" · ")
    || ev.title || "";
  const html =
    `<span class="map-chip${past ? " map-chip--past" : ""}" ` +
    `style="--chip:${color}">` +
    `<span class="map-chip-dot"></span>${escapeHtml(label)}</span>`;
  return L.marker([ev.lat, ev.lng], {
    icon: L.divIcon({ className: "map-chip-wrap", html, iconSize: null }),
  });
}

function showMapNote(placed, total) {
  let note = document.getElementById("map-note");
  if (!note) {
    note = document.createElement("div");
    note.id = "map-note";
    note.className = "map-note";
    els.mapView.appendChild(note);
  }
  if (total === 0) note.textContent = "Keine Veranstaltungen gefunden.";
  else if (placed < total) note.textContent = `${placed} von ${total} verortet`;
  else note.textContent = `${placed} Veranstaltungen`;
}

// Same palette as the genre badges in style.css (.g-kultur etc.).
const GENRE_COLORS = {
  Kultur: "#d2691e", Polit: "#d63031", Queer: "#9b30d0", Kink: "#111111",
};
function genreColor(genre) { return GENRE_COLORS[genre] || "#666"; }

let toastTimer = null;
function toast(msg) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    el.className = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 1800);
}

// ---------------- Day tabs ----------------

function buildDayTabs(sortedKeys, groups) {
  els.dayTabs.innerHTML = "";
  for (const key of sortedKeys) {
    const { date } = groups.get(key);
    const tab = document.createElement("button");
    tab.className = "day-tab";
    tab.dataset.key = key;
    tab.innerHTML =
      `<span class="dow">${TAB_DOW_FMT.format(date).replace(".", "")}</span>` +
      `<span>${TAB_DATE_FMT.format(date)}</span>`;
    tab.addEventListener("click", () => {
      if (state.viewMode === "map") {
        state.mapDay = key;
        render();
      } else {
        const target = document.getElementById(`day-${key}`);
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
    els.dayTabs.appendChild(tab);
  }
}

let dayIO = null;
let lastActiveKey = null;

// Scroll-spy via IntersectionObserver: only recompute the active day when a day
// heading actually crosses the header line (not on every scroll frame).
function setupScrollSpy(sortedKeys) {
  if (dayIO) dayIO.disconnect();
  const sections = sortedKeys
    .map((k) => document.getElementById(`day-${k}`))
    .filter(Boolean);
  lastActiveKey = null;
  if (!sections.length) return;

  const header = document.querySelector(".site-header");
  const offset = () => (header ? header.offsetHeight : 0) + 6;
  const recompute = () => {
    const top = offset();
    let activeKey = sortedKeys[0];
    for (const sec of sections) {
      if (sec.getBoundingClientRect().top <= top) activeKey = sec.id.slice(4);
      else break;
    }
    if (activeKey !== lastActiveKey) {
      lastActiveKey = activeKey;
      setActiveTab(activeKey);
    }
  };
  dayIO = new IntersectionObserver(recompute, {
    rootMargin: `-${offset()}px 0px 0px 0px`,
    threshold: 0,
  });
  for (const sec of sections) dayIO.observe(sec);
  recompute();
}

function setActiveTab(key) {
  for (const tab of els.dayTabs.children) {
    const active = tab.dataset.key === key;
    tab.classList.toggle("active", active);
    if (active) tab.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
  }
}

// ---------------- Helpers ----------------

function toggleSet(set, value) {
  if (set.has(value)) set.delete(value); else set.add(value);
}

function genreClass(genre) {
  return "g-" + String(genre || "").toLowerCase();
}

// Cinema events: list all screenings, grouped by cinema (time chips).
function renderShowings(ev) {
  if (!ev.showings || !ev.showings.length) return null;
  const wrap = document.createElement("div");
  wrap.className = "showings";
  const byCinema = new Map();
  for (const s of ev.showings) {
    if (!byCinema.has(s.cinema)) byCinema.set(s.cinema, []);
    byCinema.get(s.cinema).push(s);
  }
  for (const [cinema, list] of byCinema) {
    const row = document.createElement("div");
    row.className = "showing-row";
    const name = document.createElement("span");
    name.className = "showing-cinema";
    name.textContent = cinema;
    row.appendChild(name);
    const times = document.createElement("span");
    times.className = "showing-times";
    for (const s of list) {
      const t = document.createElement(s.url ? "a" : "span");
      t.className = "showing-time";
      t.textContent = s.time + (s.note ? " " + s.note : "");
      if (s.url) {
        t.href = s.url;
        t.target = "_blank";
        t.rel = "noopener noreferrer";
        t.addEventListener("click", (e) => e.stopPropagation());
      }
      times.appendChild(t);
    }
    row.appendChild(times);
    wrap.appendChild(row);
  }
  return wrap;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function formatTime(ev) {
  const start = new Date(ev.start);
  const end = ev.end ? new Date(ev.end) : null;
  // Multi-day run (e.g. an exhibition) -> show "… bis TT.MM.JJJJ".
  const multiDay = end && end > start && end.toDateString() !== start.toDateString();
  if (ev.time_known === false) {
    let label = CARD_DATE_FMT.format(start);
    if (multiDay) label += " · bis " + END_FMT.format(end);
    return label;
  }
  let label = CARD_DATE_FMT.format(start) + " · " + TIME_FMT.format(start) + " Uhr";
  if (end) {
    if (start.toDateString() === end.toDateString()) {
      label += " – " + TIME_FMT.format(end) + " Uhr";
    } else if (multiDay) {
      label += " · bis " + END_FMT.format(end);
    }
  }
  return label;
}
