"use strict";

// Loads the generated feed (data/events.json) and renders it grouped by
// day, with a search box and tag filters. No build step, no framework.

const state = {
  events: [],
  activeTags: new Set(),
  query: "",
};

const els = {
  feed: document.getElementById("feed"),
  status: document.getElementById("status"),
  search: document.getElementById("search"),
  tagFilter: document.getElementById("tag-filter"),
  subtitle: document.getElementById("subtitle"),
  footer: document.getElementById("footer-note"),
  dayTabs: document.getElementById("day-tabs"),
  filterToggle: document.getElementById("filter-toggle"),
  filterPanel: document.getElementById("filter-panel"),
};

const DAY_FMT = new Intl.DateTimeFormat("de-DE", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

const TIME_FMT = new Intl.DateTimeFormat("de-DE", {
  hour: "2-digit",
  minute: "2-digit",
});

const CARD_DATE_FMT = new Intl.DateTimeFormat("de-DE", {
  weekday: "short",
  day: "numeric",
  month: "numeric",
});

const TAB_DOW_FMT = new Intl.DateTimeFormat("de-DE", { weekday: "short" });
const TAB_DATE_FMT = new Intl.DateTimeFormat("de-DE", {
  day: "numeric",
  month: "numeric",
});

let dayObserver = null;

init();

async function init() {
  try {
    const res = await fetch("data/events.json", { cache: "no-cache" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    state.events = Array.isArray(data.events) ? data.events : [];
    updateMeta(data);
    buildTagFilter();
    render();
  } catch (err) {
    els.status.textContent =
      "Konnte den Veranstaltungs-Feed nicht laden. " +
      "Wurde das Tool schon einmal ausgeführt? (" + err.message + ")";
  }

  els.search.addEventListener("input", (e) => {
    state.query = e.target.value.trim().toLowerCase();
    render();
  });

  // Collapsible search & tags panel.
  els.filterToggle.addEventListener("click", () => {
    const open = els.filterPanel.hasAttribute("hidden");
    if (open) {
      els.filterPanel.removeAttribute("hidden");
    } else {
      els.filterPanel.setAttribute("hidden", "");
    }
    els.filterToggle.setAttribute("aria-expanded", String(open));
  });
}

function updateMeta(data) {
  const count = data.count ?? state.events.length;
  els.subtitle.textContent = `${count} Termine`;

  if (data.generated_at) {
    const when = new Date(data.generated_at);
    els.footer.textContent =
      "Zuletzt aktualisiert: " +
      when.toLocaleString("de-DE") +
      " · Eventkalender";
  }
}

function allTags() {
  const counts = new Map();
  for (const ev of state.events) {
    for (const tag of ev.tags || []) {
      counts.set(tag, (counts.get(tag) || 0) + 1);
    }
  }
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], "de"))
    .map(([tag]) => tag);
}

function buildTagFilter() {
  const tags = allTags();
  els.tagFilter.innerHTML = "";
  for (const tag of tags) {
    const chip = document.createElement("button");
    chip.className = "tag-chip";
    chip.textContent = tag;
    chip.addEventListener("click", () => {
      if (state.activeTags.has(tag)) {
        state.activeTags.delete(tag);
        chip.classList.remove("active");
      } else {
        state.activeTags.add(tag);
        chip.classList.add("active");
      }
      render();
    });
    els.tagFilter.appendChild(chip);
  }
}

function matches(ev) {
  // Tag filter: event must contain ALL selected tags.
  if (state.activeTags.size > 0) {
    const evTags = new Set(ev.tags || []);
    for (const t of state.activeTags) {
      if (!evTags.has(t)) return false;
    }
  }
  // Text search across the visible fields.
  if (state.query) {
    const haystack = [
      ev.title,
      ev.location,
      ev.description,
      ev.source_name,
      (ev.tags || []).join(" "),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();
    if (!haystack.includes(state.query)) return false;
  }
  return true;
}

function render() {
  const visible = state.events.filter(matches);

  if (visible.length === 0) {
    els.feed.innerHTML =
      '<p class="status">Keine Veranstaltungen gefunden.</p>';
    return;
  }

  // Group by calendar day.
  const groups = new Map();
  for (const ev of visible) {
    const date = new Date(ev.start);
    const key = date.toISOString().slice(0, 10);
    if (!groups.has(key)) groups.set(key, { date, events: [] });
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
    for (const ev of events) {
      cards.appendChild(renderCard(ev));
    }
    group.appendChild(cards);
    frag.appendChild(group);
  }

  els.feed.innerHTML = "";
  els.feed.appendChild(frag);

  buildDayTabs(sortedKeys, groups);
  setupScrollSpy(sortedKeys);
}

// The list stays continuous; the tabs just jump to a day.
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

// Highlight the tab for the day currently at the top of the list.
function setupScrollSpy(sortedKeys) {
  if (dayObserver) dayObserver.disconnect();
  dayObserver = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) setActiveTab(entry.target.dataset.key);
      }
    },
    { rootMargin: "-110px 0px -80% 0px", threshold: 0 }
  );
  for (const key of sortedKeys) {
    const heading = document.querySelector(`#day-${key} .day-heading`);
    if (heading) dayObserver.observe(heading);
  }
  if (sortedKeys.length) setActiveTab(sortedKeys[0]);
}

function setActiveTab(key) {
  for (const tab of els.dayTabs.children) {
    const active = tab.dataset.key === key;
    tab.classList.toggle("active", active);
    if (active) {
      tab.scrollIntoView({ inline: "center", block: "nearest", behavior: "smooth" });
    }
  }
}

function renderCard(ev) {
  const card = document.createElement("a");
  card.className = "card";
  card.href = ev.source_url || "#";
  card.target = "_blank";
  card.rel = "noopener noreferrer";

  // Image only when one exists. No placeholder: cards without an image
  // simply start with the text, no empty graphic.
  if (ev.image_url) {
    const img = document.createElement("img");
    img.className = "card-image";
    img.src = ev.image_url;
    img.alt = ev.title || "";
    img.loading = "lazy";
    // If the image fails to load, drop it rather than leaving a gap.
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

  if (ev.tags && ev.tags.length) {
    const tagWrap = document.createElement("div");
    tagWrap.className = "card-tags";
    for (const tag of ev.tags) {
      const t = document.createElement("span");
      t.className = "card-tag";
      t.textContent = tag;
      tagWrap.appendChild(t);
    }
    body.appendChild(tagWrap);
  }

  if (ev.source_name) {
    const src = document.createElement("div");
    src.className = "card-source";
    src.textContent = "Quelle: " + ev.source_name;
    body.appendChild(src);
  }

  card.appendChild(body);
  return card;
}

function formatTime(ev) {
  const start = new Date(ev.start);
  // Date next to the time on every card (e.g. "Mi., 10.6. · 19:00 Uhr").
  let label = CARD_DATE_FMT.format(start) + " · " + TIME_FMT.format(start) + " Uhr";
  if (ev.end) {
    const end = new Date(ev.end);
    const sameDay = start.toDateString() === end.toDateString();
    if (sameDay) {
      label += " – " + TIME_FMT.format(end) + " Uhr";
    }
  }
  return label;
}
