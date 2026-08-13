"""FunFacts (funfacts.de) -- Comedy/Talk-Shows, nur Berliner Termine.

The "tickets-kaufen" page is a Wix Events list (no JSON-LD), but the events
are server-rendered with stable ``data-hook`` attributes: ``date`` holds the
full German date+time ("18. Juni 2026, 19:00"), ``location`` the full address.
FunFacts tours nationwide, so only Berlin events are kept. All kept events are
category Vortrag; genre Kultur is set in scrapers/genres.py.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event, GERMAN_MONTHS

URL = "https://www.funfacts.de/tickets-kaufen"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

MONTHS = GERMAN_MONTHS
DATE_RE = re.compile(
    r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\s*(\d{4})(?:[,\s]+(\d{1,2}):(\d{2}))?")

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


class FunFactsScraper(BaseScraper):
    name = "FunFacts"

    def __init__(self, city: str = "Berlin", write_debug: bool = True):
        self.city = city
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(URL, headers=BROWSER).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()
        other_city = 0
        titles = soup.select('[data-hook="ev-list-item-title"]')
        for title_el in titles:
            container = self._container(title_el)
            if container is None:
                continue
            ev, loc = self._build(title_el, container)
            if ev is None:
                continue
            if self.city and self.city.lower() not in (loc or "").lower():
                other_city += 1
                continue
            key = ev.title.lower() + "|" + ev.start.isoformat()
            if key in seen:
                continue
            seen.add(key)
            events.append(ev)
        self._dump(f"Titel: {len(titles)} | {self.city}: {len(events)} | "
                   f"andere Städte: {other_city}\n" +
                   "\n".join(f"  {e.start} | {e.location} | {e.title}"
                             for e in events[:30]))
        return events

    @staticmethod
    def _container(title_el):
        """Smallest ancestor of the title that also holds the date hook."""
        node = title_el
        for _ in range(8):
            node = node.parent
            if node is None:
                return None
            if node.select_one('[data-hook="date"]'):
                return node
        return None

    def _build(self, title_el, container) -> tuple[Event | None, str | None]:
        title = title_el.get_text(" ", strip=True)
        date_el = container.select_one('[data-hook="date"]')
        if not title or not date_el:
            return None, None
        start = self._parse_date(date_el.get_text(" ", strip=True))
        if not start:
            return None, None
        loc_el = container.select_one('[data-hook="location"]')
        location = loc_el.get_text(" ", strip=True) if loc_el else None
        desc_el = container.select_one('[data-hook="ev-list-item-description"]')
        rsvp = container.select_one('[data-hook="ev-rsvp-button"]')
        url = (rsvp.get("href") if rsvp and rsvp.get("href") else URL)
        return Event(
            title=re.sub(r"\s*\|\s*[A-ZÄÖÜ]+\s*$", "", title)[:160],  # drop "| BERLIN"
            start=start,
            source_url=url,
            source_name=self.name,
            location=self._venue(location),
            address=location,
            description=(desc_el.get_text(" ", strip=True)[:500] if desc_el else None),
            tags=["Vortrag"],
        ), location

    @staticmethod
    def _venue(location: str | None) -> str:
        # "Mehringhof Theater, Gneisenaustr. 2a, 10961 Berlin, ..." -> first part.
        if not location:
            return "Berlin"
        return location.split(",")[0].strip() or "Berlin"

    @staticmethod
    def _parse_date(text: str) -> _dt.datetime | None:
        m = DATE_RE.search(text or "")
        if not m:
            return None
        day, mon_name, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        month = MONTHS.get(mon_name)
        if not month:
            return None
        hour = int(m.group(4)) if m.group(4) else 0
        minute = int(m.group(5)) if m.group(5) else 0
        try:
            return _dt.datetime(year, month, day, hour, minute)
        except ValueError:
            return None

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "funfacts.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
