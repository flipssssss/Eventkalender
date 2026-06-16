"""Dump the cinema + showtime markup of a berlin.de film-detail page, and find
how the 5 wanted cinemas are linked, so the real parser can be written.
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
TIME_RE = re.compile(r"\b[0-2]?\d:[0-5]\d\b")


class ProbeKinoScraper(BaseScraper):
    name = "Probe Kino"

    def fetch_events(self) -> Iterable[Event]:
        out = self._dump_filmdetail()
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "probe-kino.txt").write_text(out, encoding="utf-8")
        except OSError:
            pass
        return []

    def _dump_filmdetail(self) -> str:
        try:
            home = requests.get("https://www.berlin.de/kino/", headers=BROWSER,
                                timeout=25).text
            m = re.search(r'(/kino/_bin/filmdetail\.php/\d+/?)', home)
            url = "https://www.berlin.de" + m.group(1)
            html = requests.get(url, headers=BROWSER, timeout=25).text
        except (requests.RequestException, AttributeError) as exc:
            return f"FEHLER {exc}"
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style"]):
            t.decompose()

        # Cinema links + which match the wanted cinemas.
        cinema_links = []
        for a in soup.find_all("a", href=True):
            txt = a.get_text(" ", strip=True)
            href = a["href"]
            if "kino" in href and txt and any(w in txt.lower() for w in WANTED):
                cinema_links.append(f"{txt} -> {href}")

        # The element whose subtree holds the most showtimes -> the programme.
        best, best_n = None, 0
        for el in soup.find_all(["table", "div", "ul", "section"]):
            n = len(TIME_RE.findall(el.get_text(" ")))
            if 3 <= n and n >= best_n and len(el.find_all(True)) < 400:
                best, best_n = el, n
        sample = best.prettify()[:2600] if best else "(kein Showtime-Block)"
        return (f"URL: {url}\nWunschkino-Links:\n  " +
                "\n  ".join(cinema_links[:15] or ["(keine)"]) +
                f"\n\n--- DICHTESTER SHOWTIME-BLOCK ({best_n} Zeiten) ---\n{sample}")
