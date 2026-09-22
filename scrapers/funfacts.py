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
# "18. Juni 2026, 19:00" und -- seit Wix die Liste umgestellt hat --
# "Di., 22. Sept." OHNE Jahr. Die Jahreszahl ist deshalb optional.
DATE_RE = re.compile(
    r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\.?(?:\s*(\d{4}))?"
    r"(?:[,\s]+(\d{1,2})[:.](\d{2}))?")
# "18.06.2026 19:00" / "18.6.26" -- rein numerisch, als zweite Chance.
NUM_DATE_RE = re.compile(
    r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b(?:[,\s]+(\d{1,2})[:.](\d{2}))?")
# Datums-Hooks, die Wix ueber die Jahre benutzt hat. Der erste Treffer gewinnt.
DATE_HOOKS = (
    '[data-hook="ev-date"]',              # aktuell ausgeliefert
    '[data-hook="ev-full-date-location"]',
    '[data-hook="date"]',
    '[data-hook="ev-list-item-date"]',
    '[data-hook="event-date"]',
    '[data-hook="events-list-item-date"]',
    "time[datetime]",
)
# Wix hat den Orts-Hook ebenfalls umbenannt.
LOCATION_HOOKS = (
    '[data-hook="ev-list-item-location"]',
    '[data-hook="location"]',
    '[data-hook="ev-full-date-location"]',
)


def _infer_year(month: int, day: int) -> int:
    """Year for a date given without one: the next occurrence, not the past."""
    today = _dt.date.today()
    try:
        candidate = _dt.date(today.year, month, day)
    except ValueError:
        return today.year
    return today.year + 1 if (today - candidate).days > 60 else today.year

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
        report = [f"Titel: {len(titles)} | {self.city}: {len(events)} | "
                  f"andere Städte: {other_city}"]
        report += [f"  {e.start} | {e.location} | {e.title}" for e in events[:30]]
        if titles and not events:
            # Nichts erkannt -> Struktur des ersten Treffers mitschreiben.
            first = titles[0]
            report.append("\nKEINE EVENTS ERKANNT -- Struktur des 1. Titels:")
            report.append(f"  Titel-Text: {first.get_text(' ', strip=True)[:120]!r}")
            found = [h for h in DATE_HOOKS if soup.select_one(h)]
            report.append(f"  Vorhandene Datums-Hooks auf der Seite: {found or 'KEINE'}")
            hooks = sorted({el["data-hook"] for el in soup.select("[data-hook]")})
            report.append(f"  Alle data-hooks: {hooks[:60]}")
            node = first
            for _ in range(4):
                node = node.parent
                if node is None:
                    break
            if node is not None:
                report.append("\n  HTML um den 1. Titel (4 Ebenen hoch, gekürzt):")
                report.append("  " + str(node)[:2000])
        self._dump("\n".join(report))
        return events

    @staticmethod
    def _date_el(node):
        """The date element inside ``node``, whichever hook Wix is using."""
        for hook in DATE_HOOKS:
            found = node.select_one(hook)
            if found is not None:
                return found
        return None

    @classmethod
    def _container(cls, title_el):
        """Smallest ancestor of the title that also holds a date.

        Wix renames its ``data-hook`` values from time to time, so we accept
        any known hook and -- as a last resort -- any ancestor whose text
        contains a parsable date. Without that fallback a renamed hook makes
        the whole source silently return zero events.
        """
        node = title_el
        for _ in range(12):
            node = node.parent
            if node is None:
                return None
            if cls._date_el(node) is not None:
                return node
        node = title_el
        for _ in range(12):
            node = node.parent
            if node is None:
                return None
            if cls._parse_date(node.get_text(" ", strip=True)):
                return node
        return None

    def _build(self, title_el, container) -> tuple[Event | None, str | None]:
        title = title_el.get_text(" ", strip=True)
        if not title:
            return None, None
        date_el = self._date_el(container)
        start = None
        if date_el is not None:
            # <time datetime="..."> traegt das Datum im Attribut, nicht im Text.
            start = (self._parse_date(date_el.get("datetime") or "")
                     or self._parse_date(date_el.get_text(" ", strip=True)))
        if not start:
            start = self._parse_date(container.get_text(" ", strip=True))
        if not start:
            return None, None
        loc_el = None
        for hook in LOCATION_HOOKS:
            loc_el = container.select_one(hook)
            if loc_el is not None:
                break
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
        """Read "18. Juni 2026, 19:00", "18.06.2026 19:00" or an ISO string."""
        text = (text or "").strip()
        if not text:
            return None
        # <time datetime="2026-06-18T19:00:00+02:00">
        iso = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{1,2}):(\d{2}))?", text)
        if iso:
            try:
                return _dt.datetime(
                    int(iso.group(1)), int(iso.group(2)), int(iso.group(3)),
                    int(iso.group(4) or 0), int(iso.group(5) or 0))
            except ValueError:
                return None
        m = DATE_RE.search(text)
        if m:
            month = MONTHS.get(m.group(2).lower().rstrip("."))
            if month:
                day = int(m.group(1))
                year = int(m.group(3)) if m.group(3) else _infer_year(month, day)
                try:
                    return _dt.datetime(
                        year, month, day,
                        int(m.group(4) or 0), int(m.group(5) or 0))
                except ValueError:
                    return None
        m = NUM_DATE_RE.search(text)
        if m:
            year = int(m.group(3))
            if year < 100:
                year += 2000
            try:
                return _dt.datetime(
                    year, int(m.group(2)), int(m.group(1)),
                    int(m.group(4) or 0), int(m.group(5) or 0))
            except ValueError:
                return None
        return None

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "funfacts.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
