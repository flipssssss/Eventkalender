"""Flohmärkte Berlin (berlin.de/special/shopping/flohmaerkte).

Ort, Adresse und Koordinaten kommen aus dem strukturierten ``rubric.geojson``-
Feed; die Termine aus den Teasern der Bezirks-Übersicht (Feld ``teaser__meta``,
z. B. "28. Juni 2026" oder "2. bis 4. Oktober 2026"). Wöchentlich wiederkehrende
Märkte (Teaser ohne Datum) werden hier (noch) übersprungen.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

BASE = "https://www.berlin.de"
PAGE = "https://www.berlin.de/special/shopping/flohmaerkte/bezirk/"
GEOJSON = "https://www.berlin.de/special/shopping/flohmaerkte/rubric.geojson"

MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
}


def _dates(meta: str) -> list[_dt.datetime]:
    """Termine aus dem Teaser-Datum: '20. und 21. Juni 2026', '27. Juni 2026',
    '2. bis 4. Oktober 2026'. Gibt eine Liste von Datumswerten zurück."""
    m = re.search(r"([A-Za-zäöüÄÖÜ]+)\s+(\d{4})", meta or "")
    if not m:
        return []
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        return []
    year = int(m.group(2))
    head = meta[:m.start()]
    days = [int(d) for d in re.findall(r"\d{1,2}", head)]
    if not days:
        return []
    if "bis" in head.lower() and len(days) >= 2:
        days = list(range(days[0], days[-1] + 1))
    out = []
    for d in days:
        try:
            out.append(_dt.datetime(year, mon, d))
        except ValueError:
            pass
    return out


def _clean_addr(addr: str | None) -> str | None:
    if not addr:
        return None
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    street = parts[0] if parts else ""
    plz = next((p for p in parts if re.fullmatch(r"\d{5}", p)), "")
    tail = (plz + " Berlin").strip() if plz else "Berlin"
    return ", ".join(x for x in [street, tail] if x) or addr


class FlohmarktScraper(BaseScraper):
    name = "Flohmärkte Berlin"

    def fetch_events(self) -> Iterable[Event]:
        # Ort/Koordinaten/Adresse je Markt aus dem GeoJSON.
        geo: dict[str, dict] = {}
        try:
            data = json.loads(self.get(GEOJSON).text)
            for f in data.get("features", []):
                p = f.get("properties") or {}
                url = p.get("url")
                if not url:
                    continue
                c = (f.get("geometry") or {}).get("coordinates") or [None, None]
                geo[url] = {
                    "address": p.get("address"),
                    "description": p.get("description"),
                    "lat": c[1], "lng": c[0],
                }
        except Exception:  # noqa: BLE001
            pass

        try:
            soup = BeautifulSoup(self.get(PAGE).text, "html.parser")
        except Exception:  # noqa: BLE001
            return []

        events: list[Event] = []
        seen: set[str] = set()
        for art in soup.select("article.modul-teaser"):
            a = art.select_one("h3.title a, h3 a, .title a")
            if not a:
                continue
            title = a.get_text(" ", strip=True)
            url = urljoin(BASE, a.get("href", ""))
            meta_el = art.select_one(".teaser__meta, .text--meta")
            dates = _dates(meta_el.get_text(" ", strip=True) if meta_el else "")
            if not dates:
                continue  # wiederkehrend/unbekannt -> (vorerst) überspringen
            g = geo.get(url, {})
            desc = (g.get("description") or "").strip() or None
            for d in dates:
                key = url + "|" + d.isoformat()
                if key in seen:
                    continue
                seen.add(key)
                events.append(Event(
                    title=title[:140],
                    start=d,
                    source_url=url,
                    source_name=self.name,
                    location=None,
                    address=_clean_addr(g.get("address")),
                    description=desc,
                    lat=g.get("lat"),
                    lng=g.get("lng"),
                    tags=["Markt"],
                    time_known=False,
                ))
        return events
