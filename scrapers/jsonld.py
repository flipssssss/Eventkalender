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


class JsonLdScraper(BaseScraper):
    """Read schema.org Events embedded in a page as JSON-LD."""

    def __init__(self, url: str, name: str | None = None, default_tags=None):
        self.url = url
        self.name = name or url
        self.default_tags = list(default_tags or [])

    def fetch_events(self) -> Iterable[Event]:
        response = self.get(self.url)
        soup = BeautifulSoup(response.text, "html.parser")
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
                event = self._build_event(node)
                if event:
                    events.append(event)
        return events

    def _build_event(self, node: dict) -> Event | None:
        title = _text(node.get("name"))
        start = parse_datetime(node.get("startDate"))
        if not title or not start:
            return None

        source_url = node.get("url") or self.url
        if isinstance(source_url, str):
            source_url = urljoin(self.url, source_url)

        tags = self.default_tags + _tags(node)

        return Event(
            title=title,
            start=start,
            end=parse_datetime(node.get("endDate")),
            source_url=source_url,
            source_name=self.name,
            location=_location(node.get("location")),
            description=_text(node.get("description")),
            image_url=_image_url(node.get("image"), self.url),
            tags=tags,
        )
