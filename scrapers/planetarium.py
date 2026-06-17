"""Planetarium Berlin -- Drupal event listing (per category).

The Stiftung Planetarium Berlin site is Drupal; the /tickets page is a JS
widget, but the taxonomy pages under /veranstaltungsart/<art> are
server-rendered. We read just the two wanted categories (Konzerte,
Hörspiele & Lesungen). Drupal renders dates as ``<time datetime="...">`` --
we walk from each time element to its teaser and pull title + link. The raw
teaser is dumped to the debug file so the parser can be refined if needed.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Event, parse_datetime

BASE = "https://www.planetarium.berlin"
SECTIONS = [
    ("/veranstaltungsart/highlights-konzerte", "Konzert"),
    ("/veranstaltungsart/hoerspiele-lesungen", "Vortrag"),
]
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


class PlanetariumScraper(BaseScraper):
    name = "Planetarium Berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        events: list[Event] = []
        seen: set[str] = set()
        dump: list[str] = []
        for path, category in SECTIONS:
            url = BASE + path
            try:
                html = self.get(url, headers=BROWSER).text
            except Exception as exc:  # noqa: BLE001
                dump.append(f"{path}: FEHLER {exc}")
                continue
            soup = BeautifulSoup(html, "html.parser")
            times = soup.select("time[datetime]")
            n = 0
            first_card = None
            for t in times:
                card = self._teaser(t)
                ev = self._build(t, card, category)
                if ev and ev._k not in seen:
                    seen.add(ev._k)
                    events.append(ev)
                    n += 1
                if first_card is None and card is not None:
                    first_card = card
            dump.append(f"{path} ({category}): time-Elemente={len(times)} -> {n}\n"
                        + (first_card.prettify()[:1100] if first_card else "(kein Teaser)"))
        self._dump(f"Events: {len(events)}\n\n" + "\n\n----\n".join(dump))
        return events

    @staticmethod
    def _teaser(time_el):
        node = time_el
        for _ in range(6):
            node = node.parent
            if node is None:
                return None
            cls = " ".join(node.get("class", []))
            if node.name in ("article",) or re.search(
                    r"teaser|node|views-row|card|event", cls, re.I):
                return node
        return time_el.parent

    def _build(self, time_el, card, category) -> Event | None:
        start = parse_datetime(time_el.get("datetime"))
        if not start or card is None:
            return None
        link = card.find("a", href=True)
        head = card.find(["h1", "h2", "h3", "h4"])
        title = ""
        if head:
            title = head.get_text(" ", strip=True)
        if not title and link:
            title = link.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            return None
        href = urljoin(BASE, link["href"]) if link else BASE + "/veranstaltungen"
        img = card.find("img", src=True)
        ev = Event(
            title=title[:160],
            start=start.replace(tzinfo=None),
            source_url=href,
            source_name=self.name,
            location="Planetarium Berlin",
            image_url=urljoin(BASE, img["src"]) if img else None,
            tags=[category],
        )
        ev._k = href + "|" + start.isoformat()
        return ev

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "planetarium-berlin.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
