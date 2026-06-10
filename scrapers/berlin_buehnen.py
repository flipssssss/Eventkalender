"""Scraper for berlin-buehnen.de, filtered to selected venues (Bühnen).

Status: BEST EFFORT / TO BE VERIFIED.

berlin-buehnen.de is a portal whose Spielplan listing is partly rendered
by JavaScript, so a simple HTTP request may not see the events directly.
This scraper therefore does two things on every run:

1. It tries to extract schema.org/Event data (JSON-LD) from the fetched
   pages and keeps only events at the wanted venues.
2. It writes a small diagnostics file to ``docs/data/_debug/`` describing
   what each URL returned (status, length, whether structured data was
   present, a short snippet). After the first run on GitHub, that file
   tells us exactly how to finish the parser (e.g. switch to the official
   Export API at https://www.berlin-buehnen.de/de/export-api/).

Wanted venues are matched case-insensitively against an event's location,
so "HAU" / "Hebbel am Ufer", "Maxim Gorki" and "Volksbühne" all work.
"""

from __future__ import annotations

import pathlib
from typing import Iterable

from .base import BaseScraper, Event
from .jsonld import extract_events_from_html

# Aliases so we catch the various ways a venue name can appear.
DEFAULT_VENUES = {
    "Hebbel am Ufer": ["hebbel am ufer", "hau hebbel", "hau1", "hau2", "hau3", "hau "],
    "Maxim Gorki Theater": ["maxim gorki", "gorki"],
    "Volksbühne": ["volksbühne", "volksbuehne"],
}

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"


class BerlinBuehnenScraper(BaseScraper):
    name = "Berlin Bühnen"

    def __init__(
        self,
        urls: list[str] | None = None,
        venues: dict[str, list[str]] | None = None,
        default_tags: list[str] | None = None,
        write_debug: bool = True,
    ):
        self.urls = urls or ["https://www.berlin-buehnen.de/de/spielplan/"]
        self.venues = venues or DEFAULT_VENUES
        self.default_tags = list(default_tags or ["Theater", "Berlin"])
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        events: list[Event] = []
        debug_lines: list[str] = []

        for url in self.urls:
            try:
                response = self.get(url)
                html = response.text
                found = extract_events_from_html(
                    html, base_url=url, source_name=self.name,
                    default_tags=self.default_tags,
                )
                kept = [e for e in found if self._venue_of(e)]
                for event in kept:
                    venue = self._venue_of(event)
                    if venue and venue not in event.tags:
                        event.tags.append(venue)
                events.extend(kept)
                debug_lines.append(
                    f"URL: {url}\n"
                    f"  HTTP-Status: {response.status_code}\n"
                    f"  HTML-Länge: {len(html)} Zeichen\n"
                    f"  JSON-LD vorhanden: {'application/ld+json' in html}\n"
                    f"  Events gefunden (alle): {len(found)}\n"
                    f"  Events nach Bühnen-Filter: {len(kept)}\n"
                    f"  Snippet:\n{html[:1500]}\n"
                    + "-" * 60
                )
            except Exception as exc:  # noqa: BLE001
                debug_lines.append(f"URL: {url}\n  FEHLER: {exc}\n" + "-" * 60)

        if self.write_debug:
            self._dump_debug(debug_lines)
        return events

    def _venue_of(self, event: Event) -> str | None:
        haystack = " ".join(
            filter(None, [event.location, event.title])
        ).lower()
        for canonical, aliases in self.venues.items():
            if any(alias in haystack for alias in aliases):
                return canonical
        return None

    def _dump_debug(self, lines: list[str]) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "berlin-buehnen.txt").write_text(
                "\n".join(lines), encoding="utf-8"
            )
        except OSError:
            pass
