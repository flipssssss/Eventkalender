"""Einmal-Probe: dumpt eine berlin.de-Flohmarkt-Detailseite (Mauerpark), um den
Öffnungszeiten-/Wochenrhythmus zu sehen (für die wiederkehrenden Märkte).
Liefert selbst keine Events.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

DETAIL = ("https://www.berlin.de/special/shopping/flohmaerkte/"
          "1998222-1724959-flohmarkt-am-mauerpark.html")
DEBUG = (pathlib.Path(__file__).resolve().parents[1]
         / "docs" / "data" / "_debug" / "probe-markt.txt")


class ProbeMarktScraper(BaseScraper):
    name = "Probe Markt"

    def fetch_events(self) -> Iterable[Event]:
        out: list[str] = [f"DETAIL {DETAIL}"]
        try:
            soup = BeautifulSoup(self.get(DETAIL).text, "html.parser")
        except Exception as exc:  # noqa: BLE001
            out.append(f"FEHLER: {exc}")
            self._dump(out)
            return []
        for tag in soup.select("header, footer, nav, script, style"):
            tag.decompose()
        # Zeilen mit Uhrzeiten / Wochentagen herausziehen.
        out.append("--- Zeilen mit 'Uhr' / Wochentag ---")
        wk = re.compile(r"\b(montag|dienstag|mittwoch|donnerstag|freitag|"
                        r"samstag|sonntag|täglich|wochenende|uhr)\b", re.I)
        for el in soup.find_all(["p", "td", "th", "li", "dt", "dd", "div"]):
            t = el.get_text(" ", strip=True)
            if t and wk.search(t) and len(t) < 160:
                out.append(f"<{el.name}> {t}")
        # Definition lists / Tabellen (oft die Eckdaten).
        out.append("\n--- dl/table (Eckdaten) ---")
        for box in soup.select("dl, table")[:4]:
            out.append(box.prettify()[:1200])
        self._dump(out)
        return []

    def _dump(self, lines):
        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass
