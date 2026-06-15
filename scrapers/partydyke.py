"""Party Dyke Berlin (queere/lesbische Partys) -- Wix-Events-Seite.

The ``/event-list`` page is a Wix app that renders client-side, so it has no
JSON-LD and no event data in the initial HTML. It does, however, link to each
event's detail page (``/event-details/<slug>``), and those Wix detail pages
embed a schema.org ``Event`` as JSON-LD. So we collect the slugs from the list
page and read each detail page's structured data.

All events are genre ``Queer`` (set in scrapers/genres.py) and category Party.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Iterable

import requests

from .base import BaseScraper, Event, parse_datetime

LIST_URL = "https://www.partydykeberlin.com/event-list"
DETAIL = "https://www.partydykeberlin.com/event-details/{slug}"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

SLUG_RE = re.compile(r"event-details/([a-zA-Z0-9\-]+)")
MAX_DETAILS = 40


class PartyDykeScraper(BaseScraper):
    name = "Party Dyke Berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(BROWSER)
        events: list[Event] = []
        report: list[str] = []
        sample = ""

        try:
            html = session.get(LIST_URL, timeout=25).text
        except requests.RequestException as exc:
            self._dump(f"Listenseite FEHLER: {exc}")
            return events

        slugs = list(dict.fromkeys(SLUG_RE.findall(html)))[:MAX_DETAILS]
        report.append(f"Listenseite: {len(slugs)} Event-Slugs gefunden")

        for slug in slugs:
            try:
                page = session.get(DETAIL.format(slug=slug), timeout=25).text
            except requests.RequestException as exc:
                report.append(f"  {slug}: FEHLER {exc}")
                continue
            data = _event_jsonld(page)
            if not sample:
                sample = self._diag(page, data)
            ev = self._build(data, slug)
            if ev:
                events.append(ev)

        report.append(f"Events gebaut: {len(events)}")
        self._dump("\n".join(report) + "\n\n--- DIAGNOSE 1. Detailseite ---\n" + sample)
        return events

    def _build(self, data: dict | None, slug: str) -> Event | None:
        if not data:
            return None
        start = parse_datetime(data.get("startDate"))
        if not start:
            return None
        start = start.replace(tzinfo=None)
        end = parse_datetime(data.get("endDate"))
        end = end.replace(tzinfo=None) if end else None

        loc = data.get("location") or {}
        if isinstance(loc, list):
            loc = loc[0] if loc else {}
        name = loc.get("name") if isinstance(loc, dict) else None
        # Wix placeholder for an unset venue -> treat as no location.
        if name and name.strip().lower() in ("location is tbd", "tbd", "tba"):
            name = None
        address = _format_address(loc.get("address")) if isinstance(loc, dict) else None

        image = data.get("image")
        if isinstance(image, list):
            image = image[0] if image else None
        if isinstance(image, dict):
            image = image.get("url")

        return Event(
            title=(data.get("name") or slug.replace("-", " ").title())[:140],
            start=start,
            end=end,
            source_url=data.get("url") or DETAIL.format(slug=slug),
            source_name=self.name,
            location=name,
            address=address,
            description=(data.get("description") or None),
            image_url=image if isinstance(image, str) else None,
            tags=["Party"],
        )

    def _diag(self, page: str, data: dict | None) -> str:
        has_ld = "application/ld+json" in page
        warmup = "wix-warmup-data" in page
        keys = sorted(data.keys()) if isinstance(data, dict) else "(kein Event)"
        return (f"JSON-LD im HTML: {has_ld} | wix-warmup-data: {warmup}\n"
                f"Event-Felder: {keys}")

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "party-dyke-berlin.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass


def _event_jsonld(html: str) -> dict | None:
    """Return the first schema.org Event object found in the page."""
    for m in re.finditer(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL,
    ):
        try:
            data = json.loads(m.group(1).strip())
        except ValueError:
            continue
        for obj in _iter_objects(data):
            t = obj.get("@type")
            types = t if isinstance(t, list) else [t]
            if any(isinstance(x, str) and "Event" in x for x in types):
                return obj
    return None


def _iter_objects(data):
    if isinstance(data, dict):
        if "@graph" in data and isinstance(data["@graph"], list):
            yield from data["@graph"]
        yield data
    elif isinstance(data, list):
        for item in data:
            yield from _iter_objects(item)


def _format_address(addr) -> str | None:
    if isinstance(addr, str):
        return addr or None
    if not isinstance(addr, dict):
        return None
    parts = [
        addr.get("streetAddress"),
        " ".join(filter(None, [addr.get("postalCode"), addr.get("addressLocality")])),
    ]
    return ", ".join(p for p in parts if p) or None
