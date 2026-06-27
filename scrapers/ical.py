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
from urllib.parse import urlsplit

import requests
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

    def __init__(self, url: str, name: str | None = None, default_tags=None,
                 category: str | None = None, party_or_workshop: bool = False,
                 include=None):
        self.url = url
        self.name = name or url
        self.default_tags = list(default_tags or [])
        self.category = category
        self.party_or_workshop = party_or_workshop
        # Nur Events behalten, deren Titel einen dieser Begriffe enthält
        # (kleingeschrieben, Teilstring). None/leer = alle behalten.
        self.include = [s.lower() for s in (include or [])]

    def _fetch(self) -> requests.Response:
        """Fetch the feed, trying a plain feed UA then a browser UA.

        A non-"Mozilla" user agent gets past bot walls like Anubis (which only
        challenge browser-like requests). Some sites do the opposite and block
        non-browser agents (403) -- for those we retry looking like a browser.
        """
        origin = "{0.scheme}://{0.netloc}/".format(urlsplit(self.url))
        attempts = [
            {
                "User-Agent": "Eventkalender-Feed/1.0 (+https://github.com/flipssssss/eventkalender)",
                "Accept": "text/calendar, application/calendar+xml, text/plain, */*",
            },
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 "
                    "Safari/537.36"
                ),
                "Accept": ("text/html,application/xhtml+xml,application/xml;"
                           "q=0.9,text/calendar,*/*;q=0.8"),
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Referer": origin,
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
                "sec-ch-ua": '"Chromium";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
            },
        ]
        last_error: Exception | None = None
        for headers in attempts:
            try:
                return self.get(self.url, headers=headers)
            except requests.HTTPError as exc:
                last_error = exc
                status = exc.response.status_code if exc.response is not None else None
                if status in (401, 403, 406, 429):
                    continue  # blocked for this UA -> try the next one
                raise
        raise last_error  # type: ignore[misc]

    def fetch_events(self) -> Iterable[Event]:
        response = self._fetch()
        calendar = Calendar.from_ical(response.content)
        events: list[Event] = []

        for component in calendar.walk("VEVENT"):
            start = _to_datetime(component.get("dtstart"))
            title = _text(component.get("summary"))
            if not start or not title:
                continue
            if self.include and not any(k in title.lower() for k in self.include):
                continue

            source_url = _text(component.get("url")) or self.url
            if self.category:
                tags = [self.category]
            elif self.party_or_workshop:
                text = (title + " " + (_text(component.get("description")) or "")).lower()
                workshop = any(w in text for w in (
                    "workshop", "rope", "shibari", "bondage", "class ", "kurs",
                    "intro", "basics", "tutorial", "skill", "lesson", "einführung",
                    "munch", "seminar", "practice", "übung",
                ))
                tags = ["Workshop"] if workshop else ["Party"]
            else:
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
