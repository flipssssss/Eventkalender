"""Café Cralle (Wedding) -- "regelmäßige Veranstaltungen" (WordPress.com).

This page lists recurring weekly events as free text. First pass only gathers
diagnostics (raw page text) so the real recurrence parser can be written
against the actual format.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URL = "https://cafecralle.wordpress.com/regelmasige-veranstaltungen/"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


class CafeCralleScraper(BaseScraper):
    name = "Café Cralle"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            resp = self.get(URL, headers=BROWSER)
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        for t in soup(["script", "style", "header", "footer", "nav", "title"]):
            t.decompose()
        # The page content lives in the main entry; fall back to whole body.
        main = soup.select_one(".entry-content, article, main") or soup
        text = re.sub(r"[ \t]+", " ", main.get_text("\n"))
        text = re.sub(r"\n\s*\n+", "\n", text).strip()

        self._dump(
            f"HTTP-Status: {resp.status_code}\nText-Länge: {len(text)}\n"
            f"JSON-LD: {'application/ld+json' in resp.text}\n\n"
            f"--- TEXT (erste 3000 Zeichen) ---\n{text[:3000]}"
        )
        # No parser yet -- diagnostics only.
        return []

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "cafe-cralle.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
