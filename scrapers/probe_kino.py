"""Einmal-Probe: findet die berlin.de-kinodetail-ID vom Klick Kino. Das
A-Z-Verzeichnis ist nach Buchstabe gefiltert -> "K"-Seite holen.
Liefert selbst keine Events.
"""

from __future__ import annotations

import pathlib
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

CANDIDATES = [
    "https://www.berlin.de/kino/_bin/azkino.php?az=K",
    "https://www.berlin.de/kino/_bin/azkino.php?az=k",
    "https://www.berlin.de/kino/_bin/azkino.php?letter=K",
    "https://www.berlin.de/kino/_bin/azkino.php/K",
]
NAV = "https://www.berlin.de/kino/_bin/azkino.php"
DEBUG = (pathlib.Path(__file__).resolve().parents[1]
         / "docs" / "data" / "_debug" / "probe-kino.txt")


class ProbeKinoScraper(BaseScraper):
    name = "Probe Kino"

    def fetch_events(self) -> Iterable[Event]:
        out: list[str] = []
        # Buchstaben-Navigation der A-Z-Seite (zur Orientierung).
        try:
            soup = BeautifulSoup(self.get(NAV).text, "html.parser")
            nav = [a["href"] for a in soup.find_all("a", href=True)
                   if "azkino" in a["href"]]
            out.append("NAV-Links (azkino): " + ", ".join(sorted(set(nav))[:30]))
        except Exception as exc:  # noqa: BLE001
            out.append(f"NAV FEHLER: {exc}")

        for url in CANDIDATES:
            out.append(f"\n===== {url} =====")
            try:
                soup = BeautifulSoup(self.get(url).text, "html.parser")
            except Exception as exc:  # noqa: BLE001
                out.append(f"FEHLER: {exc}")
                continue
            pairs = [(a.get_text(" ", strip=True), a["href"])
                     for a in soup.find_all("a", href=True)
                     if "kinodetail" in a["href"]]
            out.append(f"Kinos: {len(pairs)}")
            klick = [f"{n} -> {h}" for n, h in pairs if "klick" in n.lower()]
            out.append("KLICK: " + (", ".join(klick) or "(keine)"))
            out.extend(f"  {n} -> {h}" for n, h in pairs[:25])
            if klick:
                break
        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []
