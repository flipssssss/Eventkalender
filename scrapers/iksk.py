"""IKSK Berlin (iksk-berlin.de/Program) -- kuratierte Kink-Specials.

The program page is server-rendered (Wix): each event is a paragraph with a
``<strong>`` title, a ``<span>`` holding "// Ort // Datum //" and a "MORE"
link. We parse that directly (one request, no detail fetches). Dates are day/
month, often a range -- we take the first day. Genre Kink via scrapers/genres.py.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URL = "https://www.iksk-berlin.de/Program"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

# Start day+month from "17.-19.07", "31.07 - 02.08", "3.-5.06", "18.07".
_CROSS = re.compile(r"(\d{1,2})\.(\d{1,2})\.?\s*[-–]\s*\d{1,2}\.\d{1,2}")
_INTRA = re.compile(r"(\d{1,2})\.\s*[-–]\s*\d{1,2}\.(\d{1,2})")
_SINGLE = re.compile(r"(\d{1,2})\.(\d{1,2})")

# Überschriften, die keine Events sind.
_SKIP_TITLES = {
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december",
    "januar", "februar", "märz", "märz", "april", "mai", "juni", "juli",
    "august", "september", "oktober", "november", "dezember", "specials",
}


def _start_daymonth(text: str):
    for rx in (_CROSS, _INTRA, _SINGLE):
        m = rx.search(text)
        if m:
            return int(m.group(1)), int(m.group(2))
    return None


class IkskScraper(BaseScraper):
    name = "IKSK Berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(URL, headers=BROWSER).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        soup = BeautifulSoup(html, "html.parser")
        today = _dt.date.today()
        events: list[Event] = []
        seen: set[str] = set()
        links = [a for a in soup.find_all("a")
                 if a.get_text(strip=True).upper() == "MORE"]
        for a in links:
            ev = self._build(a, today)
            if ev and ev.title.lower() not in seen:
                seen.add(ev.title.lower())
                events.append(ev)
        self._dump(f"MORE-Links: {len(links)} | Events: {len(events)}\n" +
                   "\n".join(f"  {e.start} | {e.title}" for e in events[:30]))
        return events

    def _build(self, link, today) -> Event | None:
        p = link.find_parent("p") or link.parent
        if p is None:
            return None
        strong = p.find("strong")
        title = strong.get_text(" ", strip=True) if strong else ""
        low = title.lower().strip()
        # Monats-/Abschnittsüberschriften und zu kurze Titel überspringen.
        if not title or low in _SKIP_TITLES or "special" in low or len(title) < 3:
            return None
        # Date text: the paragraph text without the title.
        ptext = p.get_text(" ", strip=True)
        dm = _start_daymonth(ptext)
        if not dm:
            return None
        day, mon = dm
        if not (1 <= mon <= 12 and 1 <= day <= 31):
            return None
        year = today.year + (1 if (mon, day) < (today.month, today.day) else 0)
        try:
            start = _dt.datetime(year, mon, day, 20, 0)
        except ValueError:
            return None
        href = link.get("href") or URL
        # Venue: between the first two "//" in the paragraph, if present.
        venue = None
        parts = [s.strip() for s in ptext.split("//")]
        if len(parts) >= 2 and parts[1]:
            venue = parts[1][:80]
        return Event(
            title=title[:160],
            start=start,
            source_url=href,
            source_name=self.name,
            location=venue or "Berlin",
            time_known=False,
            tags=["Party"],
        )

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "iksk-berlin.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
