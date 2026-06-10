"""A demo scraper with sample events.

This exists so the feed shows something meaningful before you have
configured any real source. It does not access the internet.

Once you have added real sources, you can remove this from the registry
in ``aggregate.py`` (or just leave it -- it is harmless).
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable

from .base import BaseScraper, Event


def _in_days(days: int, hour: int = 19) -> _dt.datetime:
    base = _dt.datetime.now().replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return base + _dt.timedelta(days=days)


class DemoScraper(BaseScraper):
    name = "Demo (Beispieldaten)"

    def fetch_events(self) -> Iterable[Event]:
        return [
            Event(
                title="Open-Air Konzert im Stadtpark",
                start=_in_days(3, 18),
                source_url="https://example.com/events/open-air-konzert",
                source_name=self.name,
                location="Stadtpark, Hauptbühne",
                description="Sommerabend mit Live-Musik regionaler Bands.",
                image_url="https://picsum.photos/seed/concert/800/450",
                tags=["Musik", "Open Air", "Familie"],
            ),
            Event(
                title="Kunstausstellung: Licht & Schatten",
                start=_in_days(7, 11),
                end=_in_days(7, 18),
                source_url="https://example.com/events/kunstausstellung",
                source_name=self.name,
                location="Städtische Galerie",
                description="Zeitgenössische Fotografie und Malerei.",
                image_url="https://picsum.photos/seed/art/800/450",
                tags=["Kunst", "Ausstellung"],
            ),
            Event(
                title="Food-Truck Festival",
                start=_in_days(12, 12),
                source_url="https://example.com/events/food-truck-festival",
                source_name=self.name,
                location="Marktplatz",
                description="Internationale Küche aus über 20 Food-Trucks.",
                image_url="https://picsum.photos/seed/food/800/450",
                tags=["Essen", "Festival", "Familie"],
            ),
            Event(
                title="Lesung & Gespräch",
                start=_in_days(20, 20),
                source_url="https://example.com/events/lesung",
                source_name=self.name,
                location="Stadtbibliothek",
                description="Autorenlesung mit anschließender Diskussion.",
                # Intentionally no image to show the fallback layout.
                tags=["Literatur", "Lesung"],
            ),
        ]
