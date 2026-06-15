"use strict";

// Loads the generated feed (data/events.json) and renders it grouped by
// day, with category + genre filters, search, favourites, a detail modal,
// calendar export and sharing. No build step, no framework.

const GENRE_ORDER = ["Kultur", "Polit", "Queer", "Kink"];
const CATEGORY_ORDER = ["Theater", "Film", "Konzert", "Party", "Vortrag",
  "Protest", "Workshop", "Ausstellung", "Essen", "Sonstiges"];
const FAV_KEY = "ek_favorites";
const THEME_KEY = "ek_theme";
const SOURCES_KEY = "ek_disabled_sources";
const REPO = "flipssssss/Eventkalender";

const state = {
  events: [],
  activeTags: new Set(),
  activeGenres: new Set(),
  query: "",
  onlyFav: false,
  favorites: loadFavorites(),
  disabledSources: loadDisabledSources(),
};

const els = {
  feed: document.getElementById("feed"),
  status: document.getElementById("status"),
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
  sourceToggles: document.getElementById("source-toggles"),
  wishText: document.getElementById("wish-text"),
  wishSend: document.getElementById("wish-send"),
  wishList: document.getElementById("wish-list"),
};

const DAY_FMT = new Intl.DateTimeFormat("de-DE", {
  weekday: "long", day: "numeric", month: "long", year: "numeric",
});
const TIME_FMT = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });
const CARD_DATE_FMT = new Intl.DateTimeFormat("de-DE", {
  weekday: "short", day: "numeric", month: "numeric",
});
const TAB_DOW_FMT = new Intl.DateTimeFormat("de-DE", { weekday: "short" });
const TAB_DATE_FMT = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric" });

let dayObserver = null;

// Offline-Fähigkeit (PWA).
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("sw.js").catch(() => {});
  });
}

init();

async function init() {
  try {
    const res = await fetch("data/events.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.events = Array.isArray(data.events) ? data.events : [];
    updateMeta(data);
    buildGenreFilter();
    buildTagFilter();
    render();
  } catch (err) {
    els.status.textContent =
      "Konnte den Veranstaltungs-Feed nicht laden. (" + err.message + ")";
  }

  els.search.addEventListener("input", (e) => {
    state.query = e.target.value.trim().toLowerCase();
    render();
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

  // Modal close handlers.
  els.modalClose.addEventListener("click", closeModal);
  els.modalBackdrop.addEventListener("click", (e) => {
    if (e.target === els.modalBackdrop) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") { closeModal(); closeSettings(); }
  });

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

  // Source wishes -> simple local list, no login.
  els.wishSend.addEventListener("click", () => {
    const text = (els.wishText.value || "").trim();
    if (!text) { els.wishText.focus(); return; }
    const wishes = loadWishes();
    wishes.push(text);
    saveWishes(wishes);
    els.wishText.value = "";
    renderWishes();
  });
  renderWishes();
}

function renderWishes() {
  const wishes = loadWishes();
  els.wishList.innerHTML = "";
  wishes.forEach((text, i) => {
    const li = document.createElement("li");
    li.className = "wish-item";
    const span = document.createElement("span");
    span.textContent = text;
    const del = document.createElement("button");
    del.className = "wish-del";
    del.setAttribute("aria-label", "Entfernen");
    del.textContent = "✕";
    del.addEventListener("click", () => {
      const list = loadWishes();
      list.splice(i, 1);
      saveWishes(list);
      renderWishes();
    });
    li.appendChild(span);
    li.appendChild(del);
    els.wishList.appendChild(li);
  });
}

function loadWishes() {
  try { return JSON.parse(localStorage.getItem("ek_wishes") || "[]"); }
  catch { return []; }
}
function saveWishes(list) {
  try { localStorage.setItem("ek_wishes", JSON.stringify(list)); }
  catch { /* ignore */ }
}

function setTheme(theme) {
  if (theme === "buergi") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem(THEME_KEY, theme); } catch { /* ignore */ }
  for (const btn of els.themeOptions.querySelectorAll(".theme-btn")) {
    btn.classList.toggle("active", btn.dataset.theme === theme);
  }
}

function buildSourceToggles() {
  const sources = [...new Set(state.events.map((e) => e.source_name).filter(Boolean))].sort();
  els.sourceToggles.innerHTML = "";
  for (const src of sources) {
    const label = document.createElement("label");
    label.className = "source-toggle";
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.checked = !state.disabledSources.has(src);
    cb.addEventListener("change", () => {
      if (cb.checked) state.disabledSources.delete(src);
      else state.disabledSources.add(src);
      saveDisabledSources();
      render();
    });
    label.appendChild(cb);
    label.appendChild(document.createTextNode(src));
    els.sourceToggles.appendChild(label);
  }
}

function openSettings() {
  buildSourceToggles();
  els.settingsBackdrop.removeAttribute("hidden");
  document.body.style.overflow = "hidden";
}
function closeSettings() {
  els.settingsBackdrop.setAttribute("hidden", "");
  if (els.modalBackdrop.hasAttribute("hidden")) document.body.style.overflow = "";
}

function loadDisabledSources() {
  try { return new Set(JSON.parse(localStorage.getItem(SOURCES_KEY) || "[]")); }
  catch { return new Set(); }
}
function saveDisabledSources() {
  try { localStorage.setItem(SOURCES_KEY, JSON.stringify([...state.disabledSources])); }
  catch { /* ignore */ }
}

function updateMeta(data) {
  if (data.generated_at) {
    const when = new Date(data.generated_at);
    els.footer.textContent =
      "Zuletzt aktualisiert: " + when.toLocaleString("de-DE") + " · Eventkalender";
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

function matches(ev) {
  // Category (OR within categories).
  if (state.activeTags.size > 0) {
    if (!(ev.tags || []).some((t) => state.activeTags.has(t))) return false;
  }
  // Genre (OR within genres).
  if (state.activeGenres.size > 0) {
    if (!state.activeGenres.has(ev.genre)) return false;
  }
  // Disabled sources (Einstellungen).
  if (state.disabledSources.has(ev.source_name)) return false;
  // Favourites only.
  if (state.onlyFav && !state.favorites.has(eventId(ev))) return false;
  // Text search.
  if (state.query) {
    const haystack = [ev.title, ev.location, ev.description, ev.source_name,
      ev.genre, (ev.tags || []).join(" ")]
      .filter(Boolean).join(" ").toLowerCase();
    if (!haystack.includes(state.query)) return false;
  }
  return true;
}

// ---------------- Rendering ----------------

function render() {
  const visible = state.events.filter(matches);

  if (visible.length === 0) {
    els.feed.innerHTML = '<p class="status">Keine Veranstaltungen gefunden.</p>';
    els.dayTabs.innerHTML = "";
    return;
  }

  const groups = new Map();
  for (const ev of visible) {
    const key = new Date(ev.start).toISOString().slice(0, 10);
    if (!groups.has(key)) groups.set(key, { date: new Date(ev.start), events: [] });
    groups.get(key).events.push(ev);
  }

  const sortedKeys = [...groups.keys()].sort();
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

    const cards = document.createElement("div");
    cards.className = "cards";
    for (const ev of events) cards.appendChild(renderCard(ev));
    group.appendChild(cards);
    frag.appendChild(group);
  }

  els.feed.innerHTML = "";
  els.feed.appendChild(frag);

  buildDayTabs(sortedKeys, groups);
  setupScrollSpy(sortedKeys);
}

function renderCard(ev) {
  const card = document.createElement("div");
  card.className = "card";
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.addEventListener("click", () => openModal(ev));
  card.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openModal(ev); }
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
  time.textContent = formatTime(ev);
  body.appendChild(time);

  const title = document.createElement("h3");
  title.className = "card-title";
  title.textContent = ev.title || "Ohne Titel";
  body.appendChild(title);

  if (ev.location) {
    const loc = document.createElement("div");
    loc.className = "card-location";
    loc.textContent = "📍 " + ev.location;
    body.appendChild(loc);
  }
  if (ev.description) {
    const desc = document.createElement("p");
    desc.className = "card-desc";
    desc.textContent = ev.description;
    body.appendChild(desc);
  }
  const tagWrap = document.createElement("div");
  tagWrap.className = "card-tags";
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

function openModal(ev) {
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

  const time = document.createElement("div");
  time.className = "modal-time";
  time.textContent = formatTime(ev);
  body.appendChild(time);

  const title = document.createElement("h2");
  title.className = "modal-title";
  title.textContent = ev.title || "Ohne Titel";
  body.appendChild(title);

  if (ev.location) {
    const loc = document.createElement("div");
    loc.className = "modal-location";
    loc.textContent = "📍 " + ev.location;
    body.appendChild(loc);
  }

  // Tags + genre.
  const meta = document.createElement("div");
  meta.className = "card-tags";
  for (const tag of ev.tags || []) {
    const t = document.createElement("span");
    t.className = "card-tag";
    t.textContent = tag;
    meta.appendChild(t);
  }
  if (ev.genre) {
    const g = document.createElement("span");
    g.className = "card-tag genre-badge " + genreClass(ev.genre);
    g.textContent = ev.genre;
    meta.appendChild(g);
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
  shareBtn.textContent = "↗ Teilen";
  shareBtn.addEventListener("click", () => shareEvent(ev));
  actions.appendChild(shareBtn);

  if (ev.source_url) {
    const link = document.createElement("a");
    link.className = "btn btn--primary";
    link.href = ev.source_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = "Zur Veranstaltung ↗";
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

function closeModal() {
  els.modalBackdrop.setAttribute("hidden", "");
  document.body.style.overflow = "";
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
    "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Eventkalender//DE",
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

// ---------------- Share ----------------

async function shareEvent(ev) {
  const url = ev.source_url || location.href;
  const text = ev.title + " · " + formatTime(ev) + (ev.location ? " · " + ev.location : "");
  if (navigator.share) {
    try { await navigator.share({ title: ev.title, text, url }); } catch { /* cancelled */ }
  } else {
    try { await navigator.clipboard.writeText(text + " — " + url); toast("Link kopiert"); }
    catch { prompt("Link kopieren:", url); }
  }
}

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
      const target = document.getElementById(`day-${key}`);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    els.dayTabs.appendChild(tab);
  }
}

let spyHandler = null;
let lastActiveKey = null;

// Robust scroll-spy: the active day is the last heading scrolled past the
// bottom of the sticky header.
function setupScrollSpy(sortedKeys) {
  const sections = sortedKeys
    .map((k) => document.getElementById(`day-${k}`))
    .filter(Boolean);
  if (spyHandler) window.removeEventListener("scroll", spyHandler);
  lastActiveKey = null;

  spyHandler = () => {
    const header = document.querySelector(".site-header");
    const offset = (header ? header.offsetHeight : 0) + 6;
    let activeKey = sortedKeys[0];
    for (const sec of sections) {
      if (sec.getBoundingClientRect().top <= offset) activeKey = sec.id.slice(4);
      else break;
    }
    if (activeKey !== lastActiveKey) {
      lastActiveKey = activeKey;
      setActiveTab(activeKey);
    }
  };
  window.addEventListener("scroll", spyHandler, { passive: true });
  spyHandler();
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

function formatTime(ev) {
  const start = new Date(ev.start);
  if (ev.time_known === false) return CARD_DATE_FMT.format(start);
  let label = CARD_DATE_FMT.format(start) + " · " + TIME_FMT.format(start) + " Uhr";
  if (ev.end) {
    const end = new Date(ev.end);
    if (start.toDateString() === end.toDateString()) {
      label += " – " + TIME_FMT.format(end) + " Uhr";
    }
  }
  return label;
}
