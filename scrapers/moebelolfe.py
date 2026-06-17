"""Möbel Olfe (queere Bar, Kreuzberg) -- programm.php.

The page is a tiny static HTML table; events sit in ``.event-block`` elements.
We parse a date (DD.MM) + time + title heuristically and dump the raw blocks to
the debug file so the parser can be refined if a site detail differs.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URL = "https://www.moebel-olfe.de/programm.php"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.")
TIME_RE = re.compile(r"\b(\d{1,2})[:.](\d{2})\b")

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
        try:
            html = self.get(URL, headers=BROWSER).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        soup = BeautifulSoup(html, "html.parser")
        blocks = soup.select(".event-block")
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
        text = block.get_text(" ", strip=True)
        dm = DATE_RE.search(text)
        if not dm:
            return None
        day, mon = int(dm.group(1)), int(dm.group(2))
        year = today.year + (1 if (mon, day) < (today.month, today.day) else 0)
        # Time: first HH:MM after the date (skip the date match span).
        rest = text[dm.end():]
        tm = TIME_RE.search(rest)
        hour, minute = (int(tm.group(1)), int(tm.group(2))) if tm else (20, 0)
        try:
            start = _dt.datetime(year, mon, day, hour, minute)
        except ValueError:
            return None
        # Title: a heading inside the block, else the text after date/time.
        head = block.select_one("h1,h2,h3,h4,.event-title,strong,b")
        title = (head.get_text(" ", strip=True) if head else "").strip()
        if not title:
            tail = rest[tm.end():] if tm else rest
            title = re.sub(r"\s+", " ", tail).strip()
        if not title:
            return None
        return Event(
            title=title[:160],
            start=start,
            source_url=URL,
            source_name=self.name,
            location="Möbel Olfe",
            address="Reichenberger Str. 177, 10999 Berlin",
            time_known=bool(tm),
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
