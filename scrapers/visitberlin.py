"""visitBerlin blues/jazz category -- follows the event detail links.

The category page (visitberlin.de/de/kategorie/blues-jazz) renders its list
client-side (no JSON-LD), but it links to ``/de/event/<slug>`` detail pages,
which do carry schema.org Event JSON-LD. This collects those links and reads
each detail page. All events are forced to category Konzert (genre Kultur).
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable
from urllib.parse import urljoin

from .base import BaseScraper, Event
from .jsonld import extract_events_from_html

BASE = "https://www.visitberlin.de"
LISTING = BASE + "/de/kategorie/blues-jazz"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
EVENT_LINK_RE = re.compile(r'href="(/de/event/[a-z0-9][a-z0-9\-]*)"', re.I)

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


class VisitBerlinJazzScraper(BaseScraper):
    name = "visitBerlin Jazz"

    def __init__(self, category: str = "Konzert", max_events: int = 50,
                 write_debug: bool = True):
        self.category = category
        self.max_events = max_events
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(LISTING, headers=BROWSER).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER (Liste): {exc}")
            return []
        paths = list(dict.fromkeys(EVENT_LINK_RE.findall(html)))[:self.max_events]
        events: list[Event] = []
        seen: set[str] = set()
        for path in paths:
            url = urljoin(BASE, path)
            try:
                dhtml = self.get(url, headers=BROWSER).text
            except Exception:  # noqa: BLE001
                continue
            for ev in extract_events_from_html(dhtml, url, self.name):
                ev.tags = [self.category]
                ev.source_url = url
                key = url + "|" + (ev.start.isoformat() if ev.start else "")
                if key in seen:
                    continue
                seen.add(key)
                events.append(ev)
        self._dump(f"Event-Links: {len(paths)} | Events: {len(events)}\n" +
                   "\n".join(f"  {e.start} | {e.location} | {e.title}"
                             for e in events[:30]))
        return events

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "visitberlin-jazz.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
