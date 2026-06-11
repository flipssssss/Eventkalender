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

PARAMS_RE = re.compile(r"\(function\(([\w$,]+)\)\{")
SECTION_RE = re.compile(r"section:\{slug:([^,}]+)")
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
        self._sample_slug = None

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
            probe = self._probe_detail_urls(session)
            self._dump_debug(
                f"Tage: {self.days} | Events (vor Dedup): {len(events)}\n"
                + "\n".join(report) + "\n\n" + probe
            )
        return events

    def _probe_detail_urls(self, session) -> str:
        """Find the real event-detail URL pattern by trying candidates."""
        slug = self._sample_slug
        if not slug:
            return "Sonde: kein Slug gefunden"
        patterns = [
            f"/en/events/{slug}/", f"/en/event/{slug}/", f"/events/{slug}/",
            f"/en/{slug}/", f"/termine/{slug}/", f"/en/events/{slug}",
            f"/event/{slug}/",
        ]
        lines = [f"Detail-URL-Sonde für Slug '{slug}':"]
        for p in patterns:
            try:
                rr = session.get("https://www.siegessaeule.de" + p, timeout=20,
                                 allow_redirects=True)
                lines.append(f"  {p} -> {rr.status_code} ({rr.url})")
            except Exception as exc:  # noqa: BLE001
                lines.append(f"  {p} -> FEHLER {exc}")
        return "\n".join(lines)

    # -- parsing ---------------------------------------------------------

    def _parse(self, html: str) -> list[Event]:
        script = self._sapper_script(html)
        if not script:
            return []
        refs = _resolve_refs(script)
        region = self._events_region(script)
        events: list[Event] = []
        for obj in _top_level_objects(region):
            if "startsAt:" not in obj:
                continue  # banner ad, not an event
            event = self._event_from_obj(obj, refs)
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

    def _event_from_obj(self, obj: str, refs: dict) -> Event | None:
        starts = STARTS_AT_RE.search(obj)
        start = parse_datetime(starts.group(1)) if starts else None
        if start:
            start = start.replace(tzinfo=None)
        else:
            return None

        slug_m = SLUG_RE.search(obj)
        if slug_m and not self._sample_slug:
            self._sample_slug = slug_m.group(1)
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
        # Link to the day listing (always valid); deep event links 404.
        source_url = f"{BASE}?date={start.date().isoformat()}"

        category = self._category(obj, title, info, refs)
        if category is None:
            return None  # advice/help ("Beratung") -> drop

        return Event(
            title=title,
            start=start,
            end=end,
            source_url=source_url,
            source_name=self.name,
            location=None,
            description=info,
            image_url=image,
            tags=[category],
        )

    @staticmethod
    def _first(pattern: re.Pattern, text: str):
        m = pattern.search(text)
        return m.group(1) if m else None

    def _category(self, obj: str, title: str, info: str | None, refs: dict) -> str:
        parts = [title or "", info or ""]
        # Section = Siegessäule's own bucket (party, fetisch, stage, cinema …).
        section = SECTION_RE.search(obj)
        if section:
            resolved = _resolve_value(section.group(1).strip(), refs)
            if resolved:
                parts.append(str(resolved))
        # Resolve the event's tags through the ref table.
        tags = TAGS_RE.search(obj)
        if tags:
            for token in tags.group(1).split(","):
                resolved = _resolve_value(token.strip(), refs)
                if resolved:
                    parts.append(str(resolved))
        return categorize([" ".join(parts)])

    def _dump_debug(self, text: str) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "siegessaeule.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass


def _resolve_refs(script: str) -> dict:
    """Build the variable table from the __SAPPER__ ``function(...)(...)``.

    The preload wraps its data in ``(function(a,b,...){return {...}}(v0,v1,…))``
    where the repeated values (tags, sections, venues) are passed as the
    arguments. This maps each parameter name to its literal value.
    """
    m = PARAMS_RE.search(script)
    if not m:
        return {}
    params = m.group(1).split(",")
    body_open = m.end() - 1  # index of the '{' that opens the function body
    body = _balanced_object(script, body_open)
    args_open = script.find("(", body_open + len(body))
    if args_open < 0:
        return {}
    args = _balanced_paren(script, args_open)
    values = [_lit(tok) for tok in _split_top(args)]
    return dict(zip(params, values))


def _resolve_value(token: str, refs: dict):
    token = token.strip()
    if not token:
        return None
    if token[0] in "\"'":
        return _unescape(token[1:-1])
    if token in refs:
        return refs[token]
    return None  # unknown identifier / non-literal


def _lit(token: str):
    token = token.strip()
    if token in ("true", "false"):
        return token == "true"
    if token in ("null", "void 0", "undefined"):
        return None
    if token and token[0] in "\"'":
        return _unescape(token[1:-1])
    if re.fullmatch(r"-?\d+(?:\.\d+)?", token):
        return token
    return None


def _split_top(text: str):
    """Split a comma-separated argument list, respecting strings/brackets."""
    parts, depth, in_str, esc, quote, buf = [], 0, False, False, "", []
    for ch in text:
        if in_str:
            buf.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == quote:
                in_str = False
            continue
        if ch in "\"'":
            in_str, quote = True, ch
            buf.append(ch)
        elif ch in "[{(":
            depth += 1
            buf.append(ch)
        elif ch in "]})":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return parts


def _balanced_paren(text: str, start: int) -> str:
    """Return the content inside the parenthesis group opening at ``start``."""
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
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return text[start + 1:i]
        i += 1
    return text[start + 1:]


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
