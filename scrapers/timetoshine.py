"""Time to Shine (Kink/Queer/Fetish comedy shows) -- via Eventbrite.

Their Squarespace site only links out to an Eventbrite organizer
(``timetoshine11.eventbrite.de``). Eventbrite event pages carry a clean
schema.org ``Event`` as JSON-LD, so we collect the event links from the
organizer page and read each event's structured data. Category Theater, genre
Kink (forced in genres.py).
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
import re
from typing import Iterable

import requests

from .base import BaseScraper, Event, parse_datetime

ORGANIZER = "https://timetoshine11.eventbrite.de/"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
MAX_EVENTS = 20

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}
EVENT_URL_RE = re.compile(r"https?://www\.eventbrite\.[a-z.]+/e/[A-Za-z0-9%\-]+")


class TimeToShineScraper(BaseScraper):
    name = "Time to Shine Kink"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(BROWSER)
        try:
            html = session.get(ORGANIZER, timeout=25).text
        except requests.RequestException as exc:
            self._dump(f"Organizer FEHLER: {exc}")
            return []

        urls = []
        for u in EVENT_URL_RE.findall(html):
            u = u.split("?")[0]
            if u not in urls:
                urls.append(u)
        urls = urls[:MAX_EVENTS]

        events: list[Event] = []
        sample = ""
        for url in urls:
            try:
                page = session.get(url, timeout=25).text
            except requests.RequestException:
                continue
            obj = _event_jsonld(page)
            if not sample:
                sample = f"{url}\nJSON-LD: {bool(obj)} | Felder: " \
                         f"{sorted(obj) if obj else '-'}"
            events.extend(self._build(obj, url))

        self._dump(f"Event-Links: {len(urls)} | Events: {len(events)}\n{sample}\n" +
                   "\n".join(f"  {e.start} | {e.title}" for e in events[:20]))
        return events

    def _build(self, obj: dict | None, url: str) -> list[Event]:
        if not obj:
            return []
        start = parse_datetime(obj.get("startDate"))
        name = (obj.get("name") or "").strip()
        if not start or not name:
            return []
        start = start.replace(tzinfo=None)
        end = parse_datetime(obj.get("endDate"))
        end = end.replace(tzinfo=None) if end else None

        loc = obj.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        venue = loc.get("name") if isinstance(loc, dict) else None
        address = _address(loc.get("address")) if isinstance(loc, dict) else None
        image = obj.get("image")
        if isinstance(image, list):
            image = image[0] if image else None
        if isinstance(image, dict):
            image = image.get("url")
        image = image if isinstance(image, str) else None
        desc = (obj.get("description") or "").strip()[:400] or None
        src = obj.get("url") or url

        # A run across several calendar days (e.g. shows on the 18th + 19th) is
        # split into one event per day. A late night ending after midnight
        # (end hour < 12) stays a single event.
        starts = [start]
        if end and end.date() > start.date() and end.hour >= 12:
            starts = []
            day = start.date()
            while day <= end.date():
                starts.append(_dt.datetime.combine(day, start.time()))
                day += _dt.timedelta(days=1)

        return [Event(
            title=name[:140],
            start=s,
            source_url=src,
            source_name=self.name,
            location=venue,
            address=address,
            description=desc,
            image_url=image,
            tags=["Theater"],
        ) for s in starts]

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "time-to-shine.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass


def _event_jsonld(html: str) -> dict | None:
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL,
    ):
        try:
            data = json.loads(m.group(1).strip())
        except ValueError:
            continue
        for obj in (data if isinstance(data, list) else [data]):
            if not isinstance(obj, dict):
                continue
            t = obj.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(isinstance(x, str) and "Event" in x for x in types):
                return obj
    return None


def _address(addr) -> str | None:
    if isinstance(addr, str):
        return addr or None
    if not isinstance(addr, dict):
        return None
    parts = [addr.get("streetAddress"),
             " ".join(filter(None, [addr.get("postalCode"),
                                    addr.get("addressLocality")]))]
    return ", ".join(p for p in parts if p) or None
