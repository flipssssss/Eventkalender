"""Other Nature (sex-positive shop, Neukölln) -- workshops & events.

The Shopify blog exposes an Atom feed (/blogs/events.atom) -- one request, no
detail-page fetching. The event date sits at the start of each post slug
(``14-07-26-...`` = 14.07.2026, sometimes without year ``19-6-...``); the title
is the post title. Genre Kink is set in scrapers/genres.py.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
import xml.etree.ElementTree as ET
from typing import Iterable

from .base import BaseScraper, Event

FEED = "https://other-nature.de/blogs/events.atom"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
ATOM = "{http://www.w3.org/2005/Atom}"
# The post title carries the real date: "18.06.26 // Event Name".
TITLE_DATE = re.compile(r"^\s*(\d{1,2})\.(\d{1,2})\.(\d{2})\s*//\s*(.*)$", re.S)
SLUG_DATE = re.compile(r"/blogs/events/(\d{1,2})-(\d{1,2})(?:-(\d{2}))?")

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/atom+xml,application/xml,*/*;q=0.8",
}


def _strip(html: str | None) -> str | None:
    if not html:
        return None
    t = re.sub(r"<[^>]+>", " ", html)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:500] or None


class OtherNatureScraper(BaseScraper):
    name = "Other Nature"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            xml = self.get(FEED, headers=BROWSER).text
            root = ET.fromstring(xml)
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        today = _dt.date.today()
        events: list[Event] = []
        entries = root.findall(f"{ATOM}entry")
        for e in entries:
            ev = self._build(e, today)
            if ev:
                events.append(ev)
        self._dump(f"entries: {len(entries)} | Events: {len(events)}\n" +
                   "\n".join(f"  {e.start} | {e.title}" for e in events[:30]))
        return events

    def _build(self, entry, today) -> Event | None:
        title_el = entry.find(f"{ATOM}title")
        title = (title_el.text or "").strip() if title_el is not None else ""
        href = None
        for link in entry.findall(f"{ATOM}link"):
            if link.get("rel", "alternate") == "alternate":
                href = link.get("href")
                break
        if not title or not href:
            return None
        # Prefer the date from the title ("18.06.26 // Name"); fall back to slug.
        tm = TITLE_DATE.match(title)
        if tm:
            day, mon, year = int(tm.group(1)), int(tm.group(2)), 2000 + int(tm.group(3))
            title = tm.group(4).strip()
        else:
            m = SLUG_DATE.search(href)
            if not m:
                return None
            day, mon = int(m.group(1)), int(m.group(2))
            year = (2000 + int(m.group(3)) if m.group(3)
                    else today.year + (1 if (mon, day) < (today.month, today.day) else 0))
        if not title:
            return None
        try:
            start = _dt.datetime(year, mon, day, 19, 0)
        except ValueError:
            return None
        content_el = entry.find(f"{ATOM}content")
        desc = _strip(content_el.text if content_el is not None else None)
        # History/Talks are Vorträge, der Rest Workshops.
        low = title.lower()
        cat = "Vortrag" if any(k in low for k in (
            "history", "geschichte", "talk", "reading", "lesung")) else "Workshop"
        return Event(
            title=title[:160],
            start=start,
            source_url=href,
            source_name=self.name,
            location="Other Nature",
            address="Mareschstraße 14, 12055 Berlin",
            description=desc,
            time_known=False,
            tags=[cat],
        )

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "other-nature.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
