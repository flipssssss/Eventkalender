"""Core building blocks shared by all scrapers.

If you want to add a new source, in most cases you do NOT need to touch
this file. Either:

* add the URL to ``sources.yml`` (uses the generic JSON-LD scraper), or
* write a small custom scraper class (see ``scrapers/demo.py`` for the
  smallest possible example).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import re
from dataclasses import dataclass, field
from typing import Iterable

import requests
from dateutil import parser as date_parser

# A friendly user agent so websites don't immediately block us.
USER_AGENT = (
    "EventkalenderBot/1.0 (+https://github.com/flipssssss/eventkalender) "
    "Mozilla/5.0 (compatible)"
)

REQUEST_TIMEOUT = 20  # seconds


@dataclass
class Event:
    """A single calendar event in a normalised shape.

    Only ``title``, ``start`` and ``source_url`` are really required.
    Everything else is optional and simply omitted from the feed when
    missing.
    """

    title: str
    start: _dt.datetime
    source_url: str
    source_name: str = ""
    end: _dt.datetime | None = None
    location: str | None = None
    description: str | None = None
    image_url: str | None = None
    tags: list[str] = field(default_factory=list)

    def dedupe_key(self) -> str:
        """Identify duplicate events coming from several sources."""
        day = self.start.date().isoformat() if self.start else ""
        title = re.sub(r"\s+", " ", (self.title or "").strip().lower())
        raw = f"{title}|{day}|{self.source_url}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        """Convert to the JSON structure consumed by the web feed."""
        return {
            "title": self.title.strip(),
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "location": self.location,
            "description": self.description,
            "image_url": self.image_url,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "tags": sorted({t.strip() for t in self.tags if t and t.strip()}),
        }


class BaseScraper:
    """Base class for all scrapers.

    Subclasses set ``name`` and implement :meth:`fetch_events`.
    """

    name: str = "Unbenannte Quelle"

    def fetch_events(self) -> Iterable[Event]:  # pragma: no cover - interface
        raise NotImplementedError

    # -- small helpers available to every scraper -------------------------

    def get(self, url: str, headers: dict | None = None) -> requests.Response:
        """HTTP GET with a sensible user agent and timeout.

        ``headers`` are merged on top of the defaults, so a scraper can
        override the User-Agent or Accept header when a site needs it.
        """
        merged = {"User-Agent": USER_AGENT}
        if headers:
            merged.update(headers)
        response = requests.get(url, headers=merged, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response


def parse_datetime(value) -> _dt.datetime | None:
    """Best-effort parsing of dates found on websites.

    Accepts ISO strings, common German formats and ``datetime`` objects.
    Returns ``None`` when nothing usable could be extracted.
    """
    if value is None:
        return None
    if isinstance(value, _dt.datetime):
        return value
    if isinstance(value, _dt.date):
        return _dt.datetime(value.year, value.month, value.day)
    text = str(value).strip()
    if not text:
        return None
    # ISO-8601 strings (e.g. "2026-07-03T19:30", as used by schema.org)
    # must NOT be read day-first, otherwise the month and day get swapped.
    # Only ambiguous formats like the German "03.07.2026" need dayfirst.
    iso_like = bool(re.match(r"^\d{4}-\d{2}-\d{2}", text))
    try:
        return date_parser.parse(text, dayfirst=not iso_like, fuzzy=True)
    except (ValueError, OverflowError, TypeError):
        return None
