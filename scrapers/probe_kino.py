"""Get all cinema IDs (from the cinema switcher on a kinodetail page) and
confirm the film-title <-> showtime-table association.
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
        url = "https://www.berlin.de/kino/_bin/kinodetail.php/35211"
        try:
            html = requests.get(url, headers=BROWSER, timeout=25).text
        except requests.RequestException as exc:
            self._dump(f"FEHLER {exc}")
            return []
        soup = BeautifulSoup(html, "html.parser")

        # All cinema names + ids from <option> and kinodetail links.
        cinemas = {}
        for opt in soup.find_all("option"):
            val = (opt.get("value") or "").strip()
            name = opt.get_text(" ", strip=True)
            if val and re.fullmatch(r"\d+", val) and name:
                cinemas[name] = val
        for a in soup.find_all("a", href=True):
            m = re.search(r"kinodetail\.php/(\d+)", a["href"])
            if m:
                cinemas[a.get_text(" ", strip=True)] = m.group(1)
        wanted = {n: i for n, i in cinemas.items()
                  if any(w in n.lower() for w in WANTED)}

        # Film title <-> table association: for each compact table, the nearest
        # preceding filmdetail link.
        assoc = []
        for tbl in soup.select("table.table--compact")[:3]:
            title = "?"
            prev = tbl.find_previous(lambda t: t.name == "a" and
                                     "filmdetail" in (t.get("href") or ""))
            if prev:
                title = prev.get_text(" ", strip=True)
            row = tbl.select_one("tbody tr")
            assoc.append(f"{title} :: {row.get_text(' | ', strip=True) if row else '-'}")

        self._dump(
            f"Kinos gesamt: {len(cinemas)}\nWunschkinos: {wanted}\n\n"
            f"<option>-Beispiele: {list(cinemas.items())[:6]}\n\n"
            f"Film<->Tabelle:\n  " + "\n  ".join(assoc))
        return []

    def _dump(self, text):
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "probe-kino.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
