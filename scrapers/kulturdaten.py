"""kulturdaten.berlin -- probing scraper (public read, no token).

Reading is open on this API (only writing needs an account). This scraper
tries a few candidate base URLs and endpoints and records what comes back,
so we can see the real structure before building the full integration.
"""

from __future__ import annotations

import json
import pathlib
from typing import Iterable

import requests

from .base import BaseScraper, Event

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

# kulturdaten-Kategorie -> unser Tag.
CATEGORY_MAP = {
    "Music": "Konzert", "Stages": "Theater", "Dance": "Party",
    "Exhibitions": "Ausstellung", "Festivals": "Party",
    "Lectures": "Vortrag", "Conferences": "Vortrag", "InformationEvents": "Vortrag",
    "Education": "Workshop", "Politics": "Protest",
    "WeeklyMarkets": "Sonstiges", "Walks": "Sonstiges", "Children": "Sonstiges",
    "Recreation": "Sonstiges", "Women": "Sonstiges", "Police": "Sonstiges",
    "Health": "Sonstiges", "ChristmasTime": "Sonstiges",
}

HEADERS = {
    "User-Agent": "EventkalenderBot/1.0 (+https://github.com/flipssssss/eventkalender)",
    "Accept": "application/json",
}

BASES = [
    "https://api-v2.kulturdaten.berlin",
]
PATHS = [
    "/api/docs-json",
    "/api-json",
    "/api/discover/attractions",
    "/api/discover/events",
    "/api/discover/locations",
    "/discover/attractions",
    "/api/attractions",
    "/api/events",
    "/api/locations",
]


class KulturdatenScraper(BaseScraper):
    name = "kulturdaten.berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    BASE = "https://api-v2.kulturdaten.berlin"

    def fetch_events(self) -> Iterable[Event]:
        return self._count_categories()

    def _count_categories(self) -> Iterable[Event]:
        import collections as _c
        import datetime as _dt

        session = requests.Session()
        session.headers.update(HEADERS)
        report: list[str] = []

        def get_data(path):
            """Robust: never raise -- return {} on any error."""
            try:
                r = session.get(self.BASE + path, timeout=30)
                return r.json().get("data", {}) if r.status_code == 200 else {}
            except Exception:  # noqa: BLE001
                return {}

        try:
            today = _dt.date.today()
            end = today + _dt.timedelta(days=14)

            # 1) Events der nächsten 14 Tage sammeln.
            events, page = [], 1
            while page <= 30:
                d = get_data(f"/api/events?startDate={today}&endDate={end}&pageSize=200&page={page}")
                batch = d.get("events") or []
                events.extend(batch)
                if not batch or page * 200 >= (d.get("totalCount") or 0):
                    break
                page += 1

            # 2) Attraktion -> Kategorie-Map (alle Attraktionen durchblättern).
            cat_of, apage, failed = {}, 1, 0
            while apage <= 130:
                d = get_data(f"/api/attractions?pageSize=200&page={apage}")
                ats = d.get("attractions") or []
                if not ats:
                    failed += 1
                    if failed > 3:
                        break
                    apage += 1
                    continue
                for a in ats:
                    tags = [t.replace("attraction.category.", "") for t in a.get("tags", [])]
                    cat_of[a.get("identifier")] = tags[0] if tags else "—"
                if apage * 200 >= (d.get("totalCount") or 0):
                    break
                apage += 1

            report.append(f"Events 14 Tage: {len(events)} | Attraktionen geladen: {len(cat_of)}")

            # 3) Events pro Kategorie + Herkunft zählen.
            by_cat, by_origin, free = _c.Counter(), _c.Counter(), 0
            for e in events:
                aid = e["attractions"][0]["referenceId"] if e.get("attractions") else None
                by_cat[cat_of.get(aid, "?ohne Kategorie")] += 1
                by_origin[(e.get("metadata") or {}).get("origin", "?")] += 1
                if (e.get("admission") or {}).get("ticketType") == "ticketType.freeOfCharge":
                    free += 1

            report.append(f"Kostenlos: {free} von {len(events)}\n")
            report.append("Events pro Kategorie (14 Tage):")
            for cat, n in by_cat.most_common():
                report.append(f"  {n:5d}  {cat:20s} -> {CATEGORY_MAP.get(cat, 'Sonstiges')}")
            report.append("\nEvents pro Herkunft:")
            for o, n in by_origin.most_common():
                report.append(f"  {n:5d}  {o}")
        except Exception as exc:  # noqa: BLE001
            report.append(f"FEHLER in der Zählung: {exc}")

        if self.write_debug:
            try:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                (DEBUG_DIR / "kulturdaten.txt").write_text("\n".join(report) or "leer",
                                                           encoding="utf-8")
            except OSError:
                pass
        return []
