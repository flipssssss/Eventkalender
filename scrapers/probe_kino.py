"""Confirm the berlin.de cinema-detail page layout (kinodetail.php) and find
the kinodetail IDs of the 5 wanted cinemas from the cinema directory.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}
WANTED = ["sputnik", "lichtblick", "zukunft", "ladenkino", "wolf"]
DIRS = [
    "https://www.berlin.de/kino/kinos/",
    "https://www.berlin.de/kino/_bin/kinoauswahl.php",
    "https://www.berlin.de/kino/adressen/",
    "https://www.berlin.de/kino/_bin/index.php?kino=1",
]


class ProbeKinoScraper(BaseScraper):
    name = "Probe Kino"

    def _get(self, url):
        return requests.get(url, headers=BROWSER, timeout=25).text

    def fetch_events(self) -> Iterable[Event]:
        out = [self._cinema_ids(), self._cinema_layout()]
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "probe-kino.txt").write_text("\n\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []

    def _cinema_ids(self) -> str:
        found = {}
        for url in DIRS:
            try:
                soup = BeautifulSoup(self._get(url), "html.parser")
            except requests.RequestException:
                continue
            for a in soup.find_all("a", href=True):
                m = re.search(r"kinodetail\.php/(\d+)", a["href"])
                if not m:
                    continue
                name = a.get_text(" ", strip=True)
                low = name.lower()
                for w in WANTED:
                    if w in low:
                        found[w] = f"{name} -> {m.group(1)}"
            if len(found) >= 4:
                return f"### Kino-IDs (von {url})\n  " + "\n  ".join(found.values())
        return ("### Kino-IDs\n  gefunden: " + str(found) +
                "\n  (Verzeichnis-Seiten brachten zu wenig — IDs ggf. manuell)")

    def _cinema_layout(self) -> str:
        url = "https://www.berlin.de/kino/_bin/kinodetail.php/35211"  # Ladenkino
        try:
            soup = BeautifulSoup(self._get(url), "html.parser")
        except requests.RequestException as exc:
            return f"### Ladenkino-Layout\nFEHLER {exc}"
        for t in soup(["script", "style"]):
            t.decompose()
        # First film block: a heading/link to filmdetail + a Tag|Zeit table.
        tables = soup.select("table.table--compact")
        sample = ""
        if tables:
            block = tables[0].find_parent(["div", "section", "li", "article"]) or tables[0]
            sample = block.prettify()[:2200]
        film_links = [a.get_text(" ", strip=True) for a in soup.find_all("a", href=True)
                      if "filmdetail" in a["href"]][:8]
        return (f"### Ladenkino-Layout ({url})\nFilm-Tabellen: {len(tables)} | "
                f"Film-Links (erste): {film_links}\n--- ERSTER BLOCK ---\n{sample}")
