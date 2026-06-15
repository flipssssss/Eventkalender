"""Klub Verboten via Resident Advisor (ra.co) GraphQL.

The RA HTML pages return 403, but the GraphQL endpoint (ra.co/graphql) is
open. We query the promoter's events and keep only the ones in Berlin.
All events are genre Kink (set in scrapers/genres.py), category Party.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from typing import Iterable

import requests

from .base import BaseScraper, Event, parse_datetime

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
PROMOTER_ID = "84128"
CITY = "berlin"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Referer": "https://ra.co/",
    "Origin": "https://ra.co",
    "ra-content-language": "en",
}

QUERY = (
    "query($id: ID!){ promoter(id: $id){ events(type: LATEST, limit: 50){ "
    "id title date startTime endTime contentUrl flyerFront "
    "venue{ name area{ name } } } } }"
)


class KlubVerbotenScraper(BaseScraper):
    name = "Klub Verboten"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(HEADERS)
        events: list[Event] = []
        total = 0
        try:
            r = session.post(
                "https://ra.co/graphql",
                data=json.dumps({"query": QUERY, "variables": {"id": PROMOTER_ID}}),
                timeout=25,
            )
            data = (r.json().get("data") or {}).get("promoter") or {}
            for e in data.get("events") or []:
                total += 1
                ev = self._build(e)
                if ev:
                    events.append(ev)
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return events

        self._dump(f"Events gesamt: {total} | in Berlin: {len(events)}")
        return events

    def _build(self, e: dict) -> Event | None:
        venue = e.get("venue") or {}
        area = (venue.get("area") or {}).get("name") or ""
        if area.lower() != CITY:
            return None
        start = parse_datetime(e.get("startTime") or e.get("date"))
        if not start:
            return None
        start = start.replace(tzinfo=None)

        flyer = e.get("flyerFront")
        image = flyer if isinstance(flyer, str) and flyer.startswith("http") else None
        path = e.get("contentUrl") or ""
        url = ("https://ra.co" + path) if path.startswith("/") else (path or "https://ra.co")
        venue_name = venue.get("name")

        return Event(
            title=e.get("title") or "Klub Verboten",
            start=start,
            source_url=url,
            source_name=self.name,
            location=(venue_name + ", Berlin") if venue_name else "Berlin",
            image_url=image,
            tags=["Party"],
        )

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "klub-verboten.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
