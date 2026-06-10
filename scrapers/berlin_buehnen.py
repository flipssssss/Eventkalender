"""Scraper for berlin-buehnen.de, filtered to selected venues (Bühnen).

The Spielplan is rendered as ``<hylo-router-link>`` cards (custom web
component elements, not plain ``<a>`` tags). Each card already carries
everything we need -- date, title, venue and image -- so we parse the
listing directly and page through it via ``?page=N`` instead of fetching
every event's detail page.

Only events at the wanted venues are kept; the venue is matched
case-insensitively, so "HAU"/"Hebbel am Ufer", "Maxim Gorki" and
"Volksbühne" all work. The specific venue is stored as the event location
(shown with a 📍); the category tag is simply "Theater".
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Event, parse_datetime

# Aliases so we catch the various ways a venue name can appear.
DEFAULT_VENUES = {
    "Hebbel am Ufer": ["hebbel am ufer", "hau hebbel", "hau1", "hau2", "hau3"],
    "Maxim Gorki Theater": ["maxim gorki", "gorki"],
    "Volksbühne": ["volksbühne", "volksbuehne"],
}

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"


class BerlinBuehnenScraper(BaseScraper):
    name = "Berlin Bühnen"

    BASE = "https://www.berlin-buehnen.de"
    EVENT_LINK_RE = re.compile(r"/de/spielplan/[a-z0-9-]+/events/\d+/", re.I)
    EVENT_ID_RE = re.compile(r"/events/(\d+)/")

    def __init__(
        self,
        venues: dict[str, list[str]] | None = None,
        max_pages: int = 60,
        write_debug: bool = True,
    ):
        self.venues = venues or DEFAULT_VENUES
        self.max_pages = max_pages
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        events: list[Event] = []
        seen_ids: set[str] = set()
        report: list[str] = []

        for page in range(1, self.max_pages + 1):
            url = f"{self.BASE}/de/spielplan/?page={page}"
            try:
                html = self.get(url).text
            except Exception as exc:  # noqa: BLE001
                report.append(f"Seite {page}: FEHLER {exc}")
                break

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.find_all("hylo-router-link", href=self.EVENT_LINK_RE)

            new_here = 0
            kept_here = 0
            for card in cards:
                event_id = self._event_id(card.get("href", ""))
                if event_id in seen_ids:
                    continue
                seen_ids.add(event_id)
                new_here += 1
                event = self._parse_card(card)
                if event:
                    events.append(event)
                    kept_here += 1

            report.append(
                f"Seite {page}: {len(cards)} Karten, {new_here} neu, "
                f"{kept_here} behalten (Wunsch-Bühnen)"
            )
            # End of programme reached (no cards or only already-seen ones).
            if not cards or new_here == 0:
                break

        if self.write_debug:
            self._dump_debug(
                [f"Behaltene Events: {len(events)} aus {len(seen_ids)} gescannten",
                 "=" * 60, *report]
            )
        return events

    # -- parsing ---------------------------------------------------------

    def _parse_card(self, card) -> Event | None:
        href = card.get("href", "")
        if not self.EVENT_LINK_RE.search(href):
            return None

        venue = self._match_venue(card.get_text(" ", strip=True))
        if not venue:
            return None

        time_el = card.find("time", attrs={"datetime": True})
        start = parse_datetime(time_el["datetime"]) if time_el else None
        if not start:
            return None

        title_el = card.find(["h3", "h2"])
        title = title_el.get_text(" ", strip=True) if title_el else None
        if not title:
            return None

        image = card.find("hylo-image", src=True)
        image_url = urljoin(self.BASE, image["src"]) if image else None

        return Event(
            title=title,
            start=start,
            source_url=urljoin(self.BASE, href),
            source_name=self.name,
            location=self._venue_display(card) or venue,
            image_url=image_url,
            tags=["Theater"],
        )

    def _match_venue(self, text: str) -> str | None:
        low = text.lower()
        for canonical, aliases in self.venues.items():
            if any(alias in low for alias in aliases):
                return canonical
        return None

    def _venue_display(self, card) -> str | None:
        """The venue name as printed on the card (e.g. 'Volksbühne Berlin')."""
        end = card.find(attrs={"slot": "end"})
        if end:
            head = end.find(["h4", "h3"])
            if head:
                span = head.find("span")
                text = (span or head).get_text(" ", strip=True)
                if text:
                    return re.sub(r"\s*\|\s*$", "", text).strip()
        return None

    # -- helpers ---------------------------------------------------------

    def _event_id(self, href: str) -> str:
        match = self.EVENT_ID_RE.search(href)
        return match.group(1) if match else href

    def _dump_debug(self, lines: list[str]) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "berlin-buehnen.txt").write_text(
                "\n".join(lines), encoding="utf-8"
            )
        except OSError:
            pass
