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

// Echte (vereinfachte) Bezirksgrenzen aus Geodaten -> SVG-Pfade.
const BEZIRK_GEO = { w: 360, h: 296, paths: [
  { b: "Mitte", cx: 148.5, cy: 125.3, l: ["Mitte"], d: "M152.4,151.0 L153.4,151.3 L154.8,147.3 L155.5,148.2 L166.3,147.2 L166.9,146.0 L171.0,148.9 L172.1,148.2 L174.3,150.7 L181.3,149.3 L182.5,146.8 L179.0,143.5 L182.4,135.6 L175.0,130.1 L169.8,128.2 L171.2,124.1 L166.2,109.5 L165.1,109.7 L165.2,103.0 L163.2,97.7 L160.7,94.8 L158.3,94.8 L155.3,96.2 L154.5,101.0 L151.2,101.1 L148.1,103.2 L147.8,100.5 L145.4,101.1 L145.2,99.9 L139.5,99.8 L133.1,97.6 L130.3,100.1 L127.6,99.4 L118.4,103.5 L114.1,111.4 L122.8,111.9 L128.8,120.7 L119.4,123.0 L120.2,126.2 L122.6,125.8 L120.4,127.7 L122.2,135.9 L124.8,132.7 L128.6,134.5 L129.1,138.4 L132.6,141.7 L129.6,143.0 L131.5,144.0 L129.3,145.4 L131.8,146.6 L132.3,149.2 L150.4,155.4 L152.4,151.0Z" },
  { b: "Friedrichshain-Kreuzberg", cx: 182.1, cy: 151.1, l: ["Fhain-", "Kreuzb."], d: "M190.7,159.4 L195.7,156.4 L207.1,162.8 L208.8,165.7 L210.5,165.2 L211.1,166.6 L215.7,164.6 L205.9,155.2 L203.5,154.6 L207.6,145.1 L207.4,141.2 L208.4,141.3 L206.5,137.5 L205.3,136.1 L200.3,136.8 L196.3,135.6 L194.7,129.9 L192.0,131.1 L189.4,127.1 L187.5,129.0 L179.4,129.8 L177.3,131.8 L182.4,135.7 L179.0,143.5 L182.5,146.8 L181.3,149.3 L174.3,150.7 L172.1,148.2 L171.0,148.9 L166.9,146.0 L166.3,147.2 L155.5,148.2 L154.8,147.3 L150.5,155.3 L149.8,160.2 L154.2,161.8 L152.9,167.3 L151.5,167.5 L163.7,166.8 L163.7,168.3 L170.2,169.4 L171.0,164.1 L179.4,166.3 L180.4,164.8 L177.7,157.9 L187.8,163.4 L190.7,159.4Z" },
  { b: "Pankow", cx: 188.3, cy: 68.8, l: ["Pankow"], d: "M189.4,127.1 L192.0,131.1 L194.7,129.9 L196.3,135.6 L200.3,136.8 L205.3,136.1 L196.8,129.5 L203.5,123.8 L202.3,122.1 L204.1,118.7 L202.6,112.0 L209.4,112.5 L209.4,110.7 L212.8,108.2 L217.3,109.6 L217.5,104.9 L211.5,97.7 L213.6,93.4 L211.1,90.4 L209.3,90.4 L209.6,81.9 L214.0,75.4 L223.0,69.5 L219.7,61.8 L218.5,62.0 L219.5,56.9 L223.2,49.1 L223.4,43.7 L229.8,40.4 L232.3,30.5 L232.6,26.8 L231.2,26.9 L230.6,25.1 L227.1,26.5 L215.3,18.2 L212.4,14.1 L214.1,4.2 L207.3,7.8 L206.6,6.4 L209.3,0.0 L208.1,1.4 L207.2,0.4 L202.0,7.4 L198.6,5.7 L193.9,11.3 L200.1,15.8 L206.1,16.7 L206.2,19.0 L198.7,24.1 L192.4,22.4 L188.6,23.1 L188.1,26.6 L184.9,27.5 L184.3,33.5 L181.5,33.4 L179.8,35.2 L173.4,28.1 L171.0,28.8 L165.7,23.9 L163.8,24.6 L161.0,33.3 L157.0,34.4 L157.6,35.4 L153.8,38.6 L154.1,41.4 L149.1,43.7 L154.1,56.6 L151.1,66.6 L145.7,74.1 L138.7,75.1 L160.5,93.2 L163.8,98.6 L165.1,109.7 L166.2,109.5 L171.2,124.1 L169.8,128.2 L177.3,131.8 L179.4,129.8 L187.5,129.0 L189.4,127.1Z" },
  { b: "Charlottenburg-Wilmersdorf", cx: 97.3, cy: 153.4, l: ["Charlb.-", "Wilm."], d: "M117.3,182.5 L123.9,183.3 L124.2,174.1 L133.1,173.5 L134.1,154.8 L133.0,153.7 L135.4,150.0 L131.4,148.5 L131.8,146.6 L129.3,145.4 L131.5,144.0 L129.6,143.0 L132.6,141.7 L129.2,138.6 L127.7,133.4 L124.4,132.9 L122.2,135.9 L120.4,127.7 L122.6,125.8 L120.2,126.2 L119.4,123.0 L128.8,120.7 L122.8,111.9 L97.5,110.8 L99.0,116.5 L98.4,120.2 L103.8,124.3 L103.0,127.9 L89.1,130.5 L84.7,129.4 L85.2,133.0 L81.1,131.4 L71.5,131.3 L70.1,135.5 L71.0,142.3 L69.6,142.6 L68.1,146.2 L66.1,146.1 L64.9,151.7 L54.3,156.5 L52.6,163.7 L54.5,169.6 L52.9,173.0 L53.4,179.1 L57.9,179.5 L59.2,181.8 L61.6,180.2 L65.9,181.2 L76.6,180.0 L91.4,183.7 L107.4,180.2 L117.3,182.5Z" },
  { b: "Spandau", cx: 48.4, cy: 131.6, l: ["Span-", "dau"], d: "M68.1,146.1 L69.6,142.6 L71.0,142.3 L70.1,135.5 L71.5,131.3 L81.1,131.4 L85.2,133.0 L84.7,129.4 L88.8,130.5 L99.7,128.9 L103.0,127.9 L103.8,124.3 L98.4,120.2 L99.0,116.5 L97.4,110.9 L88.1,110.0 L74.9,98.8 L73.2,90.2 L69.8,86.5 L67.9,80.6 L69.1,77.4 L63.7,76.6 L63.3,78.2 L40.8,67.5 L36.8,68.5 L29.5,75.4 L21.7,77.5 L21.2,81.2 L22.4,81.3 L23.6,84.3 L32.8,81.0 L34.7,84.9 L34.9,89.9 L30.7,101.0 L30.6,107.9 L25.7,108.0 L22.6,105.1 L16.7,127.6 L15.5,139.3 L29.3,137.0 L43.1,146.2 L21.4,172.1 L15.7,174.2 L15.5,177.8 L11.9,184.5 L13.0,191.5 L11.2,197.7 L18.6,207.4 L32.2,204.1 L44.1,192.9 L47.7,193.1 L51.9,187.2 L52.6,183.7 L52.9,173.0 L54.5,169.6 L52.6,163.7 L54.3,156.5 L64.9,151.7 L65.6,146.8 L68.1,146.1Z" },
  { b: "Steglitz-Zehlendorf", cx: 80.9, cy: 211.5, l: ["Steglitz-", "Zehlend."], d: "M96.7,238.5 L100.3,237.6 L111.5,227.9 L111.1,229.5 L119.7,243.0 L136.4,231.9 L136.1,229.8 L147.3,223.2 L151.4,215.9 L143.3,193.3 L139.5,192.3 L139.5,190.5 L134.0,183.7 L132.6,183.0 L128.3,185.6 L124.5,183.3 L118.9,183.4 L107.4,180.2 L91.4,183.7 L76.6,180.0 L65.9,181.2 L61.6,180.2 L59.2,181.8 L57.9,179.5 L53.4,179.1 L51.9,187.2 L47.7,193.1 L44.1,192.9 L32.2,204.1 L19.1,206.5 L12.7,213.8 L13.1,216.5 L8.7,221.1 L5.9,219.9 L4.0,222.9 L0.0,225.0 L1.3,232.0 L4.8,233.9 L5.7,232.6 L4.3,230.7 L6.7,230.1 L6.7,233.0 L9.4,233.8 L10.0,230.6 L11.4,230.9 L12.5,233.0 L9.6,234.6 L19.5,245.0 L24.2,242.8 L26.6,244.1 L25.0,244.5 L27.1,245.7 L22.4,250.6 L22.9,249.4 L20.8,249.6 L20.5,251.4 L23.0,253.4 L24.4,252.1 L22.5,250.7 L28.6,244.8 L37.7,247.5 L43.0,247.1 L44.6,246.0 L44.3,244.1 L37.1,245.4 L37.9,239.7 L58.3,228.6 L64.9,227.5 L73.2,223.7 L84.3,223.6 L86.4,237.8 L90.6,236.6 L96.7,238.5Z" },
  { b: "Tempelhof-Schöneberg", cx: 156.4, cy: 206.0, l: ["Tempelh.-", "Schöneb."], d: "M176.4,263.1 L177.9,263.2 L181.4,254.7 L176.6,236.0 L177.3,233.0 L172.5,230.5 L168.1,231.0 L166.5,226.4 L169.3,224.6 L169.7,223.1 L168.1,222.7 L175.8,196.3 L178.1,192.3 L180.9,192.3 L177.8,190.0 L179.2,189.1 L178.3,184.4 L175.8,184.7 L174.0,173.0 L170.3,173.4 L170.2,169.4 L163.7,168.3 L163.7,166.8 L151.5,167.5 L152.9,167.3 L154.2,161.8 L149.8,160.2 L150.6,155.4 L135.5,149.9 L133.0,153.7 L134.1,154.8 L133.1,173.5 L124.2,174.1 L123.9,183.3 L128.3,185.6 L132.6,183.0 L139.5,190.5 L139.5,192.3 L143.3,193.3 L151.6,216.6 L149.6,217.9 L147.2,223.3 L136.1,229.8 L136.3,235.5 L145.0,243.6 L151.8,247.7 L150.9,252.4 L160.0,252.3 L160.6,261.7 L176.4,263.1Z" },
  { b: "Neukölln", cx: 196.2, cy: 206.3, l: ["Neukölln"], d: "M199.3,224.0 L203.2,224.6 L209.4,245.8 L228.8,240.6 L231.9,235.7 L233.1,230.3 L230.1,222.1 L231.2,218.8 L223.7,216.4 L201.9,199.1 L199.6,195.6 L197.3,190.1 L206.9,190.5 L208.8,186.0 L204.2,177.9 L204.5,174.6 L197.9,166.8 L196.8,168.1 L191.8,164.0 L190.5,165.3 L177.7,157.9 L180.4,164.8 L179.4,166.3 L171.0,164.1 L170.0,171.0 L170.3,173.4 L174.0,173.0 L175.8,184.7 L178.3,184.4 L179.2,189.1 L177.8,190.0 L180.9,192.3 L178.1,192.3 L175.8,196.3 L168.1,222.7 L169.7,223.1 L169.3,224.6 L166.5,226.4 L168.1,231.0 L172.5,230.5 L177.2,233.3 L199.3,224.0Z" },
  { b: "Treptow-Köpenick", cx: 279.9, cy: 216.2, l: ["Treptow-", "Köpen."], d: "M304.5,284.5 L309.2,279.1 L309.5,275.3 L311.9,271.7 L317.7,268.9 L320.5,271.0 L323.1,271.0 L326.6,264.9 L327.6,262.3 L325.8,262.0 L326.7,258.5 L320.8,257.2 L320.2,255.1 L322.4,254.8 L326.4,249.5 L326.6,250.5 L335.8,242.5 L339.5,243.8 L343.9,242.2 L348.0,235.8 L343.2,227.8 L343.9,224.2 L347.4,218.7 L349.4,218.7 L349.6,217.4 L348.1,216.8 L348.7,213.7 L343.4,212.4 L339.5,209.6 L344.1,212.5 L350.2,213.3 L350.9,208.7 L354.3,205.8 L357.4,205.6 L356.4,210.0 L359.4,210.4 L359.9,208.9 L356.9,208.4 L357.5,201.6 L353.6,199.4 L342.8,197.6 L338.3,192.3 L335.8,186.9 L333.4,186.5 L328.0,182.2 L326.8,182.2 L330.1,189.6 L330.1,193.3 L326.4,193.6 L324.8,185.8 L318.1,184.1 L309.8,176.9 L307.3,177.4 L299.6,173.0 L296.9,172.6 L287.3,177.4 L286.0,183.8 L285.1,180.3 L282.9,179.6 L281.8,180.9 L278.1,179.7 L278.3,178.2 L275.4,178.2 L266.5,170.9 L260.5,172.3 L259.8,175.0 L255.4,177.5 L246.2,177.8 L241.6,176.3 L236.7,182.5 L231.9,176.1 L231.2,177.1 L228.1,175.7 L224.5,176.3 L221.3,169.6 L217.2,169.1 L215.3,165.3 L211.1,166.6 L210.5,165.2 L208.8,165.7 L207.1,162.8 L196.2,156.6 L190.8,159.2 L188.0,163.2 L190.5,165.3 L191.8,164.0 L196.8,168.1 L198.0,166.9 L204.5,174.6 L204.2,177.9 L208.7,185.0 L206.9,190.5 L197.3,190.2 L200.3,197.2 L223.7,216.4 L231.2,218.9 L230.1,222.1 L233.1,230.3 L231.9,235.7 L228.8,240.6 L236.2,244.6 L240.8,241.6 L239.3,251.9 L254.6,252.6 L269.9,247.6 L271.1,253.5 L277.2,260.5 L276.9,265.4 L289.0,258.6 L291.6,263.1 L296.6,262.0 L296.3,267.9 L298.8,268.4 L299.0,271.2 L294.7,276.5 L293.2,289.0 L298.3,296.1 L301.4,295.4 L301.1,292.7 L304.5,284.5Z" },
  { b: "Marzahn-Hellersdorf", cx: 262.4, cy: 135.6, l: ["Marz.-", "Hell."], d: "M266.6,171.0 L279.8,180.3 L282.6,176.4 L281.0,175.7 L281.7,171.2 L289.7,160.4 L286.6,159.4 L291.4,144.3 L296.5,138.0 L305.1,131.5 L304.2,128.1 L287.5,127.8 L287.1,120.8 L291.9,121.2 L293.8,117.1 L266.5,110.5 L267.1,105.4 L263.9,91.8 L261.9,91.8 L260.4,89.4 L257.0,90.0 L256.5,88.8 L254.7,90.9 L242.3,96.3 L233.8,105.7 L237.5,119.7 L229.2,122.9 L230.7,133.0 L230.2,142.0 L238.4,142.3 L240.3,143.7 L239.1,149.4 L241.4,155.6 L243.8,157.6 L247.1,167.2 L245.9,172.1 L248.1,177.4 L255.9,177.4 L259.8,175.0 L260.5,172.3 L266.6,171.0Z" },
  { b: "Lichtenberg", cx: 225.5, cy: 123.5, l: ["Lichten-", "berg"], d: "M221.3,169.6 L224.5,176.3 L228.1,175.7 L231.2,177.1 L231.9,176.1 L236.7,182.5 L241.6,176.3 L248.4,177.5 L245.9,172.1 L247.1,167.2 L243.8,157.6 L241.4,155.6 L239.1,149.4 L240.3,143.7 L238.4,142.3 L230.2,142.0 L230.7,133.0 L229.2,122.9 L237.5,119.7 L233.8,105.7 L242.3,96.3 L254.7,90.9 L256.5,88.8 L252.7,82.9 L245.5,77.0 L235.1,73.2 L224.6,73.3 L223.0,69.5 L214.0,75.4 L209.5,82.7 L209.3,90.4 L211.1,90.4 L213.6,93.4 L211.5,97.7 L217.5,104.9 L217.3,109.6 L212.8,108.2 L209.4,110.7 L209.4,112.5 L202.8,111.8 L204.1,118.7 L202.3,122.1 L203.5,123.8 L196.8,129.5 L198.8,131.9 L204.1,134.3 L208.4,141.3 L207.4,141.2 L207.6,145.1 L203.5,154.6 L205.9,155.2 L215.7,164.6 L217.2,169.1 L221.3,169.6Z" },
  { b: "Reinickendorf", cx: 108.6, cy: 70.1, l: ["Reinicken-", "dorf"], d: "M124.8,101.3 L127.6,99.4 L130.3,100.1 L133.1,97.6 L139.5,99.8 L145.2,99.9 L145.4,101.1 L147.8,100.5 L148.9,103.1 L151.2,101.1 L154.5,101.0 L155.3,96.2 L161.0,94.3 L138.7,75.1 L145.7,74.1 L150.6,67.4 L154.0,59.6 L153.7,54.6 L149.1,44.0 L144.1,46.2 L132.9,46.5 L120.2,41.6 L114.6,42.5 L118.8,40.0 L116.4,33.5 L118.3,28.8 L113.5,19.4 L118.6,15.9 L117.1,14.0 L104.0,13.0 L103.6,20.0 L105.3,20.2 L104.6,30.2 L97.0,31.5 L93.0,30.6 L94.6,36.0 L94.1,42.8 L70.7,41.5 L68.7,48.7 L60.6,61.5 L69.8,73.1 L67.9,80.6 L69.8,86.5 L73.2,90.2 L74.8,98.6 L87.7,109.8 L114.1,111.4 L118.4,103.5 L124.8,101.3Z" },
] };
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
  bezirkMap: document.getElementById("bezirk-map"),
  bezirkExtra: document.getElementById("bezirk-extra"),
  wishText: document.getElementById("wish-text"),
  wishSend: document.getElementById("wish-send"),
  wishBackdrop: document.getElementById("wish-backdrop"),
  wishClose: document.getElementById("wish-close"),
  openWish: document.getElementById("open-wish"),
  eventBackdrop: document.getElementById("event-backdrop"),
  eventClose: document.getElementById("event-close"),
  openEvent: document.getElementById("open-event"),
  installBtn: document.getElementById("install-btn"),
  installPill: document.getElementById("install-pill"),
  installPillYes: document.getElementById("install-pill-yes"),
  installPillNo: document.getElementById("install-pill-no"),
  installGuide: document.getElementById("install-guide"),
  installGuideClose: document.getElementById("install-guide-close"),
  installGuideSteps: document.getElementById("install-guide-steps"),
  installGuideLead: document.getElementById("install-guide-lead"),
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

// Dezenter "Als App hinzufügen"-Hinweis unten. Erscheint nur beim Erstbesuch
// (nicht in der installierten App) und kommt nach einmaligem Wegklicken nie
// wieder -- gemerkt in localStorage.
const INSTALL_DISMISS_KEY = "mzm-install-dismissed";

function isStandalone() {
  return (window.matchMedia
    && window.matchMedia("(display-mode: standalone)").matches)
    || window.navigator.standalone === true;
}

function dismissInstallPill() {
  if (els.installPill) els.installPill.setAttribute("hidden", "");
  try { localStorage.setItem(INSTALL_DISMISS_KEY, "1"); } catch { /* ignore */ }
}

function setupInstallPill() {
  if (!els.installPill) return;
  els.installPillNo.addEventListener("click", dismissInstallPill);
  els.installPillYes.addEventListener("click", () => {
    // Visuelle Anleitung zeigen; Pille danach nie wieder anbieten.
    openInstallGuide();
    dismissInstallPill();
  });

  // Schon installiert oder früher weggeklickt -> gar nicht erst zeigen.
  let dismissed = false;
  try { dismissed = localStorage.getItem(INSTALL_DISMISS_KEY) === "1"; } catch { /* ignore */ }
  if (dismissed || isStandalone()) return;

  // Etwas verzögert einblenden, damit der Hinweis erst nach dem Ankommen
  // auf der Seite auftaucht und nicht den ersten Eindruck stört.
  setTimeout(() => {
    if (!isStandalone()) els.installPill.removeAttribute("hidden");
  }, 4000);
}

// Kleine Inline-Symbole für die Anleitungsschritte.
const GUIDE_ICONS = {
  // iOS-Teilen-Symbol (Pfeil aus Box).
  share: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 16V4"/><path d="M8 8l4-4 4 4"/><path d="M5 12v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>',
  // "Zum Home-Bildschirm" / installieren (Plus im Kasten).
  plus: '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/><line x1="12" y1="9" x2="12" y2="15"/><line x1="9" y1="12" x2="15" y2="12"/></svg>',
  // Android-Menü (drei Punkte).
  dots: '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor"><circle cx="12" cy="5" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="12" cy="19" r="2"/></svg>',
};

function detectPlatform() {
  const ua = navigator.userAgent || "";
  if (/iphone|ipad|ipod/i.test(ua)
      || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)) {
    return "ios";
  }
  if (/android/i.test(ua)) return "android";
  return "other";
}

// Schritte je Plattform: [Symbol, Text-HTML].
const GUIDE_STEPS = {
  ios: {
    lead: "In Safari in drei Schritten:",
    steps: [
      ["share", "Tippe unten in der Leiste auf <strong>Teilen</strong>."],
      ["plus", "Wähle <strong>Zum Home-Bildschirm</strong>."],
      ["plus", "Tippe oben rechts auf <strong>Hinzufügen</strong> – fertig."],
    ],
  },
  android: {
    lead: "In Chrome in zwei Schritten:",
    steps: [
      ["dots", "Tippe oben rechts auf das <strong>Menü (⋮)</strong>."],
      ["plus", "Wähle <strong>App installieren</strong> bzw. <strong>Zum Startbildschirm</strong>."],
    ],
  },
  other: {
    lead: "Im Browser:",
    steps: [
      ["plus", "Klicke in der Adressleiste auf das <strong>Installieren</strong>-Symbol."],
      ["dots", "Oder im <strong>Menü</strong> des Browsers „App installieren“ wählen."],
    ],
  },
};

function buildInstallGuideSteps() {
  const data = GUIDE_STEPS[detectPlatform()] || GUIDE_STEPS.other;
  els.installGuideLead.textContent = data.lead;
  els.installGuideSteps.innerHTML = "";

  // Wenn der Browser den nativen Dialog anbietet (Android/Desktop-Chrome),
  // einen direkten Knopf zeigen -- sonst die visuellen Schritte.
  if (deferredInstallPrompt) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn btn--primary install-guide__install";
    btn.textContent = "Jetzt installieren";
    btn.addEventListener("click", async () => {
      const p = deferredInstallPrompt;
      deferredInstallPrompt = null;
      try { await p.prompt(); } catch { /* ignore */ }
      closeInstallGuide();
    });
    els.installGuideSteps.appendChild(btn);
    return;
  }

  data.steps.forEach(([icon, text], i) => {
    const row = document.createElement("div");
    row.className = "install-step";
    row.innerHTML =
      `<span class="install-step__num">${i + 1}</span>`
      + `<span class="install-step__icon">${GUIDE_ICONS[icon] || ""}</span>`
      + `<span class="install-step__text">${text}</span>`;
    els.installGuideSteps.appendChild(row);
  });
}

function openInstallGuide() {
  if (!els.installGuide) return;
  buildInstallGuideSteps();
  els.installGuide.removeAttribute("hidden");
  document.body.style.overflow = "hidden";
}

function closeInstallGuide() {
  if (!els.installGuide) return;
  els.installGuide.setAttribute("hidden", "");
  if (els.settingsBackdrop.hasAttribute("hidden")
      && els.modalBackdrop.hasAttribute("hidden")) {
    document.body.style.overflow = "";
  }
}

function setupInstallGuide() {
  if (!els.installGuide) return;
  els.installGuideClose.addEventListener("click", closeInstallGuide);
  els.installGuide.addEventListener("click", (e) => {
    if (e.target === els.installGuide) closeInstallGuide(); // Klick auf Backdrop
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !els.installGuide.hasAttribute("hidden")) {
      closeInstallGuide();
    }
  });
}

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
    headerOffset(); // geänderte Header-Höhe ins Sprungziel übernehmen
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
  setupSheetDrag();
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

  // "Als App hinzufügen" in den Einstellungen öffnet dieselbe visuelle Anleitung.
  els.installBtn.addEventListener("click", () => openInstallGuide());

  // Event-/Quelle-Popups (öffnen über den Einstellungen, schließen dorthin zurück).
  els.openEvent.addEventListener("click", () => openOverlay(els.eventBackdrop));
  els.eventClose.addEventListener("click", () => closeOverlay(els.eventBackdrop));
  els.eventBackdrop.addEventListener("click", (e) => {
    if (e.target === els.eventBackdrop) closeOverlay(els.eventBackdrop);
  });
  els.openWish.addEventListener("click", () => openOverlay(els.wishBackdrop));
  els.wishClose.addEventListener("click", () => closeOverlay(els.wishBackdrop));
  els.wishBackdrop.addEventListener("click", (e) => {
    if (e.target === els.wishBackdrop) closeOverlay(els.wishBackdrop);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    if (!els.eventBackdrop.hasAttribute("hidden")) closeOverlay(els.eventBackdrop);
    else if (!els.wishBackdrop.hasAttribute("hidden")) closeOverlay(els.wishBackdrop);
  });

  setupInstallPill();
  setupInstallGuide();

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
      if (res.ok) {
        els.wishText.value = "";
        closeOverlay(els.wishBackdrop);
        toast("Danke! Vorschlag gesendet.");
      } else { toast("Konnte nicht senden."); }
    } catch { toast("Konnte nicht senden."); }
    els.wishSend.disabled = false;
  });
}

const THEME_COLORS = {
  buergi: "#f3e9d8", punk: "#0b0a0d", hyperpop: "#ffe0fb",
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

// Beschriftung der Karte: bei zweiteiligen Namen nur den ersten Teil zeigen
// (z. B. "Charlottenburg-Wilmersdorf" -> "Charlottenburg"), einzeilig.
function bezirkLines(name) {
  return [name.split("-")[0]];
}

function buildBezirkToggles() {
  const counts = new Map();
  for (const e of state.events) {
    const b = bezirkOf(e);
    if (!counts.has(b)) counts.set(b, 0);
    if (matches(e, { bezirk: true })) counts.set(b, counts.get(b) + 1);
  }

  // Echte Berlin-Umrisse: ein Pfad je Bezirk, an/ausgewählt per Klick.
  const cells = BEZIRK_GEO.paths.map((d) => {
    const off = state.disabledBezirke.has(d.b);
    const lines = bezirkLines(d.b);
    const top = d.cy - (lines.length - 1) * 5 + 3;
    const spans = lines.map((ln, i) =>
      `<tspan x="${d.cx}" dy="${i === 0 ? 0 : 10}">${ln}</tspan>`).join("");
    return `<g class="bezirk-cell${off ? " off" : ""}" data-bezirk="${d.b}" `
      + `role="button" tabindex="0" aria-pressed="${!off}" aria-label="${d.b}">`
      + `<path d="${d.d}"/>`
      + `<text x="${d.cx}" y="${top}" text-anchor="middle">${spans}</text></g>`;
  }).join("");
  els.bezirkMap.innerHTML =
    `<svg viewBox="0 0 ${BEZIRK_GEO.w} ${BEZIRK_GEO.h}" class="bezirk-svg" `
    + `role="group" aria-label="Bezirke auf der Karte wählen">${cells}</svg>`;
  els.bezirkMap.onclick = (e) => toggleBezirkCell(e.target);
  els.bezirkMap.onkeydown = (e) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      toggleBezirkCell(e.target);
    }
  };

  // "Unbekannt" (Events ohne Bezirk) lässt sich nicht verorten -> als Chip.
  els.bezirkExtra.innerHTML = "";
  if (counts.has(BEZIRK_UNKNOWN)) {
    const chip = document.createElement("button");
    chip.type = "button";
    const setCls = () => {
      chip.className = "bezirk-chip"
        + (state.disabledBezirke.has(BEZIRK_UNKNOWN) ? " off" : "");
    };
    setCls();
    chip.textContent = "Ohne Bezirk (" + counts.get(BEZIRK_UNKNOWN) + ")";
    chip.addEventListener("click", () => {
      toggleSet(state.disabledBezirke, BEZIRK_UNKNOWN);
      saveSet(BEZIRKE_KEY, state.disabledBezirke);
      setCls();
      scheduleRender();
    });
    els.bezirkExtra.appendChild(chip);
  }
}

function toggleBezirkCell(target) {
  const cell = target.closest && target.closest(".bezirk-cell");
  if (!cell) return;
  const b = cell.dataset.bezirk;
  toggleSet(state.disabledBezirke, b);
  saveSet(BEZIRKE_KEY, state.disabledBezirke);
  const off = state.disabledBezirke.has(b);
  cell.classList.toggle("off", off);
  cell.setAttribute("aria-pressed", String(!off));
  scheduleRender();
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

// Generic overlay (popups, die über den Einstellungen liegen können).
function anyOverlayOpen(except) {
  return [els.settingsBackdrop, els.modalBackdrop, els.eventBackdrop,
    els.wishBackdrop, els.installGuide]
    .some((el) => el && el !== except && !el.hasAttribute("hidden"));
}
function openOverlay(el) {
  el.removeAttribute("hidden");
  document.body.style.overflow = "hidden";
}
function closeOverlay(el) {
  el.setAttribute("hidden", "");
  if (!anyOverlayOpen(el)) document.body.style.overflow = "";
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

// Ist das Event (am heutigen Tag) schon vorbei? Endzeit vorbei -> vorbei;
// nur Startzeit -> 1 Stunde nach Start; ohne Uhrzeit (ganztägig) nie.
function isPast(ev, now) {
  if (ev.time_known === false) return false;
  const start = new Date(ev.start);
  if (ev.end) return now > new Date(ev.end);
  return now > new Date(start.getTime() + 60 * 60 * 1000);
}

// Schlusszeit aus "10–18" / "10:00–18:00" / "9–17:30" als Dezimalstunde (18.0).
function closingTime(hours) {
  const parts = String(hours).split(/[-–]/);
  if (parts.length < 2) return null;
  const m = parts[1].match(/(\d{1,2})(?::(\d{2}))?/);
  return m ? parseInt(m[1], 10) + (m[2] ? parseInt(m[2], 10) / 60 : 0) : null;
}

// Ausstellung an einem Tag ausgegraut? Bezieht sich auf die ÖFFNUNGSZEITEN,
// nicht die Laufzeit: geschlossener Wochentag, oder (heute) nach Ladenschluss.
function isExhibitionDimmed(ev, date, now) {
  if (!ev.opening_hours) return false;
  const hours = hoursForDay(ev, date);
  if (hours == null) return true;                 // geschlossener Wochentag
  if (dayKey(date) === dayKey(now)) {             // heute: nach Schließung vorbei
    const close = closingTime(hours);
    if (close != null && now.getHours() + now.getMinutes() / 60 >= close) return true;
  }
  return false;
}

function isKino(ev) {
  return (ev.tags || []).includes("Kino");
}

// Vorstellungszeit ("HH:MM") auf den gegebenen Tag setzen.
function showTime(time, day) {
  const m = String(time || "").match(/(\d{1,2}):(\d{2})/);
  if (!m) return null;
  const d = new Date(day);
  d.setHours(parseInt(m[1], 10), parseInt(m[2], 10), 0, 0);
  return d;
}

// Kinofilm ist erst „vorbei", wenn ALLE Vorstellungen des Tages mindestens
// eine Stunde her sind (eine spätere Vorstellung hält ihn im Feed).
function kinoAllPast(ev, date, now) {
  const sh = ev.showings;
  if (!sh || !sh.length) return isPast(ev, now);
  const day = date || new Date(ev.start);
  for (const s of sh) {
    const t = showTime(s.time, day);
    if (!t) return false;                            // unklare Zeit -> nicht vorbei
    if (now <= new Date(t.getTime() + 60 * 60 * 1000)) return false;
  }
  return true;
}

// Ausgegraut/„schon vorbei"? Ausstellungen nach Öffnungszeiten, Kino nach allen
// Vorstellungen, sonst nach Zeit.
function isPastOrClosed(ev, date, now) {
  if (isExhibition(ev)) return isExhibitionDimmed(ev, date, now);
  if (isKino(ev)) return kinoAllPast(ev, date, now);
  return isPast(ev, now);
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
      const todayK = dayKey(new Date());
      let cur = dayStart(new Date(ev.start));
      if (cur < today) cur = new Date(today);
      let last = ev.end ? dayStart(new Date(ev.end)) : new Date(horizon);
      if (last > horizon) last = new Date(horizon);
      for (; cur <= last; cur.setDate(cur.getDate() + 1)) {
        const closed = oh && !oh[WEEKDAY_KEYS[cur.getDay()]];
        if (state.onlyFav) {
          // In den Favoriten nur EINMAL zeigen -- an der ersten offenen
          // Gelegenheit (nicht ausgegraut), statt an jedem offenen Tag.
          if (closed) continue;
          ensureDay(dayKey(cur), cur).events.push(ev);
          break;
        }
        // Geschlossene Wochentage künftig auslassen; heute behalten (wird
        // ausgegraut in "Schon vorbei" gezeigt).
        if (closed && dayKey(cur) !== todayK) continue;
        ensureDay(dayKey(cur), cur).events.push(ev);
      }
      continue;
    }
    // Nach LOKALEM Datum gruppieren (sonst landen 00:00-Events über UTC
    // auf einem anderen Tag -> Tag erscheint doppelt).
    const d = new Date(ev.start);
    ensureDay(dayKey(d), d).events.push(ev);
  }
  // Vergangene Tage ausblenden (um Mitternacht fällt der ganze Tag weg).
  const todayKey = dayKey(new Date());
  const sortedKeys = [...groups.keys()].filter((k) => k >= todayKey).sort();

  if (sortedKeys.length === 0) {
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

// Singular/Plural je Kategorie für "+ N weitere …".
const CATEGORY_NOUN = {
  Theater: ["Theater", "Theater"],
  Kino: ["Film", "Filme"],
  Konzert: ["Konzert", "Konzerte"],
  Party: ["Party", "Partys"],
  Vortrag: ["Vortrag", "Vorträge"],
  Protest: ["Protest", "Proteste"],
  Workshop: ["Workshop", "Workshops"],
  Ausstellung: ["Ausstellung", "Ausstellungen"],
  Essen: ["Essen", "Essen"],
  Sonstiges: ["Eintrag", "Einträge"],
};

function shouldCollapse(cat) {
  if (!COLLAPSE_CATS[cat]) return false;
  if (state.query || state.onlyFav) return false;
  if (state.activeTags.has(cat)) return false;  // chip selected -> show them all
  return true;
}

// How many cards to show before "+ N weitere": two full rows for the current
// column count, mindestens 4 (1 Spalte->4, 2->4, 3->6, 4->8 ...). Eingeklappt
// wird erst, wenn dadurch mindestens 2 Events verborgen werden (kein "+1").
function gridColumns() {
  const w = (els.feed.clientWidth || window.innerWidth || 360) - 32;
  return Math.max(1, Math.floor((w + 16) / (280 + 16)));  // matcht CSS minmax+gap
}
function previewCount() {
  return Math.max(4, gridColumns() * 2);
}

// Append a category's cards into `container`. With `preview` set, only that
// many cards show; the rest hide behind a "+ N weitere …" toggle (built lazily
// on first open). Only collapses when it would hide at least 2 events -- a
// single extra card is just shown. `preview` falsy (0) => show all.
function appendCategoryCards(container, cat, list, day, preview) {
  const grid = document.createElement("div");
  grid.className = "cards";
  container.appendChild(grid);

  if (!preview || list.length <= preview + 1) {
    for (const ev of list) grid.appendChild(renderCard(ev, day));
    return;
  }

  const head = list.slice(0, preview);
  const rest = list.slice(preview);
  for (const ev of head) grid.appendChild(renderCard(ev, day));

  const n = CATEGORY_NOUN[cat];
  const noun = n ? " " + (rest.length === 1 ? n[0] : n[1]) : "";
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
function renderCollapsedCategory(cat, list, day, preview) {
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

  appendCategoryCards(section, cat, list, day, preview);
  return section;
}

function renderList(sortedKeys, groups) {
  const frag = document.createDocumentFragment();
  const preview = previewCount();
  const now = new Date();
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

    // Vorbei (heute, nach Zeit) bzw. geschlossen (Ausstellung nach Öffnungs-
    // zeiten) -> ausgegraut in eine zugeklappte Box ganz oben am Tag.
    let dayEvents = events;
    const past = events.filter((e) => isPastOrClosed(e, date, now));
    if (past.length) {
      const passed = new Set(past);
      dayEvents = events.filter((e) => !passed.has(e));
      group.appendChild(renderPastBox(past, date));
    }

    if (state.sortMode === "category") renderDayByCategory(dayEvents, group, date, preview);
    else if (state.sortMode === "genre") renderDayByGenre(dayEvents, group, date, preview);
    else renderDayByTime(dayEvents, group, date, preview);

    frag.appendChild(group);
  }

  els.feed.innerHTML = "";
  els.feed.appendChild(frag);

  setupScrollSpy(sortedKeys);
}

// Sort "Uhrzeit": cards in time order; Kino/Ausstellungen bundled per day.
function renderDayByTime(events, group, day, preview) {
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
    if (list && list.length) group.appendChild(renderCollapsedCategory(cat, list, day, preview));
  }
}

// Ausstellungen behalten die Reihenfolge der Quelle; alles andere nach Uhrzeit.
function orderForCat(cat, list) {
  return cat === "Ausstellung" ? list.slice() : list.slice().sort(byStart);
}

// Sort "Kategorie": one open (collapsible) box per category, cards by time.
function renderDayByCategory(events, group, day, preview) {
  const byCat = groupBy(events, (ev) => (ev.tags || [])[0] || "Sonstiges");
  for (const cat of orderedKeys(byCat.keys(), SORT_CATEGORY_ORDER)) {
    const list = orderForCat(cat, byCat.get(cat));
    const box = buildSortBox(cat, list.length);
    appendCategoryCards(box, cat, list, day, preview);
    group.appendChild(box);
  }
}

// Sort "Genre": one open box per genre, inside it a sub-box per category.
function renderDayByGenre(events, group, day, preview) {
  const byGenre = groupBy(events, (ev) => ev.genre || "Ohne Genre");
  for (const genre of orderedKeys(byGenre.keys(), GENRE_ORDER)) {
    const gEvents = byGenre.get(genre);
    const box = buildSortBox(genre, gEvents.length, genreClass(genre));
    const byCat = groupBy(gEvents, (ev) => (ev.tags || [])[0] || "Sonstiges");
    for (const cat of orderedKeys(byCat.keys(), SORT_CATEGORY_ORDER)) {
      const list = orderForCat(cat, byCat.get(cat));
      const sub = buildSortBox(cat, list.length, "sort-subbox");
      appendCategoryCards(sub, cat, list, day, preview);
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

// "Schon vorbei": zugeklappte Box (gleicher Stil wie die Sortier-Kästen) ganz
// oben am heutigen Tag; die Karten darin sind ausgegraut, lazy gebaut.
function renderPastBox(past, day) {
  const det = buildSortBox("Schon vorbei", past.length, "past-box");
  det.open = false;
  const grid = document.createElement("div");
  grid.className = "cards";
  det.appendChild(grid);
  let built = false;
  det.addEventListener("toggle", () => {
    if (det.open && !built) {
      built = true;
      for (const ev of past) {
        const c = renderCard(ev, day);
        c.classList.add("card--past");
        grid.appendChild(c);
      }
    }
  });
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
  resetSheet();
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
  resetSheet();
  for (const m of modalMaps) m.remove();
  modalMaps = [];
}

// Clear any drag transform left on the sheet (so the next open starts clean).
function resetSheet() {
  els.modal.style.transition = "";
  els.modal.style.transform = "";
  els.modalBackdrop.style.background = "";
}

// Bottom-sheet "wegschieben": when the detail view is scrolled to the very top
// and the user drags it further down, the sheet follows the finger; releasing
// after a long enough pull -- or a quick flick -- closes it. A short, gentle
// pull snaps back.
function setupSheetDrag() {
  const sheet = els.modal;
  let startY = 0, lastY = 0, lastT = 0, dy = 0, velocity = 0;
  let active = false, dragging = false;

  sheet.addEventListener("touchstart", (e) => {
    if (e.touches.length !== 1 || sheet.scrollTop > 0) { active = false; return; }
    active = true; dragging = false; dy = 0; velocity = 0;
    startY = lastY = e.touches[0].clientY;
    lastT = e.timeStamp;
    sheet.style.transition = "none";
  }, { passive: true });

  sheet.addEventListener("touchmove", (e) => {
    if (!active) return;
    const y = e.touches[0].clientY;
    dy = y - startY;
    if (dy > 0) {
      // Nach unten gezogen, während der Inhalt schon ganz oben ist -> Sheet
      // mitschieben statt scrollen. Sobald zwischendurch gescrollt wurde,
      // den Griff loslassen.
      if (sheet.scrollTop > 0) { active = false; resetSheet(); return; }
      dragging = true;
      e.preventDefault();
      sheet.style.transform = `translateY(${dy}px)`;
      const fade = Math.max(0, 1 - dy / (window.innerHeight * 0.8));
      els.modalBackdrop.style.background = `rgba(40, 26, 15, ${0.45 * fade})`;
    } else if (!dragging) {
      // Nach oben gewischt -> normales Scrollen erlauben.
      active = false;
    }
    velocity = (y - lastY) / ((e.timeStamp - lastT) || 1);
    lastY = y; lastT = e.timeStamp;
  }, { passive: false });

  const end = () => {
    if (!active) return;
    active = false;
    sheet.style.transition = "";  // CSS-Übergang fürs Zurückschnappen/Schließen
    const flick = velocity > 0.55;             // kräftiges Wegschieben
    const far = dy > sheet.offsetHeight * 0.28; // weit genug gezogen
    if (dragging && (far || flick)) {
      els.modalBackdrop.style.background = "transparent";
      sheet.style.transform = "translateY(100%)";
      setTimeout(() => { resetSheet(); closeModal(); }, 200);
    } else {
      resetSheet();
    }
    dragging = false;
  };
  sheet.addEventListener("touchend", end);
  sheet.addEventListener("touchcancel", end);
}

// ---------------- Favourites ----------------

function eventId(ev) {
  // Ausstellungen ohne Datum identifizieren -- so bleibt ein Favorit stabil,
  // auch wenn sich das Start-Datum von Lauf zu Lauf ändert.
  if (isExhibition(ev)) return (ev.source_url || "") + "|ausstellung|" + (ev.title || "");
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
  if (navigator.share) {
    try { await navigator.share({ url }); } catch { /* cancelled */ }
  } else {
    try { await navigator.clipboard.writeText(url); toast("Link kopiert"); }
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
    closeOverlay(els.eventBackdrop);
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
  headerOffset(); // Header-Höhe (und damit Sprungziel) aktuell halten
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
  const mapDate = new Date(state.mapDay + "T12:00:00");

  for (const ev of mapDayEvents) {
    const past = isPastOrClosed(ev, mapDate, now);
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
        jumpToDay(key);
      }
    });
    els.dayTabs.appendChild(tab);
  }
}

// Jump to a day's heading and park it just under the sticky header. We compute
// the target scroll position explicitly (absolute document position minus the
// measured header height) instead of relying on scrollIntoView + CSS
// scroll-margin, whose timing left the previous day partly visible.
function jumpToDay(key) {
  const target = document.getElementById(`day-${key}`);
  if (!target) return;
  setActiveTab(key);
  // Absolute Zielposition: Tagesüberschrift knapp unter den Sticky-Header.
  const wantTop = () => Math.max(0,
    target.getBoundingClientRect().top + window.scrollY - headerOffset());
  window.scrollTo({ top: wantTop(), behavior: "smooth" });

  // Nach der Smooth-Animation mehrfach nachjustieren: Bilder, die wegfallen,
  // oder spät ladende Schrift verschieben das Layout, sonst landet man im
  // Nachbartag (und müsste mehrfach klicken). Die Korrektur bricht ab, sobald
  // der/die Nutzer:in selbst scrollt.
  let cancelled = false;
  const cancel = () => { cancelled = true; };
  window.addEventListener("wheel", cancel, { passive: true, once: true });
  window.addEventListener("touchstart", cancel, { passive: true, once: true });

  let tries = 0;
  const cleanup = () => {
    window.removeEventListener("wheel", cancel);
    window.removeEventListener("touchstart", cancel);
  };
  const settle = () => {
    if (cancelled) { cleanup(); return; }
    const want = wantTop();
    if (Math.abs(window.scrollY - want) > 2) window.scrollTo({ top: want });
    if (++tries < 5) setTimeout(settle, 140);
    else cleanup();
  };
  setTimeout(settle, 380);
}

let dayIO = null;
let lastActiveKey = null;

// Both the click-to-jump target (CSS scroll-margin) and the scroll-spy line
// must use the SAME, REAL header height -- otherwise jumps land behind the
// sticky header and the wrong day gets highlighted. The header height varies
// (genre row wraps, categories expand, safe-area inset), so measure it live.
const HEADER_GAP = 8;
function headerOffset() {
  const header = document.querySelector(".site-header");
  const h = (header ? header.offsetHeight : 0) + HEADER_GAP;
  document.documentElement.style.setProperty("--header-h", h + "px");
  return h;
}

// Scroll-spy via IntersectionObserver: only recompute the active day when a day
// heading actually crosses the header line (not on every scroll frame).
function setupScrollSpy(sortedKeys) {
  if (dayIO) dayIO.disconnect();
  const sections = sortedKeys
    .map((k) => document.getElementById(`day-${k}`))
    .filter(Boolean);
  lastActiveKey = null;
  if (!sections.length) return;

  const offset = headerOffset;
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
    if (active) {
      // Aktiven Reiter horizontal in der Leiste zentrieren -- nur die Leiste
      // scrollen (nicht scrollIntoView, das auch das Fenster vertikal anstößt
      // und den Tagessprung stört).
      const nav = els.dayTabs;
      const left = tab.offsetLeft - (nav.clientWidth - tab.clientWidth) / 2;
      nav.scrollTo({ left: Math.max(0, left), behavior: "smooth" });
    }
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
