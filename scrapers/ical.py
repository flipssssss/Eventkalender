"""Generic scraper for iCalendar (.ics) feeds.

iCalendar is a strict, widely used standard, so parsing an ``.ics`` feed
is far more reliable than scraping HTML. Many event platforms expose one
-- for example radar.squat.net offers a feed per group at
``https://radar.squat.net/ical/node/<id>``.

Configure an iCal source in ``sources.yml`` with ``type: ical``.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable
from urllib.parse import urlsplit

import requests
from icalendar import Calendar

from .base import BaseScraper, Event

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"


def _looks_like_ical(body: bytes) -> bool:
    """True when the payload really is an iCalendar document."""
    return b"BEGIN:VCALENDAR" in (body or b"")[:4096].upper()


def _ical_candidates(url: str) -> list[str]:
    """The feed URL plus known-good variants for the same site.

    "The Events Calendar" (WordPress) serves its feed under several shapes and
    silently returns an EMPTY body for the wrong one -- which surfaces as the
    cryptic "Found no components where exactly one is required: b''". The
    query-string form below is the one that demonstrably works for the other
    Events-Calendar sources in this repo, so it is always worth a second try.
    """
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}/"
    variants = [
        url,
        f"{origin}?post_type=tribe_events&ical=1&eventDisplay=list",
        f"{origin}events/?ical=1&eventDisplay=list",
    ]
    seen, out = set(), []
    for candidate in variants:
        if candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


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

    def _fetch(self, url: str | None = None) -> requests.Response:
        """Fetch the feed, trying a plain feed UA then a browser UA.

        A non-"Mozilla" user agent gets past bot walls like Anubis (which only
        challenge browser-like requests). Some sites do the opposite and block
        non-browser agents (403) -- for those we retry looking like a browser.
        """
        url = url or self.url
        origin = "{0.scheme}://{0.netloc}/".format(urlsplit(url))
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
                return self.get(url, headers=headers)
            except requests.HTTPError as exc:
                last_error = exc
                status = exc.response.status_code if exc.response is not None else None
                if status in (401, 403, 406, 429):
                    continue  # blocked for this UA -> try the next one
                raise
        raise last_error  # type: ignore[misc]

    def _load_calendar(self) -> tuple[Calendar, str]:
        """Fetch the feed and return the parsed calendar plus the URL used.

        Tries the configured URL first, then the known variants. An empty or
        non-iCal body is treated as a miss (not a hard error), so a site that
        moved its feed is recovered instead of silently reporting zero events.
        """
        notes: list[str] = []
        for candidate in _ical_candidates(self.url):
            try:
                response = self._fetch(candidate)
            except Exception as exc:  # noqa: BLE001 - try the next candidate
                notes.append(f"{candidate} -> FEHLER {type(exc).__name__}: {exc}")
                continue
            body = response.content or b""
            if not _looks_like_ical(body):
                head = body[:120].decode("utf-8", "replace").replace("\n", " ")
                notes.append(
                    f"{candidate} -> HTTP {response.status_code}, "
                    f"{len(body)} Bytes, kein VCALENDAR "
                    f"(Anfang: {head!r})")
                continue
            try:
                calendar = Calendar.from_ical(body)
            except Exception as exc:  # noqa: BLE001 - malformed feed
                notes.append(f"{candidate} -> unlesbar: {exc}")
                continue
            if notes:
                notes.append(f"{candidate} -> OK ({len(body)} Bytes)")
                self._dump(notes)
            return calendar, candidate
        self._dump(notes)
        raise RuntimeError(
            "Kein brauchbarer iCal-Feed erreichbar. Versuche:\n  "
            + "\n  ".join(notes))

    def _dump(self, notes: list[str]) -> None:
        """Write the per-URL diagnosis so a broken feed is debuggable."""
        if not notes:
            return
        slug = re.sub(r"[^a-z0-9]+", "-", (self.name or "ical").lower()).strip("-")
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / f"ical-{slug or 'feed'}.txt").write_text(
                "iCal-Abruf\n\n" + "\n".join(notes) + "\n", encoding="utf-8")
        except OSError:
            pass

    def fetch_events(self) -> Iterable[Event]:
        calendar, _used_url = self._load_calendar()
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
