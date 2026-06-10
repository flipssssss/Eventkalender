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
from urllib.parse import urljoin

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
        # The live site uses the same Drupal markup as the (now stale 2021)
        # mirror, so the same parser works. We read the live site directly;
        # the mirror is intentionally NOT used as a fallback because its
        # snapshot is years out of date.
        self.urls = urls or [
            "https://stressfaktor.squat.net/termine",
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
        """Extract events from the Drupal ``views-row`` markup.

        Each event row contains structured fields:
          .views-field-title           -> title + link
          .views-field-field-date-time -> a <time datetime="..."> element
          .location / .locality        -> venue / place
          .views-field-body            -> description
          .views-field-field-category  -> tags
          .views-field-field-topic     -> tags
        """
        events: list[Event] = []
        for row in soup.select(".views-row"):
            event = self._row_to_event(row, base_url)
            if event:
                events.append(event)
        return events

    def _row_to_event(self, row, base_url: str) -> Event | None:
        title_el = row.select_one(".views-field-title")
        link = (title_el or row).find("a", href=True)
        title = (title_el or row).get_text(" ", strip=True) if title_el else (
            link.get_text(" ", strip=True) if link else None
        )
        if not title:
            return None

        start = self._row_date(row)
        if not start:
            return None

        href = link["href"] if link else base_url
        source_url = urljoin(base_url, href)

        location = self._first_text(
            row, ".location", ".locality", ".field--name-field-address"
        )
        description = self._first_text(row, ".views-field-body")

        tags = list(self.default_tags)
        for sel in (".views-field-field-category", ".views-field-field-topic"):
            for el in row.select(sel):
                txt = el.get_text(" ", strip=True)
                # Strip a leading field label like "Kategorie: ".
                txt = re.sub(r"^[\wäöüÄÖÜ ]{0,20}:\s*", "", txt)
                tags.extend(t.strip() for t in re.split(r"[,/]", txt) if t.strip())

        img = row.find("img")
        image_url = urljoin(base_url, img["src"]) if img and img.get("src") else None

        return Event(
            title=title,
            start=start,
            source_url=source_url,
            source_name=self.name,
            location=location,
            description=description,
            image_url=image_url,
            tags=tags,
        )

    def _row_date(self, row) -> _dt.datetime | None:
        # Drupal renders dates as <time datetime="2026-07-03T20:00:00Z">.
        time_el = row.select_one(".views-field-field-date-time time, time")
        if time_el and time_el.get("datetime"):
            dt = parse_datetime(time_el["datetime"])
            if dt:
                return dt.replace(tzinfo=None)
        # Fallbacks: the field's text, then any German date in the row.
        date_field = row.select_one(".views-field-field-date-time")
        if date_field:
            dt = parse_datetime(date_field.get_text(" ", strip=True))
            if dt:
                return dt.replace(tzinfo=None)
        match = GERMAN_DATE_RE.search(row.get_text(" ", strip=True))
        return parse_datetime(match.group(0)) if match else None

    @staticmethod
    def _first_text(row, *selectors) -> str | None:
        for sel in selectors:
            el = row.select_one(sel)
            if el:
                txt = el.get_text(" ", strip=True)
                if txt:
                    return txt
        return None

    # -- diagnostics -----------------------------------------------------

    def _diagnose(self, soup: BeautifulSoup, html: str, url: str, n: int) -> str:
        classes: dict[str, int] = {}
        for el in soup.find_all(class_=True):
            for cls in el.get("class", []):
                classes[cls] = classes.get(cls, 0) + 1
        top = sorted(classes.items(), key=lambda kv: -kv[1])[:25]
        dates = GERMAN_DATE_RE.findall(html)

        first_row = soup.select_one(".views-row")
        if first_row:
            detail = "  Erste .views-row (HTML):\n" + first_row.decode()[:3000]
        else:
            # Likely an Anubis challenge page -- dump it raw so the
            # proof-of-work solver can be built to match exactly.
            detail = "  Roh-HTML (vollständig):\n" + html[:6000]

        return (
            f"URL: {url}\n"
            f"  HTML-Länge: {len(html)} Zeichen\n"
            f"  Events geparst: {n}\n"
            f"  Datum-Treffer (Text) im HTML: {len(dates)}\n"
            f"  Häufigste CSS-Klassen: {top}\n"
            f"{detail}\n" + "-" * 60
        )

    def _dump_debug(self, lines: list[str]) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "stressfaktor.txt").write_text(
                "\n".join(lines), encoding="utf-8"
            )
        except OSError:
            pass
