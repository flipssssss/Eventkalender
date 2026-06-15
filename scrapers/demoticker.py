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

# Posts come in English + German pairs; we keep the German ones, which carry a
# clean structured line: "Wochentag, DD.MM.YYYY | HH:MM Uhr | Ort/Adresse".
HEADER_RE = re.compile(r"💥.*?💥", re.DOTALL)
DEMO_RE = re.compile(
    r"(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag),?\s*"
    r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s*\|\s*"
    r"(\d{1,2}):(\d{2})\s*Uhr\s*\|\s*"
    r"([^|]+?)\s*(?:Anreise\b|Aufruf\b|📣|$)",
    re.IGNORECASE,
)
EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿⬀-⯿️‍]")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", EMOJI_RE.sub("", text)).strip(" |•-–—#").strip()


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
        # Keep only the German posts (skip the English duplicate of each demo).
        if "Ankündigung" not in text:
            return None
        m = DEMO_RE.search(text)
        if not m:
            return None
        day, mon, year, hh, mm = (int(m.group(i)) for i in range(1, 6))
        try:
            start = _dt.datetime(year, mon, day, hh, mm)
        except ValueError:
            return None

        location = _clean(m.group(6)) or None
        # Title: the topic between the "💥…💥" header and the demo line.
        header = HEADER_RE.search(text)
        body = text[header.end():] if header else text
        title = _clean(body[:m.start() - (header.end() if header else 0)])
        title = (title or "Demo")[:140]

        return Event(
            title=title,
            start=start,
            source_url=link,
            source_name=self.name,
            location=location,
            description=_clean(text)[:600] or None,
            image_url=image,
            time_known=True,
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
