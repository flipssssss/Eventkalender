"""Generic scraper for the schema.org/Event standard (JSON-LD).

Many event, venue and city websites embed their events as structured
``<script type="application/ld+json">`` data so that Google can show them
in search results. This scraper reads exactly that data, which means a
large number of sites work WITHOUT any custom code -- you only add their
URL to ``sources.yml``.

If a website returns no events here, it probably does not expose JSON-LD
and needs a small custom scraper instead.
"""

from __future__ import annotations

import json
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Event, parse_datetime


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _first(value):
    items = _as_list(value)
    return items[0] if items else None


def _text(value) -> str | None:
    """Pull a readable string out of the many shapes schema.org allows."""
    value = _first(value)
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        for key in ("name", "@value", "text", "url"):
            if value.get(key):
                return str(value[key]).strip()
    return str(value).strip() or None


def _image_url(value, base_url: str) -> str | None:
    value = _first(value)
    if isinstance(value, dict):
        value = value.get("url") or value.get("contentUrl")
    if isinstance(value, str) and value.strip():
        return urljoin(base_url, value.strip())
    return None


def _location(value) -> str | None:
    value = _first(value)
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict):
        name = value.get("name")
        address = value.get("address")
        if isinstance(address, dict):
            parts = [
                address.get("streetAddress"),
                address.get("postalCode"),
                address.get("addressLocality"),
            ]
            address = ", ".join(p for p in parts if p)
        bits = [b for b in (name, address) if b]
        return ", ".join(bits) or None
    return None


def _tags(node) -> list[str]:
    tags: list[str] = []
    for key in ("keywords", "genre"):
        raw = node.get(key)
        if isinstance(raw, str):
            tags.extend(part.strip() for part in raw.split(","))
        else:
            tags.extend(str(t).strip() for t in _as_list(raw))
    category = node.get("eventType") or node.get("@type")
    if isinstance(category, str) and category not in ("Event",):
        tags.append(category)
    return [t for t in tags if t]


def _iter_nodes(data):
    """Yield every dict inside an arbitrarily nested JSON-LD document."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)
    elif isinstance(data, dict):
        if "@graph" in data:
            yield from _iter_nodes(data["@graph"])
        yield data


def _is_event(node: dict) -> bool:
    types = _as_list(node.get("@type"))
    return any(isinstance(t, str) and "Event" in t for t in types)


def extract_events_from_html(
    html: str,
    base_url: str,
    source_name: str,
    default_tags=None,
) -> list[Event]:
    """Pull all schema.org Events out of a raw HTML string.

    Shared by :class:`JsonLdScraper` and other scrapers that already have
    the page HTML in hand.
    """
    soup = BeautifulSoup(html, "html.parser")
    default_tags = list(default_tags or [])
    events: list[Event] = []

    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _iter_nodes(data):
            if not _is_event(node):
                continue
            event = _build_event_from_node(node, base_url, source_name, default_tags)
            if event:
                events.append(event)
    return events


def _build_event_from_node(node, base_url, source_name, default_tags) -> Event | None:
    title = _text(node.get("name"))
    start = parse_datetime(node.get("startDate"))
    if not title or not start:
        return None

    source_url = node.get("url") or base_url
    if isinstance(source_url, str):
        source_url = urljoin(base_url, source_url)

    return Event(
        title=title,
        start=start,
        end=parse_datetime(node.get("endDate")),
        source_url=source_url,
        source_name=source_name,
        location=_location(node.get("location")),
        description=_text(node.get("description")),
        image_url=_image_url(node.get("image"), base_url),
        tags=list(default_tags) + _tags(node),
    )


class JsonLdScraper(BaseScraper):
    """Read schema.org Events embedded in a page as JSON-LD.

    ``category`` forces every event onto a single fixed tag (e.g. all
    Donau115 events -> "Konzert"), ignoring whatever keywords the page
    declares. ``extra_urls`` lets a source list several pages to read.
    """

    def __init__(
        self,
        url: str,
        name: str | None = None,
        default_tags=None,
        category: str | None = None,
        extra_urls=None,
        write_debug: bool = True,
    ):
        self.url = url
        self.name = name or url
        self.default_tags = list(default_tags or [])
        self.category = category
        self.extra_urls = list(extra_urls or [])
        self.write_debug = write_debug

    # Full browser-like headers so WAFs (Cloudflare etc.) don't return 403.
    BROWSER_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }

    def fetch_events(self) -> Iterable[Event]:
        events: list[Event] = []
        debug_lines: list[str] = []
        for url in [self.url, *self.extra_urls]:
            try:
                response = self.get(url, headers=self.BROWSER_HEADERS)
            except Exception as exc:  # noqa: BLE001
                debug_lines.append(f"URL: {url}\n  FEHLER: {exc}\n" + "-" * 60)
                continue
            found = extract_events_from_html(
                response.text,
                base_url=url,
                source_name=self.name,
                default_tags=self.default_tags,
            )
            events.extend(found)
            debug_lines.append(
                f"URL: {url}\n"
                f"  HTTP-Status: {response.status_code}\n"
                f"  HTML-Länge: {len(response.text)} Zeichen\n"
                f"  JSON-LD vorhanden: {'application/ld+json' in response.text}\n"
                f"  Events gefunden: {len(found)}\n"
                f"{self._discover_links(response.text, url)}\n"
                f"{self._discover_scripts(response.text)}\n"
                f"  Body (ohne CSS/JS):\n{self._body_snippet(response.text, 2500)}\n"
                + "-" * 60
            )

        if self.category:
            for event in events:
                event.tags = [self.category]

        if self.write_debug:
            self._dump_debug(debug_lines)
        return events

    def _discover_scripts(self, html: str) -> str:
        """Find the data endpoint a JS-rendered page fetches its events from."""
        import re as _re

        soup = BeautifulSoup(html, "html.parser")
        # External script files.
        ext = [s.get("src") for s in soup.find_all("script", src=True)]
        # Inline script text.
        inline = "\n".join(
            s.string or s.get_text() or "" for s in soup.find_all("script", src=False)
        )
        urls = sorted(set(_re.findall(
            r"""["'`]([^"'`]*(?:https?://[^"'`]+|/[^"'`]*(?:api|event|json|calendar|feed|sheet|data)[^"'`]*))["'`]""",
            inline, flags=_re.IGNORECASE,
        )))
        fetches = sorted(set(_re.findall(
            r"""fetch\(\s*[`'"]([^`'"]+)[`'"]""", inline, flags=_re.IGNORECASE
        )))
        lines = []
        if fetches:
            lines.append("  fetch()-Aufrufe: " + ", ".join(fetches[:10]))
        if urls:
            lines.append("  URL-Strings im Skript: " + ", ".join(urls[:15]))
        if ext:
            lines.append("  Externe Skripte: " + ", ".join(s for s in ext if s)[:400])
        return "\n".join(lines) if lines else "  (keine Skript-Endpunkte gefunden)"

    def _body_snippet(self, html: str, limit: int = 6000) -> str:
        import re as _re

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["style", "script", "head", "svg", "noscript"]):
            tag.decompose()
        body = soup.body or soup
        decoded = _re.sub(r"\n\s*\n+", "\n", body.decode())
        # Start at the first <time> (where event listings usually begin) so
        # the header/nav don't eat the whole snippet.
        idx = decoded.find("<time")
        start = max(0, idx - 400) if idx > 0 else 0
        return decoded[start:start + limit]

    def _discover_links(self, html: str, base_url: str) -> str:
        """Surface likely programme/event subpages to read instead."""
        soup = BeautifulSoup(html, "html.parser")
        hints = ("programm", "konzert", "event", "termin", "kalender",
                 "spielplan", "veranstalt", "shows", "tickets", "calendar")
        found = set()
        for a in soup.find_all("a", href=True):
            low = a["href"].lower()
            if any(h in low for h in hints):
                found.add(urljoin(base_url, a["href"]))
        listed = sorted(found)[:25]
        if not listed:
            return "  (keine Programm-/Event-Unterseiten erkannt)"
        return "  Mögliche Programm-Unterseiten:\n" + "\n".join(
            f"    - {u}" for u in listed
        )

    def _dump_debug(self, lines: list[str]) -> None:
        import pathlib
        import re

        debug_dir = (
            pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
        )
        slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-") or "jsonld"
        try:
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / f"{slug}.txt").write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass
