"""Turn venue names/addresses into coordinates + a Berlin borough.

The map view and the Bezirk filter need every event to carry a location
name, a postal address, geo coordinates and the Berlin borough it sits in.
Many sources already provide a venue name; this module fills in the rest by
geocoding via OpenStreetMap/Nominatim (free, no API key).

To stay fast and polite we cache every lookup in ``docs/data/_geocache.json``
(committed to the repo), so each address is only ever requested once.

Network is only available inside the GitHub Action -- locally the cache is
simply reused, and unknown addresses are left ungeocoded.
"""

from __future__ import annotations

import json
import pathlib
import re
import time

import requests

ROOT = pathlib.Path(__file__).parent.parent
CACHE_FILE = ROOT / "docs" / "data" / "_geocache.json"

NOMINATIM = "https://nominatim.openstreetmap.org/search"
USER_AGENT = (
    "EventkalenderBot/1.0 (+https://github.com/flipssssss/eventkalender)"
)
# Nominatim usage policy: at most one request per second.
RATE_LIMIT_SECONDS = 1.1

# The twelve official Berlin boroughs.
BEZIRKE = [
    "Mitte", "Friedrichshain-Kreuzberg", "Pankow",
    "Charlottenburg-Wilmersdorf", "Spandau", "Steglitz-Zehlendorf",
    "Tempelhof-Schöneberg", "Neukölln", "Treptow-Köpenick",
    "Marzahn-Hellersdorf", "Lichtenberg", "Reinickendorf",
]

# Berlin "Ortsteile" -> their borough, so a geocoded suburb maps onto one of
# the twelve official Bezirke.
ORTSTEIL_TO_BEZIRK = {
    # Mitte
    "mitte": "Mitte", "moabit": "Mitte", "hansaviertel": "Mitte",
    "tiergarten": "Mitte", "wedding": "Mitte", "gesundbrunnen": "Mitte",
    # Friedrichshain-Kreuzberg
    "friedrichshain": "Friedrichshain-Kreuzberg",
    "kreuzberg": "Friedrichshain-Kreuzberg",
    # Pankow
    "prenzlauer berg": "Pankow", "weißensee": "Pankow", "weissensee": "Pankow",
    "pankow": "Pankow", "blankenburg": "Pankow", "heinersdorf": "Pankow",
    "karow": "Pankow", "buch": "Pankow", "französisch buchholz": "Pankow",
    "niederschönhausen": "Pankow", "rosenthal": "Pankow",
    "wilhelmsruh": "Pankow", "stadtrandsiedlung malchow": "Pankow",
    "blankenfelde": "Pankow",
    # Charlottenburg-Wilmersdorf
    "charlottenburg": "Charlottenburg-Wilmersdorf",
    "wilmersdorf": "Charlottenburg-Wilmersdorf",
    "schmargendorf": "Charlottenburg-Wilmersdorf",
    "grunewald": "Charlottenburg-Wilmersdorf",
    "westend": "Charlottenburg-Wilmersdorf",
    "charlottenburg-nord": "Charlottenburg-Wilmersdorf",
    "halensee": "Charlottenburg-Wilmersdorf",
    # Spandau
    "spandau": "Spandau", "haselhorst": "Spandau", "siemensstadt": "Spandau",
    "staaken": "Spandau", "gatow": "Spandau", "kladow": "Spandau",
    "hakenfelde": "Spandau", "falkenhagener feld": "Spandau",
    "wilhelmstadt": "Spandau",
    # Steglitz-Zehlendorf
    "steglitz": "Steglitz-Zehlendorf", "lichterfelde": "Steglitz-Zehlendorf",
    "lankwitz": "Steglitz-Zehlendorf", "zehlendorf": "Steglitz-Zehlendorf",
    "dahlem": "Steglitz-Zehlendorf", "nikolassee": "Steglitz-Zehlendorf",
    "wannsee": "Steglitz-Zehlendorf",
    # Tempelhof-Schöneberg
    "schöneberg": "Tempelhof-Schöneberg", "friedenau": "Tempelhof-Schöneberg",
    "tempelhof": "Tempelhof-Schöneberg", "mariendorf": "Tempelhof-Schöneberg",
    "marienfelde": "Tempelhof-Schöneberg", "lichtenrade": "Tempelhof-Schöneberg",
    # Neukölln
    "neukölln": "Neukölln", "neukolln": "Neukölln", "britz": "Neukölln",
    "buckow": "Neukölln", "rudow": "Neukölln", "gropiusstadt": "Neukölln",
    # Treptow-Köpenick
    "alt-treptow": "Treptow-Köpenick", "treptow": "Treptow-Köpenick",
    "plänterwald": "Treptow-Köpenick", "baumschulenweg": "Treptow-Köpenick",
    "johannisthal": "Treptow-Köpenick", "niederschöneweide": "Treptow-Köpenick",
    "oberschöneweide": "Treptow-Köpenick", "adlershof": "Treptow-Köpenick",
    "bohnsdorf": "Treptow-Köpenick", "altglienicke": "Treptow-Köpenick",
    "köpenick": "Treptow-Köpenick", "friedrichshagen": "Treptow-Köpenick",
    "rahnsdorf": "Treptow-Köpenick", "grünau": "Treptow-Köpenick",
    "müggelheim": "Treptow-Köpenick", "schmöckwitz": "Treptow-Köpenick",
    # Marzahn-Hellersdorf
    "marzahn": "Marzahn-Hellersdorf", "biesdorf": "Marzahn-Hellersdorf",
    "kaulsdorf": "Marzahn-Hellersdorf", "mahlsdorf": "Marzahn-Hellersdorf",
    "hellersdorf": "Marzahn-Hellersdorf",
    # Lichtenberg
    "lichtenberg": "Lichtenberg", "friedrichsfelde": "Lichtenberg",
    "karlshorst": "Lichtenberg", "rummelsburg": "Lichtenberg",
    "fennpfuhl": "Lichtenberg", "alt-hohenschönhausen": "Lichtenberg",
    "neu-hohenschönhausen": "Lichtenberg", "hohenschönhausen": "Lichtenberg",
    "falkenberg": "Lichtenberg", "malchow": "Lichtenberg",
    "wartenberg": "Lichtenberg",
    # Reinickendorf
    "reinickendorf": "Reinickendorf", "tegel": "Reinickendorf",
    "konradshöhe": "Reinickendorf", "heiligensee": "Reinickendorf",
    "frohnau": "Reinickendorf", "hermsdorf": "Reinickendorf",
    "waidmannslust": "Reinickendorf", "lübars": "Reinickendorf",
    "wittenau": "Reinickendorf", "märkisches viertel": "Reinickendorf",
    "borsigwalde": "Reinickendorf",
}

# Known single-venue sources -> exact address, coords and borough. These are
# our core sources where the feed's "location" can be vague or missing.
VENUE_OVERRIDES = {
    "Donau115": {
        "location": "Donau115",
        "address": "Donaustraße 115, 12043 Berlin",
        "lat": 52.47567, "lng": 13.43597, "bezirk": "Neukölln",
    },
    "Silverfuture": {
        "location": "SilverFuture",
        "address": "Weserstraße 206, 12047 Berlin",
        "lat": 52.49293, "lng": 13.42897, "bezirk": "Neukölln",
    },
}

# Single-venue sources whose feed "location" is unusable (e.g. a URL): supply
# the known address and let the geocoder resolve the exact coordinates/Bezirk.
SOURCE_ADDRESS = {
    "Karada House": "Perleberger Straße 59, 10559 Berlin",
}


_cache: dict | None = None
_last_request = 0.0


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache = {}
    return _cache


def save_cache() -> None:
    if _cache is None:
        return
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(_cache, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )


def _bezirk_from_address(addr: dict) -> str | None:
    """Map a Nominatim address dict onto one of the twelve Bezirke."""
    # Direct borough fields first.
    for key in ("borough", "city_district", "district"):
        val = (addr.get(key) or "").strip()
        for b in BEZIRKE:
            if val.lower() == b.lower():
                return b
        if val.lower() in ORTSTEIL_TO_BEZIRK:
            return ORTSTEIL_TO_BEZIRK[val.lower()]
    # Then the Ortsteil-like fields.
    for key in ("suburb", "quarter", "neighbourhood", "city_block", "town"):
        val = (addr.get(key) or "").strip().lower()
        if val in ORTSTEIL_TO_BEZIRK:
            return ORTSTEIL_TO_BEZIRK[val]
        for b in BEZIRKE:
            if val == b.lower():
                return b
    # Nominatim kennt den Ortsteil nicht immer -- die PLZ reicht dann aus.
    return PLZ_TO_BEZIRK.get((addr.get("postcode") or "").strip()[:5])


def _format_address(addr: dict) -> str | None:
    road = addr.get("road") or addr.get("pedestrian") or addr.get("square")
    house = addr.get("house_number")
    plz = addr.get("postcode")
    ort = (addr.get("suburb") or addr.get("city_district")
           or addr.get("borough") or "Berlin")
    parts = []
    if road:
        parts.append(road + (" " + house if house else ""))
    tail = " ".join(filter(None, [plz, ort]))
    if tail:
        parts.append(tail)
    return ", ".join(parts) or None


_PLZ_RE = re.compile(r"\b(\d{5})\b")
_STREET_RE = re.compile(
    r"([A-ZÄÖÜ][\wäöüß.\-]*\s*"
    r"(?:stra(?:ß|ss)e|str\.?|allee|damm|platz|weg|ufer|ring|chaussee|"
    r"gasse|tor|pfad|steig|hof)\.?\s+\d{1,4}(?:\s*[-/]\s*\d{1,4})?"
    r"(?:\s?[a-zA-Z](?![A-Za-zäöüß]))?)",
    re.IGNORECASE,
)


def _is_generic_berlin(text: str) -> bool:
    """True, wenn der Ort praktisch nur "Berlin" ist (kein konkreter Ort)."""
    t = re.sub(r"\b(deutschland|germany|de)\b", "", text or "", flags=re.IGNORECASE)
    t = re.sub(r"[\s,.;:\-]+", " ", t).strip().lower()
    return t in ("", "berlin")


def _address_from_description(desc: str | None) -> str | None:
    """Versucht, eine echte Adresse (Straße + ggf. PLZ) aus dem Beschreibungstext
    zu ziehen -- für Events, deren Ortsfeld nur "Berlin" ist."""
    if not desc:
        return None
    street = _STREET_RE.search(desc)
    plz = _PLZ_RE.search(desc)
    if street and plz:
        return f"{street.group(1).strip()}, {plz.group(1)} Berlin"
    if street:
        return f"{street.group(1).strip()}, Berlin"
    if plz:
        return f"{plz.group(1)} Berlin"
    return None


def clean_query(location: str) -> str:
    """Turn a noisy ``location`` string into a Nominatim-friendly address.

    Source feeds often give "<Venue> <Street> <No> <PLZ> Berlin Deutschland"
    without commas, which the geocoder struggles with. We extract the
    street+number and the postal code and rebuild a tidy "Street No, PLZ
    Berlin" query (falling back to just "PLZ Berlin", then the raw text).
    """
    text = re.sub(r"\b(Deutschland|Germany)\b", "", location, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text.replace(",", " ")).strip()
    plz = _PLZ_RE.search(text)
    street = _STREET_RE.search(text)
    if street and plz:
        return f"{street.group(1).strip()}, {plz.group(1)} Berlin"
    if plz:
        return f"{plz.group(1)} Berlin"
    if street:
        return f"{street.group(1).strip()}, Berlin"
    if "berlin" not in text.lower():
        text = f"{text}, Berlin"
    return text


# --------------------------------------------------------------------------
# Postleitzahl -> Bezirk.
#
# Warum: rund ein Sechstel der Events hatte keinen Bezirk und fiel damit aus
# Bezirksfilter UND Karte heraus -- obwohl in der Adresse eine Berliner PLZ
# stand. Die Zuordnung ist rein rechnerisch, braucht also weder Netz noch
# Nominatim-Treffer und greift auch dann, wenn das Geocoding scheitert.
#
# Ein paar PLZ liegen auf einer Bezirksgrenze (z. B. 10119 Mitte/Prenzlauer
# Berg, 10785 Tiergarten/Schöneberg, 14195 Dahlem/Wilmersdorf). Dort steht der
# flächenmäßig dominierende Bezirk -- besser als "Unbekannt", aber im
# Einzelfall eine Näherung.
# --------------------------------------------------------------------------
PLZ_TO_BEZIRK = {}


def _fill_plz(bezirk: str, *codes: str) -> None:
    for code in codes:
        PLZ_TO_BEZIRK[code] = bezirk


_fill_plz("Mitte",
          "10115", "10117", "10119", "10178", "10179", "10551", "10553",
          "10555", "10557", "10559", "10785", "10787", "13347", "13349",
          "13351", "13353", "13355", "13357", "13359")
_fill_plz("Friedrichshain-Kreuzberg",
          "10243", "10245", "10247", "10249", "10961", "10963", "10965",
          "10967", "10969", "10997", "10999")
_fill_plz("Pankow",
          "10405", "10407", "10409", "10435", "10437", "10439", "13086",
          "13088", "13089", "13125", "13127", "13129", "13156", "13158",
          "13159", "13187", "13189")
_fill_plz("Charlottenburg-Wilmersdorf",
          "10585", "10587", "10589", "10623", "10625", "10627", "10629",
          "10707", "10709", "10711", "10713", "10715", "10717", "10719",
          "10789", "14050", "14052", "14053", "14055", "14057", "14059",
          "14193", "14195")
_fill_plz("Spandau",
          "13581", "13583", "13585", "13587", "13589", "13591", "13593",
          "13595", "13597", "13599")
_fill_plz("Steglitz-Zehlendorf",
          "12163", "12165", "12167", "12169", "12203", "12205", "12207",
          "12209", "12247", "14109", "14129", "14163", "14165", "14167",
          "14169", "14199")
_fill_plz("Tempelhof-Schöneberg",
          "10777", "10779", "10781", "10783", "10823", "10825", "10827",
          "10829", "12099", "12101", "12103", "12105", "12107", "12109",
          "12157", "12159", "12161", "12249", "12277", "12279", "12305",
          "12307", "12309", "14197")
_fill_plz("Neukölln",
          "12043", "12045", "12047", "12049", "12051", "12053", "12055",
          "12057", "12059", "12347", "12349", "12351", "12353", "12355",
          "12357", "12359")
_fill_plz("Treptow-Köpenick",
          "12435", "12437", "12439", "12459", "12487", "12489", "12524",
          "12526", "12527", "12555", "12557", "12559", "12587", "12589")
_fill_plz("Marzahn-Hellersdorf",
          "12619", "12621", "12623", "12627", "12629", "12679", "12681",
          "12683", "12685", "12687", "12689")
_fill_plz("Lichtenberg",
          "10315", "10317", "10318", "10319", "10365", "10367", "10369",
          "13051", "13053", "13055", "13057", "13059")
_fill_plz("Reinickendorf",
          "13403", "13405", "13407", "13409", "13435", "13437", "13439",
          "13465", "13467", "13469", "13503", "13505", "13507", "13509")


def bezirk_from_plz(text: str | None) -> str | None:
    """Borough for the first Berlin postal code found in ``text``."""
    if not text:
        return None
    for match in _PLZ_RE.finditer(str(text)):
        hit = PLZ_TO_BEZIRK.get(match.group(1))
        if hit:
            return hit
    return None


# Wiederkehrende Orte ohne brauchbare Adresse in der Quelle. Kuratiert, damit
# sie nicht dauerhaft im Bezirksfilter fehlen (Namen kleingeschrieben).
VENUE_BEZIRK = {
    "säule/berghain": "Friedrichshain-Kreuzberg",
    "säule": "Friedrichshain-Kreuzberg",
    "berghain": "Friedrichshain-Kreuzberg",
    "panorama bar": "Friedrichshain-Kreuzberg",
    "ask a punk": "Friedrichshain-Kreuzberg",
    "trixxxter": "Friedrichshain-Kreuzberg",
    "martha": "Friedrichshain-Kreuzberg",
    "bethaniendamm": "Friedrichshain-Kreuzberg",
    "xxl – berlin, pornokino & sexshop": "Tempelhof-Schöneberg",
    "xxl berlin": "Tempelhof-Schöneberg",
    "busche club": "Friedrichshain-Kreuzberg",
    "ogh": "Friedrichshain-Kreuzberg",
    "nollendorfplatz": "Tempelhof-Schöneberg",
    "thomashöhe": "Neukölln",
    "capoeira akademie berlin": "Neukölln",
    "plänterwald": "Treptow-Köpenick",
    "willy brand haus": "Friedrichshain-Kreuzberg",
    "willy-brandt-haus": "Friedrichshain-Kreuzberg",
    "reichstag": "Mitte",
}


def bezirk_from_venue(*texts: str | None) -> str | None:
    """Borough for a known venue name, matched as a substring."""
    for text in texts:
        if not text:
            continue
        low = str(text).lower()
        for needle, bezirk in VENUE_BEZIRK.items():
            if needle in low:
                return bezirk
    return None


def _nominatim(query: str) -> dict | None:
    global _last_request
    wait = RATE_LIMIT_SECONDS - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = requests.get(
            NOMINATIM,
            params={
                "q": query,
                "format": "jsonv2",
                "addressdetails": 1,
                "limit": 1,
                "countrycodes": "de",
                # Bias (not restrict) results towards Greater Berlin.
                "viewbox": "13.05,52.70,13.80,52.30",
            },
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        _last_request = time.time()
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError):
        return None
    if not data:
        return None
    hit = data[0]
    addr = hit.get("address") or {}
    return {
        "lat": float(hit["lat"]),
        "lng": float(hit["lon"]),
        "address": _format_address(addr),
        "bezirk": _bezirk_from_address(addr),
    }


def geocode(query: str, *, allow_network: bool = True) -> dict | None:
    """Return ``{lat, lng, address, bezirk}`` for a venue/address string."""
    query = (query or "").strip()
    if not query:
        return None
    cache = _load_cache()
    if query in cache:
        return cache[query]
    if not allow_network:
        return None
    result = _nominatim(query)
    # Cache misses too (as None) so we don't retry hopeless queries every run.
    cache[query] = result
    return result


def locate_event(event, *, allow_network: bool = True) -> None:
    """Fill ``event.address/lat/lng/bezirk`` in place, best effort.

    Geocoding runs first; whatever borough it could not determine is then
    filled from the postal code, the cinema screenings or the curated venue
    table, so an event still lands in the Bezirk filter and on the map.
    """
    _locate_event_core(event, allow_network=allow_network)
    _fill_missing_bezirk(event)


def _bezirke_from_showings(event) -> list[str]:
    """Boroughs of all cinemas a film runs in (deduplicated, order kept)."""
    out: list[str] = []
    for showing in getattr(event, "showings", None) or []:
        hit = (bezirk_from_plz(showing.get("address"))
               or bezirk_from_venue(showing.get("cinema")))
        if hit and hit not in out:
            out.append(hit)
    return out


def _fill_missing_bezirk(event) -> None:
    """Last-resort borough assignment, without any network call."""
    # Filme laufen oft in mehreren Kinos -> alle Bezirke merken, damit ein Film
    # im Neukoelln-Filter auftaucht, wenn er (auch) in Neukoelln laeuft.
    showing_bezirke = _bezirke_from_showings(event)
    if showing_bezirke:
        event.bezirke = showing_bezirke
        if not event.bezirk:
            event.bezirk = showing_bezirke[0]
        return
    if event.bezirk:
        return
    event.bezirk = (bezirk_from_plz(event.address)
                    or bezirk_from_plz(event.location)
                    or bezirk_from_plz(getattr(event, "description", None))
                    or bezirk_from_venue(event.location, event.address))


def _locate_event_core(event, *, allow_network: bool = True) -> None:
    override = VENUE_OVERRIDES.get(event.source_name)
    if override:
        event.address = event.address or override["address"]
        event.lat = override["lat"]
        event.lng = override["lng"]
        event.bezirk = override["bezirk"]
        return

    fixed = SOURCE_ADDRESS.get(event.source_name)
    if fixed:
        # Single venue: a clean, consistent name + the known address.
        event.address = fixed
        event.location = event.source_name

    if not event.location and not event.address:
        return
    raw = (fixed or event.address or event.location).strip()
    # "2 Kinos" etc. is a summary, not a place -> don't geocode it.
    if not event.address and re.fullmatch(r"\d+ Kinos", raw):
        return
    # Skip obvious non-addresses (e.g. a stray URL in the location field).
    if raw.lower().startswith("http"):
        return

    # Ort ist nur "Berlin": echte Adresse aus der Beschreibung holen -- sonst
    # lieber gar kein Ort (sonst landet alles im Stadtzentrum).
    if not fixed and _is_generic_berlin(raw):
        addr = _address_from_description(getattr(event, "description", None))
        if not addr:
            event.location = None
            event.address = None
            event.lat = event.lng = None
            event.bezirk = None
            return
        raw = addr
        event.location = None      # nichtssagendes "Berlin"-Label verwerfen
        event.address = addr

    # Try the full string first (works well for clean addresses), then the
    # extracted "Street No, PLZ Berlin" as a fallback for noisy strings.
    candidates = [raw if "berlin" in raw.lower() else f"{raw}, Berlin"]
    cleaned = clean_query(raw)
    if cleaned not in candidates:
        candidates.append(cleaned)

    for query in candidates:
        hit = geocode(query, allow_network=allow_network)
        if hit and hit.get("lat") is not None:
            event.lat = hit.get("lat")
            event.lng = hit.get("lng")
            event.bezirk = hit.get("bezirk")
            if hit.get("address"):
                event.address = hit["address"]
            return
