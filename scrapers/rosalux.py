"""Rosa-Luxemburg-Stiftung -- politische Vorträge/Diskussionen.

The events page (rosalux.de/veranstaltungen) is server-rendered HTML (no
JSON-LD): each event is a ``section.elasticsearch__result`` carrying a
``data-ts`` start timestamp (ms), with the title, city and type inside a
``.teaser--event``. Foundation events are nationwide, so only Berlin ones are
kept. All kept events are category Vortrag; genre Polit is set in
scrapers/genres.py.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/Berlin")
except Exception:  # noqa: BLE001
    _TZ = None

BASE = "https://www.rosalux.de"
URL = BASE + "/veranstaltungen"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")

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


class RosaLuxScraper(BaseScraper):
    name = "Rosa-Luxemburg-Stiftung"

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
        secs = soup.select("section.elasticsearch__result")
        events: list[Event] = []
        other_city = 0
        for sec in secs:
            ev, city = self._build(sec)
            if ev is None:
                continue
            if self.city and self.city.lower() not in (city or "").lower():
                other_city += 1
                continue
            events.append(ev)
        self._dump(f"Teaser: {len(secs)} | {self.city}: {len(events)} | "
                   f"andere Städte: {other_city}\n" +
                   "\n".join(f"  {e.start} | {e.location} | {e.title}"
                             for e in events[:30]))
        return events

    def _build(self, sec) -> tuple[Event | None, str | None]:
        link = sec.select_one("a.teaser__link")
        title_el = sec.select_one(".teaser__title-text")
        ts = sec.get("data-ts")
        if not (link and title_el and ts and ts.isdigit()):
            return None, None
        start = self._start(ts)
        if not start:
            return None, None
        title = title_el.get_text(" ", strip=True)
        if not title:
            return None, None
        city = self._city(sec)
        desc_el = sec.select_one(".teaser__text")
        href = link.get("href") or ""
        return Event(
            title=title[:160],
            start=start,
            source_url=urljoin(BASE, href) if href else URL,
            source_name=self.name,
            location=city or "Berlin",
            description=(desc_el.get_text(" ", strip=True)[:500] if desc_el else None),
            tags=["Vortrag"],
        ), city

    @staticmethod
    def _start(ts: str) -> _dt.datetime | None:
        try:
            epoch = int(ts) / 1000
        except (TypeError, ValueError):
            return None
        if _TZ:
            return _dt.datetime.fromtimestamp(epoch, _TZ).replace(tzinfo=None)
        return _dt.datetime.utcfromtimestamp(epoch)

    @staticmethod
    def _city(sec) -> str | None:
        # The right-hand date group holds the city as a class-less span
        # (the date itself sits in .teaser__date-day/-month/-year spans).
        for sp in sec.select(".teaser__date-group--right > span"):
            if sp.select_one(".teaser__date-day"):
                continue
            txt = sp.get_text(" ", strip=True)
            if txt and not TIME_RE.search(txt):
                return txt
        return None

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "rosa-luxemburg-stiftung.txt").write_text(
                text, encoding="utf-8")
        except OSError:
            pass
