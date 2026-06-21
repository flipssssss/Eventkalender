"""Einmal-Probe: findet die berlin.de-kinodetail-ID vom Klick Kino aus dem
A-Z-Kino-Verzeichnis. Liefert selbst keine Events.
"""

from __future__ import annotations

import pathlib
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

AZ = "https://www.berlin.de/kino/_bin/azkino.php"
DEBUG = (pathlib.Path(__file__).resolve().parents[1]
         / "docs" / "data" / "_debug" / "probe-kino.txt")


class ProbeKinoScraper(BaseScraper):
    name = "Probe Kino"

    def fetch_events(self) -> Iterable[Event]:
        out: list[str] = [f"AZ {AZ}"]
        try:
            soup = BeautifulSoup(self.get(AZ).text, "html.parser")
        except Exception as exc:  # noqa: BLE001
            out.append(f"FEHLER: {exc}")
            self._dump(out)
            return []
        pairs = []
        for a in soup.find_all("a", href=True):
            if "kinodetail" in a["href"]:
                pairs.append((a.get_text(" ", strip=True), a["href"]))
        out.append(f"Kinos gesamt: {len(pairs)}")
        out.append("--- KLICK ---")
        for name, href in pairs:
            if "klick" in name.lower() or "klick" in href.lower():
                out.append(f"{name} -> {href}")
        out.append("--- alle (Name -> id) ---")
        out.extend(f"{n} -> {h}" for n, h in pairs)
        self._dump(out)
        return []

    def _dump(self, lines):
        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass
