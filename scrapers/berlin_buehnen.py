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
import re
from typing import Iterable

from bs4 import BeautifulSoup

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

    BASE = "https://www.berlin-buehnen.de"
    # Matches links to an event detail page, e.g.
    # /de/spielplan/caligula-inferno/events/368323/
    EVENT_LINK_RE = re.compile(r"/de/spielplan/[a-z0-9-]+/events/\d+/", re.I)

    def __init__(
        self,
        listing_urls: list[str] | None = None,
        venues: dict[str, list[str]] | None = None,
        default_tags: list[str] | None = None,
        max_events: int = 120,
        write_debug: bool = True,
    ):
        self.listing_urls = listing_urls or [
            "https://www.berlin-buehnen.de/de/spielplan/",
        ]
        self.venues = venues or DEFAULT_VENUES
        self.default_tags = list(default_tags or ["Theater", "Berlin"])
        self.max_events = max_events
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        debug_lines: list[str] = []

        # 1) Collect event detail links from the listing page(s).
        detail_urls = self._collect_detail_urls(debug_lines)

        # 2) Visit each detail page, read its structured data, keep the
        #    events at the wanted venues.
        events: list[Event] = []
        first_snippets = 0
        for detail_url in detail_urls[: self.max_events]:
            try:
                html = self.get(detail_url).text
                found = extract_events_from_html(
                    html, base_url=detail_url, source_name=self.name,
                    default_tags=self.default_tags,
                )
                if not found and first_snippets < 2:
                    # Detail page had no JSON-LD -- capture it so we can see
                    # how the data is structured instead.
                    first_snippets += 1
                    debug_lines.append(
                        f"DETAIL ohne JSON-LD: {detail_url}\n"
                        f"  JSON-LD vorhanden: {'application/ld+json' in html}\n"
                        f"  Snippet:\n{html[:1200]}\n" + "-" * 60
                    )
                for event in found:
                    venue = self._venue_of(event)
                    if not venue:
                        continue
                    if venue not in event.tags:
                        event.tags.append(venue)
                    events.append(event)
            except Exception as exc:  # noqa: BLE001
                debug_lines.append(f"DETAIL FEHLER {detail_url}: {exc}")

        if self.write_debug:
            debug_lines.append(self._probe_pagination(detail_urls))

        debug_lines.insert(
            0,
            f"Gefundene Event-Links: {len(detail_urls)}\n"
            f"Behaltene Events (nach Bühnen-Filter): {len(events)}\n"
            + "=" * 60,
        )
        if self.write_debug:
            self._dump_debug(debug_lines)
        return events

    def _collect_detail_urls(self, debug_lines: list[str]) -> list[str]:
        seen: list[str] = []
        for url in self.listing_urls:
            try:
                html = self.get(url).text
                paths = self.EVENT_LINK_RE.findall(html)
                for path in paths:
                    full = self.BASE + path
                    if full not in seen:
                        seen.append(full)
                debug_lines.append(
                    f"LISTING {url}: {len(paths)} Links "
                    f"({len(set(paths))} eindeutig)\n"
                    f"{self._discover_links(html)}\n"
                    f"{self._discover_endpoints(html)}\n"
                    f"{self._inspect_scripts(html)}\n" + "-" * 60
                )
            except Exception as exc:  # noqa: BLE001
                debug_lines.append(f"LISTING FEHLER {url}: {exc}\n" + "-" * 60)
        return seen

    def _probe_pagination(self, base_urls: list[str]) -> str:
        """Empirically test candidate pagination / date / venue URLs.

        The listing exposes no navigation links, so we try likely URL
        shapes and report which return a *different* set of event links.
        Whichever works tells us how to page through the full programme.
        """
        import datetime as _dt

        base_ids = {self.EVENT_LINK_RE.search(u).group(0) for u in base_urls}
        future = (_dt.date.today() + _dt.timedelta(days=40)).isoformat()
        candidates = [
            "/de/spielplan/?page=2",
            "/de/spielplan/?seite=2",
            "/de/spielplan/?p=2",
            "/de/spielplan/page/2/",
            "/de/spielplan/seite/2/",
            "/de/spielplan/?offset=24",
            "/de/spielplan/?start=24",
            "/de/spielplan/?limit=200",
            f"/de/spielplan/?date={future}",
            f"/de/spielplan/?datum={future}",
            f"/de/spielplan/?tag={future}",
            f"/de/spielplan/{future}/",
            f"/de/spielplan/?from={future}",
            "/de/spielstaetten/",
            "/de/spielplan/?spielstaette=volksbuehne",
        ]
        lines = ["  Blätter-Test (Kandidaten):"]
        for path in candidates:
            url = self.BASE + path
            try:
                html = self.get(url).text
                ids = set(self.EVENT_LINK_RE.findall(html))
                new = ids - base_ids
                lines.append(
                    f"    {path}  ->  {len(ids)} Events, {len(new)} neue"
                )
            except Exception as exc:  # noqa: BLE001
                lines.append(f"    {path}  ->  FEHLER {exc}")
        return "\n".join(lines)

    def _inspect_scripts(self, html: str) -> str:
        """Fetch the page's own JS bundles and look for the events API.

        The Spielplan is filled by a web component (project.esm.js). The
        URL it calls to load events is the key to full coverage, so we
        download those scripts and surface any endpoint-like strings.
        """
        soup = BeautifulSoup(html, "html.parser")
        srcs = [s.get("src") for s in soup.find_all("script", src=True)]
        own = [self.BASE + s if s.startswith("/") else s
               for s in srcs if s and (s.startswith("/") or self.BASE in s)]
        lines: list[str] = []
        for src in own[:4]:
            try:
                js = self.get(src).text
            except Exception as exc:  # noqa: BLE001
                lines.append(f"  Skript {src}: FEHLER {exc}")
                continue
            hits = sorted(set(re.findall(
                r"""["'`](/[a-z0-9_./-]*(?:api|event|spielplan|calendar|search|graphql|query|list)[a-z0-9_./-]*)["'`]""",
                js, flags=re.IGNORECASE,
            )))
            url_hits = sorted(set(re.findall(
                r"""(https?://[a-z0-9_.:/-]*(?:api|event|spielplan|graphql)[a-z0-9_.:/?=&-]*)""",
                js, flags=re.IGNORECASE,
            )))
            found = (hits + url_hits)[:30]
            lines.append(
                f"  Skript {src} ({len(js)} Zeichen): "
                + (", ".join(found) if found else "keine Endpunkt-Strings")
            )
        return "\n".join(lines) if lines else "  (keine eigenen Skripte)"

    def _discover_links(self, html: str) -> str:
        """Surface venue and pagination links to widen coverage later.

        The default listing only shows the nearest dates. To build a full
        calendar for the wanted venues we need their venue pages or a
        date/page parameter -- this dumps candidate internal links so the
        right ones can be added to ``listing_urls``.
        """
        soup = BeautifulSoup(html, "html.parser")
        hints = ("spielstaette", "spielstätte", "haus", "buehne", "bühne",
                 "venue", "ort", "seite", "page", "datum", "date", "/b/",
                 "hebbel", "gorki", "volksbuehne", "volksbühne", "filter")
        priority = set()
        others = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if self.EVENT_LINK_RE.search(href):
                continue
            low = href.lower()
            if not low.startswith(("/de/", "/en/", "?")):
                continue
            if any(h in low for h in hints):
                priority.add(href)
            else:
                others.add(href)
        lines = ["  Interne Links (Bühnen/Blättern bevorzugt):"]
        lines += [f"    * {c}" for c in sorted(priority)[:40]]
        lines += [f"    - {c}" for c in sorted(others)[:40]]
        return "\n".join(lines)

    def _discover_endpoints(self, html: str) -> str:
        """Look through the HTML for the data source the page uses.

        The Spielplan is rendered client-side, so the events come from an
        API or an embedded JSON blob. This surfaces likely candidates so
        the parser can be pointed at the right endpoint next.
        """
        soup = BeautifulSoup(html, "html.parser")
        lines: list[str] = []

        # Inline JSON blobs (<script type="application/json"> ...).
        json_blobs = soup.find_all("script", type=lambda t: t and "json" in t)
        for blob in json_blobs[:3]:
            text = (blob.string or blob.get_text() or "").strip()
            if text:
                lines.append(f"  JSON-Block ({blob.get('type')}):\n    {text[:600]}")

        # URLs that look like data/API endpoints anywhere in the markup.
        candidates = set(
            re.findall(
                r"""["'(]([^"'() ]*(?:api|export|spielplan|veranstalt|event|calendar|feed|ajax|\.json|\.xml)[^"'() ]*)["')]""",
                html,
                flags=re.IGNORECASE,
            )
        )
        interesting = sorted(
            c for c in candidates
            if not c.lower().endswith((".css", ".png", ".jpg", ".svg", ".woff", ".woff2", ".ico"))
        )[:25]
        if interesting:
            lines.append("  Mögliche Daten-Endpunkte:")
            lines.extend(f"    - {c}" for c in interesting)

        # External script files (the API URL is often built inside these).
        scripts = [s.get("src") for s in soup.find_all("script", src=True)]
        if scripts:
            lines.append("  Eingebundene Skripte:")
            lines.extend(f"    - {s}" for s in scripts[:15])

        return "\n".join(lines) if lines else "  (keine Endpunkt-Hinweise gefunden)"

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
