"""Generic scraper for Squarespace event collections (e.g. B-flat).

Squarespace renders its event calendar client-side, so there is no usable
JSON-LD in the page. But every Squarespace collection URL also serves its data
as JSON when ``?format=json-pretty`` is appended -- the ``items`` array holds
each event with ``startDate``/``endDate`` (ms), ``title``, ``fullUrl`` and an
image. This reads that directly.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable
from urllib.parse import urljoin

from .base import BaseScraper, Event

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/Berlin")
except Exception:  # noqa: BLE001
    _TZ = None

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/javascript,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def _strip_html(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500] or None


class SquarespaceEventsScraper(BaseScraper):
    def __init__(self, name: str, url: str, *, category: str = "Konzert",
                 address: str | None = None, write_debug: bool = True):
        self.name = name
        self.url = url
        self.category = category
        self.address = address
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        sep = "&" if "?" in self.url else "?"
        api = self.url + sep + "format=json-pretty"
        try:
            data = self.get(api, headers=BROWSER).json()
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        items = (data.get("items") or data.get("upcoming")
                 or data.get("past") or [])
        events: list[Event] = []
        for it in items:
            ev = self._build(it)
            if ev:
                events.append(ev)
        sample = items[0] if items else {}
        self._dump(
            f"top-keys: {list(data.keys())[:15]}\n"
            f"items: {len(items)} | Events: {len(events)}\n"
            f"erstes item keys: {list(sample.keys())[:25]}\n" +
            "\n".join(f"  {e.start} | {e.title}" for e in events[:30]))
        return events

    def _build(self, it: dict) -> Event | None:
        sc = it.get("structuredContent") or {}
        start_ms = it.get("startDate") or sc.get("startDate")
        end_ms = it.get("endDate") or sc.get("endDate")
        title = (it.get("title") or "").strip()
        if not isinstance(start_ms, (int, float)) or not title:
            return None
        start = self._dt(start_ms)
        end = self._dt(end_ms) if isinstance(end_ms, (int, float)) else None
        if end and end <= start:
            end = None
        href = it.get("fullUrl") or ""
        loc = it.get("location") or {}
        addr_parts = [loc.get("addressLine1"), loc.get("addressLine2")]
        address = ", ".join(p for p in addr_parts if p) or self.address
        return Event(
            title=title[:160],
            start=start,
            end=end,
            source_url=urljoin(self.url, href) if href else self.url,
            source_name=self.name,
            location=loc.get("addressTitle") or self.name,
            address=address,
            description=_strip_html(it.get("excerpt") or it.get("body")),
            image_url=it.get("assetUrl") or None,
            tags=[self.category],
        )

    @staticmethod
    def _dt(ms) -> _dt.datetime:
        epoch = ms / 1000
        if _TZ:
            return _dt.datetime.fromtimestamp(epoch, _TZ).replace(tzinfo=None)
        return _dt.datetime.utcfromtimestamp(epoch)

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-") or "squarespace"
            (DEBUG_DIR / f"{slug}.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
