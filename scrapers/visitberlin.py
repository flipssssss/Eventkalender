"""visitBerlin -- folgt den Event-Detaillinks einer Listenseite.

Listenseiten von visitberlin.de rendern ihre Treffer clientseitig (kein
JSON-LD in der Liste), verlinken aber auf ``/de/event/<slug>``-Detailseiten,
und DIE tragen schema.org-Event-JSON-LD. Also: Links aus der Liste sammeln,
jede Detailseite lesen.

Zwei Instanzen laufen damit (siehe aggregate.py):

* ``blues-jazz``-Kategorieseite -> alles als Konzert,
* der Veranstaltungskalender, gefiltert auf die Festival-Kategorien
  -> alles als Festival. Festivals bringen aus dem JSON-LD eine endDate mit
  und laufen im Feed deshalb über ihren ganzen Zeitraum, wie Ausstellungen.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable
from urllib.parse import urljoin

from .base import BaseScraper, Event
from .jsonld import extract_events_from_html

BASE = "https://www.visitberlin.de"
JAZZ_LISTING = BASE + "/de/kategorie/blues-jazz"
# Veranstaltungskalender, gefiltert auf die beiden Festival-Kategorien
# (cat[0]=9312, cat[1]=9782). Die Adresse kommt unverändert aus der
# Filterauswahl auf der Seite -- die Zahlen sind deren Kategorie-IDs.
FESTIVAL_LISTING = (
    BASE + "/de/veranstaltungskalender-berlin"
    "?cat%5B0%5D=9312&cat%5B1%5D=9782&keys=&date_between%5Bmin%5D="
    "&date_between%5Bmax%5D=&district=All&items_per_page=21&page=1"
)
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
EVENT_LINK_RE = re.compile(r'href="(/de/event/[a-z0-9][a-z0-9\-]*)"', re.I)

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


class VisitBerlinJazzScraper(BaseScraper):
    name = "visitBerlin Jazz"

    def __init__(self, category: str = "Konzert", max_events: int = 50,
                 write_debug: bool = True, listing: str | None = None,
                 name: str | None = None, slug: str | None = None):
        self.category = category
        self.max_events = max_events
        self.write_debug = write_debug
        self.listing = listing or JAZZ_LISTING
        if name:
            self.name = name
        # Dateiname der Diagnose; Standard bleibt der bisherige.
        self.slug = slug or "visitberlin-jazz"

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(self.listing, headers=BROWSER).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER (Liste): {exc}")
            return []
        paths = list(dict.fromkeys(EVENT_LINK_RE.findall(html)))[:self.max_events]
        events: list[Event] = []
        seen: set[str] = set()
        for path in paths:
            url = urljoin(BASE, path)
            try:
                dhtml = self.get(url, headers=BROWSER).text
            except Exception:  # noqa: BLE001
                continue
            for ev in extract_events_from_html(dhtml, url, self.name):
                ev.tags = [self.category]
                ev.source_url = url
                key = url + "|" + (ev.start.isoformat() if ev.start else "")
                if key in seen:
                    continue
                seen.add(key)
                events.append(ev)
        lines = [f"Liste: {self.listing}",
                 f"Event-Links: {len(paths)} | Events: {len(events)}"]
        lines += [f"  {e.start} → {e.end} | {e.location} | {e.title}"
                  for e in events[:30]]
        if not paths:
            # Keine Detaillinks: entweder rendert die Liste jetzt anders, oder
            # der Abruf wurde abgewiesen. Beides muss hier erkennbar sein.
            lines += ["",
                      "KEINE /de/event/-LINKS IN DER LISTE.",
                      f"  HTML-Länge: {len(html)} Zeichen",
                      f"  enthält '/de/event/': {'/de/event/' in html}",
                      f"  enthält 'veranstaltung': {'veranstaltung' in html.lower()}",
                      "", "HTML-Anfang (1500 Zeichen):", html[:1500]]
        self._dump("\n".join(lines))
        return events

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / f"{self.slug}.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
