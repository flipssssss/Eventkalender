"""Generic scraper for Modern Events Calendar (MEC) WordPress sites.

Several venues run MEC (Boiler, Club Sauna ...). Its list markup is stable:
each ``.mec-event-article`` carries the year+month in a ``mec-toggle-YYYYMM``
class, the day in ``.event-d`` and the title in ``.mec-event-title``. This
class turns that into events; per-source genre is set in scrapers/genres.py.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


class MecScraper(BaseScraper):
    def __init__(self, name: str, url: str, *, address: str | None = None,
                 fixed_hour: int | None = None, category: str = "Party",
                 write_debug: bool = True):
        self.name = name
        self.url = url
        self.address = address
        self.fixed_hour = fixed_hour
        self.category = category
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(self.url, headers=BROWSER).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()
        for art in soup.select(".mec-event-article"):
            ev = self._build(art)
            if ev:
                key = f"{ev.title.lower()}|{ev.start.date()}"
                if key not in seen:
                    seen.add(key)
                    events.append(ev)
        self._dump(f"Events: {len(events)}\n" +
                   "\n".join(f"  {e.start} | {e.title}" for e in events[:25]))
        return events

    def _build(self, art) -> Event | None:
        cls = " ".join(art.get("class", []))
        ym = re.search(r"mec-toggle-(\d{4})(\d{2})", cls)
        day_el = art.select_one(".event-d")
        link = art.select_one(".mec-event-title a") or art.select_one(".mec-event-title")
        if not (ym and day_el and link):
            return None
        try:
            year, month = int(ym.group(1)), int(ym.group(2))
            day = int(re.sub(r"\D", "", day_el.get_text()) or 0)
        except ValueError:
            return None
        title = re.sub(r"\s+", " ", link.get_text(" ")).strip()
        if not title:
            return None

        hour, minute, time_known = self._time(art)
        try:
            start = _dt.datetime(year, month, day, hour, minute)
        except ValueError:
            return None

        href = link.get("href") if link.name == "a" else None
        place = art.select_one(".mec-event-loc-place")
        location = (place.get_text(" ", strip=True) if place else None) or self.name
        return Event(
            title=title[:140],
            start=start,
            source_url=href or self.url,
            source_name=self.name,
            location=location,
            address=self.address,
            time_known=time_known,
            tags=[self.category],
        )

    def _time(self, art):
        if self.fixed_hour is not None:
            return self.fixed_hour, 0, True
        el = art.select_one("[class*=mec-time], [class*=mec-event-time]")
        text = el.get_text(" ") if el else art.get_text(" ")
        m = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
        if m:
            return int(m.group(1)), int(m.group(2)), True
        return 0, 0, False

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
            (DEBUG_DIR / f"{slug}.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
