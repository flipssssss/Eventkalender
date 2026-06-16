"""König Drag Show -- Google Sites page (text only).

The shows are described in prose, e.g. "König Theater - Graduation show /
5th and 6th September 2026 at Theater im Delphi". We read the rendered text,
extract the date(s), venue and the nearest "… show" title. Category Theater,
genre Queer (forced in genres.py).
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URL = "https://www.konigdragshow.com/dragshows"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en;q=0.9,de;q=0.8",
}

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}

# "5th and 6th September 2026" / "12 October 2026" (optional second day + venue).
DATE_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?(?:\s*(?:and|&|,|-|–|to|\+)\s*"
    r"(\d{1,2})(?:st|nd|rd|th)?)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(\d{4})"
    r"(?:\s+at\s+([A-ZÄÖÜ][\w .,'’\-]{2,50}?)(?=[.,;]|\s{2}|$))?",
    re.IGNORECASE)
SHOW_RE = re.compile(r"([A-ZÄÖÜ][\wäöüß'&./ \-]{2,55}?[Ss]how)\b")


class KoenigScraper(BaseScraper):
    name = "König Drag Show"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(URL, headers=BROWSER).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        text = re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" "))

        shows = [(m.start(), m.group(1).strip()) for m in SHOW_RE.finditer(text)]
        events: list[Event] = []
        seen: set[str] = set()
        for dm in DATE_RE.finditer(text):
            month = MONTHS[dm.group(3).lower()]
            year = int(dm.group(4))
            days = [int(dm.group(1))]
            if dm.group(2):
                days.append(int(dm.group(2)))
            venue = (dm.group(5) or "").strip(" .,") or None
            title = next((t for pos, t in reversed(shows) if pos < dm.start()),
                         "König Drag Show")

            for day in days:
                try:
                    start = _dt.datetime(year, month, day)
                except ValueError:
                    continue
                key = f"{title.lower()}|{start.date()}"
                if key in seen:
                    continue
                seen.add(key)
                events.append(Event(
                    title=title[:140],
                    start=start,
                    source_url=URL,
                    source_name=self.name,
                    location=venue,
                    address=f"{venue}, Berlin" if venue else None,
                    time_known=False,
                    tags=["Theater"],
                ))

        self._dump(f"Events: {len(events)} | Shows erkannt: {len(shows)}\n" +
                   "\n".join(f"  {e.start.date()} | {e.title} @ {e.location}"
                             for e in events[:20]))
        return events

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "koenig.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
