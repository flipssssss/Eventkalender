"""A-Trane (Jazzclub) -- liest die JSON-LD der Seite, destilliert aber einen
knappen Titel.

Das ``name``-Feld stopft Werbe-Banner, Künstler, Werk und Credits in einen
einzigen ``<br>``-Block (z. B. "A-TRANE PRÄSENTIERT SUMMERCONCERTS DAY2:<br>
JAZZ VERSUS SOCCER<br>Hanno Busch<br>«Perspective»<br>Album Release Concert<br>
Feat: …"). Der generische Ausleser macht daraus einen 150-Zeichen-Klotz. Hier
zerlegen wir den Block in Zeilen, werfen Banner-/Credits-Zeilen weg und behalten
Künstler + Werk. Reine "Heute geschlossen"-Tage fliegen ganz raus.
"""

from __future__ import annotations

import html as _html
import json
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from .jsonld import _build_event_from_node, _is_event, _iter_nodes

BASE = "https://www.a-trane.de/"
# Banner-/Promo-Zeilen, die nicht in den Titel gehören.
_BANNER = re.compile(
    r"^(a-?trane|heute|today|sonderzeit|special time|jazz versus soccer|"
    r"präsentiert|summer|feat\b)", re.I)
_CLOSED = re.compile(r"geschlossen|closed", re.I)


def _atrane_title(raw) -> str:
    text = _html.unescape(raw or "")
    lines = []
    for part in re.split(r"<br\s*/?>", text, flags=re.I):
        line = BeautifulSoup(part, "html.parser").get_text(" ")
        line = re.sub(r"\s+", " ", line).replace("­", "").strip()
        if line:
            lines.append(line)
    keep = [l for l in lines if not _BANNER.match(l)]
    if not keep:                       # nur Banner -> Originalzeilen (für Filter)
        keep = lines
    return " – ".join(keep[:3])[:140]


class ATraneScraper(BaseScraper):
    name = "A-Trane"

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(BASE).text
        except Exception:  # noqa: BLE001
            return []
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()
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
                ev = _build_event_from_node(node, BASE, self.name, ["Konzert"])
                if not ev:
                    continue
                title = _atrane_title(node.get("name"))
                if not title or _CLOSED.search(title):
                    continue            # "Heute geschlossen" o. Ä. -> kein Event
                ev.title = title
                ev.tags = ["Konzert"]   # feste Kategorie wie zuvor in sources.yml
                key = ev.source_url + "|" + ev.start.isoformat()
                if key in seen:
                    continue
                seen.add(key)
                events.append(ev)
        return events
