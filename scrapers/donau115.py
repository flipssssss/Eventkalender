"""Scraper for Donau115 (Berlin jazz club).

The site renders its programme client-side from a public Firebase
Realtime Database export (``events.json``). We read that JSON directly.
All events are forced onto the "Konzert" category.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from typing import Iterable

from .base import BaseScraper, Event, parse_datetime

EVENTS_URL = (
    "https://shifts-a77a1-default-rtdb.europe-west1.firebasedatabase.app/events.json"
)
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

TITLE_KEYS = ("title", "name", "event", "artist", "act", "headline")
DATE_KEYS = ("date", "start", "startDate", "datetime", "day", "when")
TIME_KEYS = ("time", "start_time", "startTime", "doors", "beginn")
DESC_KEYS = ("description", "text", "info", "details", "subtitle", "support")
IMAGE_KEYS = ("image", "img", "photo", "flyer", "picture", "imageUrl")
LINK_KEYS = ("link", "url", "tickets", "ticketLink", "ticket_url")


class Donau115Scraper(BaseScraper):
    name = "Donau115"

    def __init__(self, url: str = EVENTS_URL, write_debug: bool = True):
        self.url = url
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        response = self.get(self.url, headers={"Accept": "application/json"})
        data = response.json()

        items = []
        if isinstance(data, dict):
            items = [v for v in data.values() if isinstance(v, dict)]
        elif isinstance(data, list):
            items = [v for v in data if isinstance(v, dict)]

        events: list[Event] = []
        for item in items:
            event = self._build(item)
            if event:
                events.append(event)

        if self.write_debug:
            sample = json.dumps(items[:2], ensure_ascii=False, indent=2)[:2500]
            self._dump_debug(
                f"URL: {self.url}\nGefundene Einträge: {len(items)}\n"
                f"Events geparst: {len(events)}\n"
                f"Beispiel-Datensätze:\n{sample}"
            )
        return events

    def _build(self, item: dict) -> Event | None:
        title = _first(item, TITLE_KEYS)
        date_raw = _first(item, DATE_KEYS)
        if not title or date_raw is None:
            return None

        start = _to_datetime(date_raw)
        if not start:
            return None
        # If the date had no time, try to add a separate time field.
        if start.hour == 0 and start.minute == 0:
            time_raw = _first(item, TIME_KEYS)
            parsed_time = parse_datetime(f"{start.date().isoformat()} {time_raw}") if time_raw else None
            if parsed_time:
                start = parsed_time

        link = _first(item, LINK_KEYS) or "https://www.donau115.de"
        image = _first(item, IMAGE_KEYS)

        return Event(
            title=str(title).strip(),
            start=start,
            source_url=str(link),
            source_name=self.name,
            location="Donau115, Donaustraße 115, Berlin",
            description=_first(item, DESC_KEYS),
            image_url=str(image) if image else None,
            tags=["Konzert"],
        )

    def _dump_debug(self, text: str) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "donau115.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass


def _first(item: dict, keys):
    for key in keys:
        if key in item and item[key] not in (None, "", []):
            return item[key]
    return None


def _to_datetime(value):
    # Epoch (seconds or milliseconds)?
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        num = int(value)
        if num > 10_000_000_000:  # milliseconds
            num //= 1000
        try:
            return _dt.datetime.fromtimestamp(num)
        except (OverflowError, OSError, ValueError):
            return None
    return parse_datetime(value)
