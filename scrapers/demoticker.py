"""Demo Ticker Berlin (Mastodon) -- upcoming demonstrations.

Mastodon exposes a standard RSS feed per account, so we read
``https://todon.eu/@Demo_Ticker_Berlin.rss`` and turn each post into an event.
Posts are free text, so we extract the demo's date (and time/place) from the
text. Everything is genre Polit (set in scrapers/genres.py) and category
Protest.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

FEED_URL = "https://todon.eu/@Demo_Ticker_Berlin.rss"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}
MEDIA_NS = "http://search.yahoo.com/mrss/"

DATE_RE = re.compile(r"\b(\d{1,2})\.\s?(\d{1,2})\.(?:\s?(\d{4}))?")
TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*Uhr|\b(\d{1,2}):(\d{2})\b")
PLACE_RE = re.compile(
    r"(?:Ort|Treffpunkt|Start|Beginn|Wo)\s*:?\s*([^\n.]{3,80})", re.IGNORECASE)


def _infer_year(day: int, mon: int) -> int:
    today = _dt.date.today()
    try:
        cand = _dt.date(today.year, mon, day)
    except ValueError:
        return today.year
    return today.year + 1 if (today - cand).days > 60 else today.year


class DemoTickerScraper(BaseScraper):
    name = "Demo Ticker Berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            xml = self.get(FEED_URL, headers=BROWSER).content
            root = ET.fromstring(xml)
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []

        events: list[Event] = []
        samples: list[str] = []
        for item in root.iter("item"):
            html = (item.findtext("description") or "")
            text = BeautifulSoup(html, "html.parser").get_text("\n")
            text = re.sub(r"[ \t]+", " ", text)
            link = item.findtext("link") or FEED_URL
            image = None
            for media in item.findall(f"{{{MEDIA_NS}}}content"):
                if (media.get("medium") == "image" or
                        (media.get("type") or "").startswith("image")):
                    image = media.get("url")
                    break

            if len(samples) < 12:
                samples.append(re.sub(r"\s+", " ", text).strip()[:280])

            ev = self._build(text, link, image)
            if ev:
                events.append(ev)

        self._dump(
            f"Items: {sum(1 for _ in root.iter('item'))} | Events: {len(events)}\n\n"
            "--- POST-TEXTE ---\n" + "\n\n".join(samples)
        )
        return events

    def _build(self, text: str, link: str, image: str | None) -> Event | None:
        dm = DATE_RE.search(text)
        if not dm:
            return None
        day, mon = int(dm.group(1)), int(dm.group(2))
        if not (1 <= mon <= 12 and 1 <= day <= 31):
            return None
        year = int(dm.group(3)) if dm.group(3) else _infer_year(day, mon)

        tm = TIME_RE.search(text)
        time_known = bool(tm)
        if tm:
            hh = int(tm.group(1) or tm.group(3) or 0)
            mm = int(tm.group(2) or tm.group(4) or 0)
        else:
            hh, mm = 0, 0
        try:
            start = _dt.datetime(year, mon, day, hh, mm)
        except ValueError:
            return None

        # Title: first meaningful line; place: from a "Ort:/Treffpunkt:" hint.
        lines = [ln.strip(" •#-–—") for ln in text.split("\n") if ln.strip()]
        title = next((ln for ln in lines if len(ln) > 6), "Demo")[:140]
        place = PLACE_RE.search(text)
        location = place.group(1).strip() if place else None

        return Event(
            title=title,
            start=start,
            source_url=link,
            source_name=self.name,
            location=location,
            description=re.sub(r"\s+", " ", text).strip()[:600] or None,
            image_url=image,
            time_known=time_known,
            tags=["Protest"],
        )

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "demo-ticker.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
