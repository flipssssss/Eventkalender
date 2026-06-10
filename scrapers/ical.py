"""Generic scraper for iCalendar (.ics) feeds.

iCalendar is a strict, widely used standard, so parsing an ``.ics`` feed
is far more reliable than scraping HTML. Many event platforms expose one
-- for example radar.squat.net offers a feed per group at
``https://radar.squat.net/ical/node/<id>``.

Configure an iCal source in ``sources.yml`` with ``type: ical``.
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable

from icalendar import Calendar

from .base import BaseScraper, Event


def _to_datetime(value) -> _dt.datetime | None:
    """Normalise an iCal date/datetime value to a naive datetime."""
    if value is None:
        return None
    dt = getattr(value, "dt", value)
    if isinstance(dt, _dt.datetime):
        # Drop timezone info so all events compare/sort consistently.
        return dt.replace(tzinfo=None)
    if isinstance(dt, _dt.date):
        return _dt.datetime(dt.year, dt.month, dt.day)
    return None


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _tags(component) -> list[str]:
    raw = component.get("categories")
    if not raw:
        return []
    # icalendar may give a vCategory, a list, or a comma string.
    cats = getattr(raw, "cats", None)
    if cats:
        return [str(c).strip() for c in cats if str(c).strip()]
    return [part.strip() for part in str(raw).split(",") if part.strip()]


def _image(component) -> str | None:
    # Non-standard but common: IMAGE or ATTACH pointing at a picture.
    for key in ("IMAGE", "ATTACH"):
        value = component.get(key)
        if value:
            url = str(value).strip()
            if url.lower().startswith("http"):
                return url
    return None


class ICalScraper(BaseScraper):
    """Read events from an iCalendar (.ics) feed."""

    def __init__(self, url: str, name: str | None = None, default_tags=None):
        self.url = url
        self.name = name or url
        self.default_tags = list(default_tags or [])

    def fetch_events(self) -> Iterable[Event]:
        # A non-"Mozilla" user agent plus a calendar Accept header gets
        # past bot walls like Anubis, which only challenge browser-like
        # requests. Plain feed fetchers are allowed through.
        response = self.get(
            self.url,
            headers={
                "User-Agent": "Eventkalender-Feed/1.0 (+https://github.com/flipssssss/eventkalender)",
                "Accept": "text/calendar, application/calendar+xml, text/plain, */*",
            },
        )
        calendar = Calendar.from_ical(response.content)
        events: list[Event] = []

        for component in calendar.walk("VEVENT"):
            start = _to_datetime(component.get("dtstart"))
            title = _text(component.get("summary"))
            if not start or not title:
                continue

            source_url = _text(component.get("url")) or self.url
            tags = self.default_tags + _tags(component)

            events.append(
                Event(
                    title=title,
                    start=start,
                    end=_to_datetime(component.get("dtend")),
                    source_url=source_url,
                    source_name=self.name,
                    location=_text(component.get("location")),
                    description=_text(component.get("description")),
                    image_url=_image(component),
                    tags=tags,
                )
            )
        return events
