"""berlin.de/ausstellungen -- current Berlin exhibitions.

Every exhibition is embedded as a schema.org ``ExhibitionEvent`` (JSON-LD) with
name, start/end dates and the venue's full address. Exhibitions run for weeks,
so a single start time doesn't fit the day-grouped feed: we anchor a running
exhibition to *today* (date only, sorted to the end of the day) and an upcoming
one to its opening day, and note the run end in the description.

All events are category Ausstellung and genre Kultur (forced in genres.py).
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event, parse_datetime

URL = "https://www.berlin.de/ausstellungen/"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def _naive(value) -> _dt.datetime | None:
    dt = parse_datetime(value)
    return dt.replace(tzinfo=None) if dt else None


class BerlinAusstellungenScraper(BaseScraper):
    name = "Ausstellungen Berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(URL, headers=BROWSER).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        soup = BeautifulSoup(html, "html.parser")

        now = _dt.datetime.now()
        events: list[Event] = []
        seen: set[str] = set()
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (ValueError, TypeError):
                continue
            for obj in data if isinstance(data, list) else [data]:
                ev = self._build(obj, now)
                if ev and ev.title not in seen:
                    seen.add(ev.title)
                    events.append(ev)

        self._dump(f"ExhibitionEvents -> Events: {len(events)}\n" +
                   "\n".join(f"  {e.start.date()} {e.title[:50]}" for e in events))
        return events

    def _build(self, obj, now: _dt.datetime) -> Event | None:
        if not isinstance(obj, dict):
            return None
        t = obj.get("@type")
        types = t if isinstance(t, list) else [t]
        if not any(isinstance(x, str) and "Event" in x for x in types):
            return None
        name = (obj.get("name") or "").strip()
        if not name:
            return None

        start_dt = _naive(obj.get("startDate"))
        end_dt = _naive(obj.get("endDate"))
        if end_dt and end_dt < now:
            return None  # exhibition already over

        # Running -> anchor to today; upcoming -> its opening day. Date only,
        # sorted to the end of the day so timed events stay on top.
        anchor = start_dt if (start_dt and start_dt > now) else now
        start = _dt.datetime(anchor.year, anchor.month, anchor.day, 23, 59)

        loc = obj.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        venue = loc.get("name") if isinstance(loc, dict) else None
        address = self._address(loc.get("address") if isinstance(loc, dict) else None)

        desc = (obj.get("description") or "").strip()
        if end_dt:
            note = f"Läuft bis {end_dt:%d.%m.%Y}"
            desc = f"{desc}  ·  {note}" if desc else note

        image = obj.get("image")
        if isinstance(image, list):
            image = image[0] if image else None
        if isinstance(image, dict):
            image = image.get("url")

        return Event(
            title=name[:140],
            start=start,
            source_url=obj.get("url") or URL,
            source_name=self.name,
            location=venue,
            address=address,
            description=desc or None,
            image_url=image if isinstance(image, str) else None,
            time_known=False,
            tags=["Ausstellung"],
        )

    @staticmethod
    def _address(addr) -> str | None:
        if not isinstance(addr, dict):
            return None
        street = addr.get("streetAddress")
        tail = " ".join(filter(None, [addr.get("postalCode"),
                                      addr.get("addressLocality")]))
        return ", ".join(p for p in [street, tail] if p) or None

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "ausstellungen.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
