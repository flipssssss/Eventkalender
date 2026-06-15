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

        ld = []
        for s in soup.find_all("script", type="application/ld+json"):
            ld.append((s.string or "").strip()[:1200])

        # Text of the first few article/teaser items (title + run dates + venue).
        items = soup.select("article")[:4] or soup.select(".teaser")[:4]
        item_dumps = []
        for it in items:
            txt = re.sub(r"\s+", " ", it.get_text(" ")).strip()
            link = it.find("a", href=True)
            href = link["href"] if link else "?"
            item_dumps.append(f"[{href}]\n{txt[:400]}")

        self._dump(
            f"Status: {resp.status_code} | Länge: {len(html)} | "
            f"JSON-LD-Blöcke: {len(ld)}\n\n"
            f"--- JSON-LD (gekürzt) ---\n" + "\n~~~\n".join(ld[:3]) + "\n\n"
            f"--- ARTICLE/TEASER-TEXTE ---\n" + "\n\n".join(item_dumps)
        )
        return []

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "ausstellungen.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
