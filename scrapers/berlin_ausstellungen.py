"""berlin.de/ausstellungen -- current Berlin exhibitions.

First pass: diagnostics only. The page blocks our sandbox IP, so we dump the
fetched structure (from the GitHub Action) to design the real parser against
the actual markup. All events will be category Ausstellung, genre Kultur.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URL = "https://www.berlin.de/ausstellungen/"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


class BerlinAusstellungenScraper(BaseScraper):
    name = "Ausstellungen Berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            resp = self.get(URL, headers=BROWSER)
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        # Count candidate containers so we can spot the repeating item element.
        counts = {}
        for sel in ("article", ".teaser", ".row-list", ".list", "li.list-item",
                    "[class*=teaser]", "[class*=ausstellung]", "time",
                    "a[href*=ausstellungen]"):
            counts[sel] = len(soup.select(sel))

        # Grab the markup of a likely item for inspection.
        sample_html = ""
        candidate = (soup.select_one("[class*=teaser]") or soup.select_one("article")
                     or soup.select_one("li"))
        if candidate:
            sample_html = candidate.prettify()[:1800]

        self._dump(
            f"Status: {resp.status_code} | Länge: {len(html)} | "
            f"JSON-LD: {'application/ld+json' in html}\n"
            f"Selektor-Treffer: {counts}\n\n"
            f"--- BEISPIEL-ELEMENT ---\n{sample_html}\n\n"
            f"--- HTML (3000 Z. ab <main>/<body>) ---\n"
            f"{self._slice(html)}"
        )
        return []

    @staticmethod
    def _slice(html: str) -> str:
        m = re.search(r"<main\b", html) or re.search(r"<body\b", html)
        start = m.start() if m else 0
        return html[start:start + 3000]

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "ausstellungen.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
