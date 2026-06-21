"""Einmal-Probe: Klick-Kino-kinodetail-ID aus dem A-Z-Verzeichnis (firstchar=K).
Liefert selbst keine Events.
"""

from __future__ import annotations

import pathlib
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URL = "https://www.berlin.de/kino/_bin/azkino.php?firstchar=K"
DEBUG = (pathlib.Path(__file__).resolve().parents[1]
         / "docs" / "data" / "_debug" / "probe-kino.txt")


class ProbeKinoScraper(BaseScraper):
    name = "Probe Kino"

    def fetch_events(self) -> Iterable[Event]:
        out: list[str] = [f"URL {URL}"]
        try:
            soup = BeautifulSoup(self.get(URL).text, "html.parser")
        except Exception as exc:  # noqa: BLE001
            out.append(f"FEHLER: {exc}")
            self._dump(out)
            return []
        pairs = [(a.get_text(" ", strip=True), a["href"])
                 for a in soup.find_all("a", href=True)
                 if "kinodetail" in a["href"]]
        out.append(f"Kinos (K): {len(pairs)}")
        out.extend(f"{n} -> {h}" for n, h in pairs)
        self._dump(out)
        return []

    def _dump(self, lines):
        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass
