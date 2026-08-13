"""Möbel Olfe (queere Bar, Kreuzberg) -- programm.php.

The page is a tiny static HTML table; events sit in ``.event-block`` elements.
We parse a date (DD.MM) + time + title heuristically and dump the raw blocks to
the debug file so the parser can be refined if a site detail differs.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
import time as _time
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event, GERMAN_MONTHS

URL = "https://www.moebel-olfe.de/programm.php"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
MONTHS = GERMAN_MONTHS
# "Donnerstag, 18. Juni 21:30" oder "Freitag, 14. Aug. 22:00" (abgekürzt, mit
# Punkt) -> Tag, Monatsname, (optional) HH:MM
DATETIME_RE = re.compile(
    r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\.?(?:\s+(\d{1,2}):(\d{2}))?")

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


class MoebelOlfeScraper(BaseScraper):
    name = "Möbel Olfe"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        # Die Seite liefert gelegentlich (trotz HTTP 200) eine leere Antwort
        # ohne ``.event-block``. Bei leerem Ergebnis kurz warten und erneut
        # abrufen, statt sofort 0 Events zu melden.
        blocks = []
        last_err = None
        for attempt in range(3):
            try:
                html = self.get(URL, headers=BROWSER).text
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                html = ""
            blocks = BeautifulSoup(html, "html.parser").select(".event-block")
            if blocks:
                break
            if attempt < 2:
                _time.sleep(3.0 * (attempt + 1))
        if not blocks and last_err is not None:
            self._dump(f"FEHLER: {last_err}")
            return []
        today = _dt.date.today()
        events: list[Event] = []
        for b in blocks:
            ev = self._build(b, today)
            if ev:
                events.append(ev)
        dump = "\n\n----\n".join(b.prettify()[:900] for b in blocks[:4])
        self._dump(f"event-blocks: {len(blocks)} | Events: {len(events)}\n\n{dump}")
        return events

    def _build(self, block, today) -> Event | None:
        t_el = block.select_one(".event-time")
        title_el = block.select_one(".event-title")
        if not t_el or not title_el:
            return None
        m = DATETIME_RE.search(t_el.get_text(" ", strip=True))
        if not m:
            return None
        day = int(m.group(1))
        month = MONTHS.get(m.group(2).lower())
        if not month:
            return None
        has_time = m.group(3) is not None
        hour, minute = (int(m.group(3)), int(m.group(4))) if has_time else (20, 0)
        year = today.year + (1 if (month, day) < (today.month, today.day) else 0)
        try:
            start = _dt.datetime(year, month, day, hour, minute)
        except ValueError:
            return None
        title = title_el.get_text(" ", strip=True)
        if not title:
            return None
        desc_el = block.select_one(".event-description")
        desc = desc_el.get_text(" ", strip=True) if desc_el else None
        return Event(
            title=title[:160],
            start=start,
            source_url=URL,
            source_name=self.name,
            location="Möbel Olfe",
            address="Reichenberger Str. 177, 10999 Berlin",
            description=desc or None,
            time_known=has_time,
            tags=["Party"],
        )

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "m-bel-olfe.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
