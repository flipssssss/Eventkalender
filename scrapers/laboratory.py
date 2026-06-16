"""Lab.oratory (Berghain-Gebäude) -- men-only fetish parties.

The site lists events as plain text, each as:

    THURSDAY 18.06.2026 21:00 NAKED SEX PARTY strict dresscode: fully naked …

We read date, time, an UPPERCASE title and the trailing description. All events
are category Party, genre Kink (forced in genres.py).
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URL = "https://www.lab-oratory.de/"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

_WD = "MONDAY|TUESDAY|WEDNESDAY|THURSDAY|FRIDAY|SATURDAY|SUNDAY|SPECIAL"
EVENT_RE = re.compile(
    rf"(?:(?:{_WD})\s+)?(\d{{2}})\.(\d{{2}})\.(\d{{4}})\s+(\d{{1,2}}):(\d{{2}})\s+"
    rf"(.*?)(?=(?:{_WD})\s+\d{{2}}\.\d{{2}}\.\d{{4}}\s+\d|$)",
    re.IGNORECASE | re.DOTALL,
)
TITLE_RE = re.compile(r"^([0-9A-ZÄÖÜß][0-9A-ZÄÖÜß '&!/+\-]+)")


class LaboratoryScraper(BaseScraper):
    name = "Lab.oratory"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(URL, headers=BROWSER).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        text = re.sub(r"\s+", " ", BeautifulSoup(html, "html.parser").get_text(" "))

        events: list[Event] = []
        seen: set[str] = set()
        for m in EVENT_RE.finditer(text):
            day, mon, year, hh, mm = (int(m.group(i)) for i in range(1, 6))
            try:
                start = _dt.datetime(year, mon, day, hh, mm)
            except ValueError:
                continue
            chunk = m.group(6).strip()
            tm = TITLE_RE.match(chunk)
            title = (tm.group(1).strip() if tm else chunk[:40]).strip()
            if len(title) < 2:
                continue
            desc = chunk[len(title):].strip(" -–—:") or None

            key = f"{title.lower()}|{start}"
            if key in seen:
                continue
            seen.add(key)
            events.append(Event(
                title=title[:140],
                start=start,
                source_url=URL,
                source_name=self.name,
                location="Lab.oratory",
                address="Am Wriezener Bahnhof, 10243 Berlin",
                description=desc[:400] if desc else None,
                tags=["Party"],
            ))

        self._dump(f"Events: {len(events)}\n" +
                   "\n".join(f"  {e.start} | {e.title}" for e in events[:20]))
        return events

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "lab-oratory.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
