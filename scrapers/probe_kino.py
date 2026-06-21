"""Einmal-Probe: findet die berlin.de-Kino-ID vom Klick Kino (Charlottenburg).
Liefert selbst keine Events.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URLS = [
    "https://www.berlin.de/kino/kinoprogramm/spielzeitenliste/",
    "https://www.berlin.de/kino/_bin/azlist.php",
    "https://www.berlin.de/kino/kinos/",
    "https://www.berlin.de/kino/",
    "https://www.berlin.de/kino/charlottenburg/",
]
DEBUG = (pathlib.Path(__file__).resolve().parents[1]
         / "docs" / "data" / "_debug" / "probe-kino.txt")


class ProbeKinoScraper(BaseScraper):
    name = "Probe Kino"

    def fetch_events(self) -> Iterable[Event]:
        out: list[str] = []
        for url in URLS:
            out.append(f"\n===== {url} =====")
            try:
                html = self.get(url).text
            except Exception as exc:  # noqa: BLE001
                out.append(f"FEHLER: {exc}")
                continue
            soup = BeautifulSoup(html, "html.parser")
            title = soup.find("title")
            out.append("title: " + (title.get_text(strip=True) if title else "?"))
            out.append("'klick' im Text: " + str("klick" in html.lower()))
            links = soup.find_all("a", href=True)
            out.append(f"Links gesamt: {len(links)}")
            # Jede Klick-Erwähnung (Text oder href).
            for a in links:
                t = a.get_text(" ", strip=True)
                if "klick" in t.lower() or "klick" in a["href"].lower():
                    out.append(f"KLICK: '{t}' -> {a['href']}")
            # Muster der Kino-Links (zur Orientierung).
            kino = [a["href"] for a in links
                    if re.search(r"kinodetail|/kino/", a["href"])]
            out.append(f"Kino-Links: {len(kino)}")
            out.extend("  " + h for h in kino[:30])
        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []
