"""Scraper for Gancio instances (open-source DIY event calendars).

berlin.askapunk.de runs Gancio, which exposes a clean JSON API at
``/api/events``. Each event carries title, ``start_datetime`` (unix seconds),
place (name + address), media (images) and tags. We read the API directly --
no HTML scraping needed. Category is forced (e.g. Konzert); the per-event music
genre is inferred from title/tags.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
import time
from typing import Iterable

from .base import BaseScraper, Event
from .musicgenre import music_genre_for

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
    "Accept": "application/json,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


def _strip(html: str | None) -> str | None:
    if not html:
        return None
    t = re.sub(r"<[^>]+>", " ", html)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:500] or None


class GancioScraper(BaseScraper):
    def __init__(self, name: str, base_url: str, *, category: str = "Konzert",
                 horizon_days: int = 120, write_debug: bool = True):
        self.name = name
        self.base = base_url.rstrip("/")
        self.category = category
        self.horizon_days = horizon_days
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        now = int(time.time())
        end = now + self.horizon_days * 86400
        url = f"{self.base}/api/events?start={now}&end={end}&max=200"
        try:
            data = self.get(url, headers=BROWSER).json()
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        if not isinstance(data, list):
            self._dump(f"Unerwartete Antwort: {type(data)}")
            return []
        events: list[Event] = []
        for e in data:
            ev = self._build(e)
            if ev:
                events.append(ev)
        self._dump(f"API-Events: {len(data)} | übernommen: {len(events)}\n" +
                   "\n".join(f"  {e.start} | {e.music_genre} | {e.title}"
                             for e in events[:30]))
        return events

    def _build(self, e: dict) -> Event | None:
        title = (e.get("title") or "").strip()
        ts = e.get("start_datetime")
        if not title or not isinstance(ts, (int, float)):
            return None
        start = (_dt.datetime.fromtimestamp(ts, _TZ).replace(tzinfo=None)
                 if _TZ else _dt.datetime.utcfromtimestamp(ts))
        end = None
        if isinstance(e.get("end_datetime"), (int, float)):
            end = (_dt.datetime.fromtimestamp(e["end_datetime"], _TZ).replace(tzinfo=None)
                   if _TZ else _dt.datetime.utcfromtimestamp(e["end_datetime"]))
        place = e.get("place") or {}
        media = e.get("media") or []
        image = None
        if media and isinstance(media[0], dict) and media[0].get("url"):
            image = f"{self.base}/media/{media[0]['url']}"
        tags = e.get("tags") or []
        slug = e.get("slug") or ""
        mg = music_genre_for(None, " ".join([title, " ".join(
            t if isinstance(t, str) else "" for t in tags), e.get("description") or ""]))
        ev = Event(
            title=title[:160],
            start=start,
            end=end,
            source_url=f"{self.base}/event/{slug}" if slug else self.base,
            source_name=self.name,
            location=place.get("name"),
            address=place.get("address"),
            description=_strip(e.get("description")),
            image_url=image,
            tags=[self.category],
            music_genre=mg,
        )
        return ev

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-") or "gancio"
            (DEBUG_DIR / f"{slug}.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
