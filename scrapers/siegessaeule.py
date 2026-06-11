"""Scraper for siegessaeule.de (Berlin queer city magazine events).

The events page is a Sapper/Apollo app that embeds its data in a
``__SAPPER__`` preload script. The event objects (title, startsAt, info,
slug, image) appear as literal strings, so we read the next ``days`` days
via the ``?date=YYYY-MM-DD`` pages, pull the events out of the embedded
data and auto-categorise each one from its title/info/tags.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable

import requests

from .base import BaseScraper, Event, parse_datetime
from .categories import categorize

BASE = "https://www.siegessaeule.de/en/events/"
DETAIL = "https://www.siegessaeule.de/en/events/{slug}/"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en;q=0.9,de;q=0.8",
}

STARTS_AT_RE = re.compile(r'startsAt:"([^"]+)"')
TITLE_RE = re.compile(r'title:"((?:[^"\\]|\\.)*)"')
SLUG_RE = re.compile(r'slug:"([^"]+)"')
INFO_RE = re.compile(r'info:"((?:[^"\\]|\\.)*)"')
ENDS_AT_RE = re.compile(r'endsAt:"([^"]+)"')
IMAGE_RE = re.compile(r'url:"(https?:[^"]*?cdn\.siegessaeule\.de[^"]+)"')
TAGS_RE = re.compile(r'tags:\[([^\]]*)\]')


def _unescape(text: str) -> str:
    if text is None:
        return None
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), text)
    return text.replace('\\/', '/').replace('\\"', '"').replace("\\'", "'").strip()


class SiegessaeuleScraper(BaseScraper):
    name = "Siegessäule"

    def __init__(self, days: int = 14, write_debug: bool = True):
        self.days = days
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(BROWSER_HEADERS)
        today = _dt.date.today()
        events: list[Event] = []
        report: list[str] = []

        for offset in range(self.days):
            day = today + _dt.timedelta(days=offset)
            url = f"{BASE}?date={day.isoformat()}"
            try:
                response = session.get(url, timeout=25)
                response.encoding = "utf-8"
                found = self._parse(response.text)
            except Exception as exc:  # noqa: BLE001
                report.append(f"{day}: FEHLER {exc}")
                continue
            events.extend(found)
            report.append(f"{day}: {len(found)} Events")

        if self.write_debug:
            self._dump_debug(
                f"Tage: {self.days} | Events (vor Dedup): {len(events)}\n"
                + "\n".join(report)
            )
        return events

    # -- parsing ---------------------------------------------------------

    def _parse(self, html: str) -> list[Event]:
        script = self._sapper_script(html)
        if not script:
            return []
        region = self._events_region(script)
        events: list[Event] = []
        for obj in _top_level_objects(region):
            if "startsAt:" not in obj:
                continue  # banner ad, not an event
            event = self._event_from_obj(obj)
            if event:
                events.append(event)
        return events

    def _sapper_script(self, html: str) -> str | None:
        for match in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.DOTALL):
            text = match.group(1)
            if "eventsAndAdsForDate" in text:
                return text
        return None

    def _events_region(self, script: str) -> str:
        """The items array of eventsAndAdsForDate (the requested day's list)."""
        key = "eventsAndAdsForDate:"
        i = script.find(key)
        if i < 0:
            return script
        j = script.find("items:[", i)
        if j < 0:
            return script
        start = j + len("items:[")
        return _balanced_array(script, start)

    def _event_from_obj(self, obj: str) -> Event | None:
        starts = STARTS_AT_RE.search(obj)
        start = parse_datetime(starts.group(1)) if starts else None
        if start:
            start = start.replace(tzinfo=None)
        else:
            return None

        slug_m = SLUG_RE.search(obj)
        title_m = TITLE_RE.search(obj)
        title = _unescape(title_m.group(1)) if title_m else (
            slug_m.group(1).replace("-", " ").title() if slug_m else None
        )
        if not title:
            return None

        info = self._first(INFO_RE, obj)
        info = _unescape(info) if info else None
        ends = ENDS_AT_RE.search(obj)
        end = parse_datetime(ends.group(1)).replace(tzinfo=None) if ends else None
        image = self._first(IMAGE_RE, obj)
        image = _unescape(image) if image else None
        source_url = DETAIL.format(slug=slug_m.group(1)) if slug_m else BASE

        return Event(
            title=title,
            start=start,
            end=end,
            source_url=source_url,
            source_name=self.name,
            location=None,
            description=info,
            image_url=image,
            tags=[self._category(obj, title, info)],
        )

    @staticmethod
    def _first(pattern: re.Pattern, text: str):
        m = pattern.search(text)
        return m.group(1) if m else None

    def _category(self, obj: str, title: str, info: str | None) -> str:
        parts = [title or "", info or ""]
        tags = TAGS_RE.search(obj)
        if tags:
            for token in tags.group(1).split(","):
                token = token.strip()
                if token.startswith('"') and token.endswith('"'):
                    parts.append(_unescape(token[1:-1]))
        category = categorize([" ".join(parts)])
        # Siegessäule is mostly queer nightlife; unknowns lean to Party.
        if category == "Sonstiges":
            return "Party"
        return category or "Party"

    def _dump_debug(self, text: str) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "siegessaeule.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass


def _top_level_objects(text: str):
    """Yield each top-level {...} object string in a JS array body."""
    i, n = 0, len(text)
    while i < n:
        if text[i] == "{":
            obj = _balanced_object(text, i)
            yield obj
            i += len(obj)
        else:
            i += 1


def _balanced_object(text: str, start: int) -> str:
    depth, in_str, esc, quote = 0, False, False, ""
    i = start
    while i < len(text):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
        else:
            if ch in "\"'":
                in_str, quote = True, ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        i += 1
    return text[start:]


def _balanced_array(text: str, start: int) -> str:
    """Return the array body starting just after the opening '['."""
    depth, in_str, esc, quote = 1, False, False, ""
    i = start
    while i < len(text):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
        else:
            if ch in "\"'":
                in_str, quote = True, ch
            elif ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    return text[start:i]
        i += 1
    return text[start:]
