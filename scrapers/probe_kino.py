"""Inspect berlin.de/kino structure: the programme index (to find the wanted
cinemas' detail-page IDs) and a film-detail page (cinema + showtime layout).
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


class ProbeKinoScraper(BaseScraper):
    name = "Probe Kino"

    def fetch_events(self) -> Iterable[Event]:
        out = [self._index(), self._filmdetail()]
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "probe-kino.txt").write_text("\n\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []

    def _get(self, url):
        return requests.get(url, headers=BROWSER, timeout=25).text

    def _index(self) -> str:
        # The programme search lists every cinema with a kinodetail link.
        for url in ("https://www.berlin.de/kino/_bin/index.php",
                    "https://www.berlin.de/kino/spielplan/"):
            try:
                html = self._get(url)
            except requests.RequestException as exc:
                return f"### index {url}\nFEHLER {exc}"
            soup = BeautifulSoup(html, "html.parser")
            hits = []
            for a in soup.find_all("a", href=True):
                t = a.get_text(" ", strip=True).lower()
                if any(w in t for w in WANTED) and "kino" in a["href"]:
                    hits.append(f"{a.get_text(' ', strip=True)} -> {a['href']}")
            kino_links = sorted(set(re.findall(r'/kino/[\w/_.\-]*kinodetail[\w/_.\-]*',
                                               html)))[:10]
            if hits or kino_links:
                return (f"### index ({url})\nKino-Treffer:\n  " +
                        "\n  ".join(hits[:12]) +
                        f"\nkinodetail-Links: {kino_links}")
        return "### index: keine Kino-Treffer gefunden"

    def _filmdetail(self) -> str:
        # Find a film-detail link from the main page, fetch it, dump layout.
        try:
            home = self._get("https://www.berlin.de/kino/")
        except requests.RequestException as exc:
            return f"### filmdetail\nFEHLER {exc}"
        m = re.search(r'(/kino/_bin/filmdetail\.php/\d+/?)', home)
        if not m:
            return "### filmdetail: kein Link gefunden"
        url = "https://www.berlin.de" + m.group(1)
        try:
            html = self._get(url)
        except requests.RequestException as exc:
            return f"### filmdetail {url}\nFEHLER {exc}"
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style"]):
            t.decompose()
        txt = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
        classes = sorted(set(re.findall(r'class="([^"]+)"', html)))
        relevant = [c for c in classes if any(k in c for k in
                    ("kino", "spielzeit", "time", "termin", "vorstell", "showtime"))]
        return (f"### filmdetail ({url})\nrelevante Klassen: {relevant[:20]}\n"
                f"HH:MM={len(re.findall(r'[0-2]?[0-9]:[0-5][0-9]', html))}\n"
                f"TEXT: {txt[:1400]}")
