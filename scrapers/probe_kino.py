"""Einmal-Probe: findet die berlin.de-Kino-ID vom Klick Kino (Charlottenburg).
Liefert selbst keine Events.
"""

from __future__ import annotations

import pathlib
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URLS = [
    "https://www.berlin.de/kino/kinos/",
    "https://www.berlin.de/kino/",
    "https://www.berlin.de/kino/kinos/charlottenburg-wilmersdorf/",
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
                soup = BeautifulSoup(self.get(url).text, "html.parser")
            except Exception as exc:  # noqa: BLE001
                out.append(f"FEHLER: {exc}")
                continue
            hits = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(" ", strip=True)
                if "kinodetail" in href and ("klick" in href.lower()
                                             or "klick" in text.lower()):
                    hits.append(f"{text} -> {href}")
            out.append("Klick-Treffer: " + (", ".join(hits) or "(keine)"))
            # Fallback: alle kinodetail-Links (Name -> id) auflisten.
            all_links = [
                f"{a.get_text(' ', strip=True)} -> {a['href']}"
                for a in soup.find_all("a", href=True)
                if "kinodetail" in a["href"]
            ]
            out.append(f"kinodetail-Links gesamt: {len(all_links)}")
            out.extend(all_links[:120])
        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []
