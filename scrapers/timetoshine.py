"""Time to Shine (Kink/Fetish comedy shows) -- Squarespace events.

Squarespace exposes any collection as JSON via ``?format=json``. The events
collection returns ``items`` with epoch-millisecond start/end dates, a title,
a location block and an image. Category Theater, genre Kink (forced).
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from typing import Iterable

from .base import BaseScraper, Event

BASE = "https://www.timetoshinekink.com"
# /all-events turned out to be a page, not the events collection. Try the
# common Squarespace events-collection slugs and use whichever has events.
CANDIDATES = ["/all-events", "/events", "/shows", "/calendar",
              "/upcoming-events", "/upcoming"]
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*",
}


def _ms(value) -> _dt.datetime | None:
    if not isinstance(value, (int, float)):
        return None
    return _dt.datetime.fromtimestamp(value / 1000)


class TimeToShineScraper(BaseScraper):
    name = "Time to Shine Kink"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        notes = []
        for path in CANDIDATES:
            url = BASE + path + "?format=json"
            try:
                r = self.get(url, headers=BROWSER)
                data = json.loads(r.content)
            except Exception as exc:  # noqa: BLE001
                notes.append(f"{path}: FEHLER {str(exc)[:50]}")
                continue
            items = (data.get("items") or []) + (data.get("upcoming") or []) \
                + (data.get("past") or [])
            events = [ev for it in items if (ev := self._build(it))]
            coll = (data.get("collection") or {})
            notes.append(f"{path}: type={coll.get('typeName')} items={len(items)} "
                         f"events={len(events)}")
            if events:
                self._dump(f"Quelle: {path}\n" + "\n".join(notes) + "\n\n" +
                           "\n".join(f"  {e.start} | {e.title}" for e in events[:20]))
                return events
        self._dump("Keine Events gefunden:\n" + "\n".join(notes))
        return []

    def _build(self, it: dict) -> Event | None:
        start = _ms(it.get("startDate"))
        title = (it.get("title") or "").strip()
        if not start or not title:
            return None
        loc = it.get("location") or {}
        venue = loc.get("addressTitle")
        address = ", ".join(p for p in [loc.get("addressLine1"),
                                        loc.get("addressLine2")] if p) or None
        path = it.get("fullUrl") or ""
        url = (BASE + path) if path.startswith("/") else (path or BASE)
        image = it.get("assetUrl") if isinstance(it.get("assetUrl"), str) else None

        return Event(
            title=title[:140],
            start=start,
            end=_ms(it.get("endDate")),
            source_url=url,
            source_name=self.name,
            location=venue,
            address=address,
            description=(it.get("excerpt") or "").strip() or None,
            image_url=image,
            tags=["Theater"],
        )

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "time-to-shine.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
