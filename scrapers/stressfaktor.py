"""Scraper for the Stressfaktor event calendar (Berlin).

The original site (stressfaktor.squat.net / radar.squat.net) sits behind
an anti-bot wall, so we read the freely accessible static mirror at
mirror.systemli.org instead.

Status: BEST EFFORT / TO BE VERIFIED. The mirror's exact HTML structure
is confirmed on the first real run via the diagnostics written to
``docs/data/_debug/stressfaktor.txt``.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event, parse_datetime

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

# German weekday/month names help us spot date headings in the markup.
GERMAN_DATE_RE = re.compile(
    r"(Mo|Di|Mi|Do|Fr|Sa|So|Montag|Dienstag|Mittwoch|Donnerstag|Freitag|"
    r"Samstag|Sonntag)[\w,\. ]*?\d{1,2}\.\s*\d{1,2}\.\s*\d{2,4}",
    re.IGNORECASE,
)


class StressfaktorScraper(BaseScraper):
    name = "Stressfaktor"

    def __init__(
        self,
        urls: list[str] | None = None,
        default_tags: list[str] | None = None,
        write_debug: bool = True,
    ):
        self.urls = urls or [
            "https://mirror.systemli.org/stressfaktor.squat.net/termine/alle.html",
            "https://mirror.systemli.org/stressfaktor.squat.net/termine.html",
        ]
        self.default_tags = list(default_tags or ["Berlin", "Politik & Kultur"])
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        debug_lines: list[str] = []
        events: list[Event] = []

        for url in self.urls:
            try:
                html = self.get(url).text
            except Exception as exc:  # noqa: BLE001
                debug_lines.append(f"URL {url}: FEHLER {exc}\n" + "-" * 60)
                continue

            soup = BeautifulSoup(html, "html.parser")
            found = self._parse(soup, url)
            events.extend(found)
            debug_lines.append(self._diagnose(soup, html, url, len(found)))
            if found:
                # First working mirror is enough.
                break

        if self.write_debug:
            self._dump_debug(debug_lines)
        return events

    # -- parsing ---------------------------------------------------------

    def _parse(self, soup: BeautifulSoup, base_url: str) -> list[Event]:
        """Best-effort extraction of events from the mirror markup.

        The Drupal-based listing renders each event in a ``views-row``
        container with a date and a titled link. We try that first and
        fall back to scanning rows that contain a German date plus a link.
        """
        events: list[Event] = []
        rows = soup.select(".views-row, .event, .termin, tr.termin, li.termin")
        for row in rows:
            event = self._row_to_event(row, base_url)
            if event:
                events.append(event)
        return events

    def _row_to_event(self, row, base_url: str) -> Event | None:
        link = row.find("a", href=True)
        if not link:
            return None
        title = link.get_text(" ", strip=True)
        if not title:
            return None

        text = row.get_text(" ", strip=True)
        match = GERMAN_DATE_RE.search(text)
        start = parse_datetime(match.group(0)) if match else None
        if not start:
            return None

        href = link["href"]
        if href.startswith("/"):
            href = "https://stressfaktor.squat.net" + href

        img = row.find("img")
        image_url = img["src"] if img and img.get("src") else None
        if image_url and image_url.startswith("/"):
            image_url = "https://stressfaktor.squat.net" + image_url

        return Event(
            title=title,
            start=start,
            source_url=href,
            source_name=self.name,
            description=None,
            image_url=image_url,
            tags=list(self.default_tags),
        )

    # -- diagnostics -----------------------------------------------------

    def _diagnose(self, soup: BeautifulSoup, html: str, url: str, n: int) -> str:
        classes: dict[str, int] = {}
        for el in soup.find_all(class_=True):
            for cls in el.get("class", []):
                classes[cls] = classes.get(cls, 0) + 1
        top = sorted(classes.items(), key=lambda kv: -kv[1])[:25]
        dates = GERMAN_DATE_RE.findall(html)

        body = soup.find("body")
        snippet = (body.decode() if body else html)[:5000]

        return (
            f"URL: {url}\n"
            f"  HTML-Länge: {len(html)} Zeichen\n"
            f"  Events geparst: {n}\n"
            f"  Datum-Treffer im HTML: {len(dates)}\n"
            f"  Häufigste CSS-Klassen: {top}\n"
            f"  Body-Snippet:\n{snippet}\n" + "-" * 60
        )

    def _dump_debug(self, lines: list[str]) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "stressfaktor.txt").write_text(
                "\n".join(lines), encoding="utf-8"
            )
        except OSError:
            pass
