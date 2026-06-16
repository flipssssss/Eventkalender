"""Diagnostics for cinema aggregators (berlin.de/kino, kino.de) -- find a
film-centric source with structured showtimes for the wanted cinemas.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable

import requests

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


class ProbeKinoScraper(BaseScraper):
    name = "Probe Kino"

    def fetch_events(self) -> Iterable[Event]:
        out = []
        out.append(self._berlin_de())
        out.append(self._simple("kino.de Berlin",
                                "https://www.kino.de/kinoprogramm/stadt/berlin/"))
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "probe-kino.txt").write_text("\n\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []

    def _berlin_de(self) -> str:
        url = "https://www.berlin.de/kino/"
        try:
            html = requests.get(url, headers=BROWSER, timeout=25).text
        except requests.RequestException as exc:
            return f"### berlin.de/kino\nFEHLER {exc}"
        low = html.lower()
        types = sorted(set(re.findall(r'"@type"\s*:\s*"([^"]+)"', html)))
        # Film-detail links on berlin.de.
        film_links = sorted(set(re.findall(
            r'/kino/(?:filme|_bin|programm)?[\w\-/.]{3,60}', low)))[:10]
        # Fetch one film detail to inspect its structure.
        detail = ""
        m = re.search(r'href="(/kino/[\w\-/]+(?:\.\d+|/)?\.(?:php|html)?[^"]*)"', html)
        any_film = re.search(r'href="(https://www\.berlin\.de/kino/[^"]+)"', html)
        durl = (any_film.group(1) if any_film else None)
        if durl:
            try:
                dhtml = requests.get(durl, headers=BROWSER, timeout=25).text
                dtypes = sorted(set(re.findall(r'"@type"\s*:\s*"([^"]+)"', dhtml)))
                times = len(re.findall(r"\b\d{1,2}:\d{2}\b", dhtml))
                dtext = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", dhtml)).strip()
                detail = (f"\nDETAIL {durl}\n  @type: {dtypes[:14]} | HH:MM={times}\n"
                          f"  TEXT: {dtext[:500]}")
            except requests.RequestException as exc:
                detail = f"\nDETAIL FEHLER {exc}"
        idx_text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
        return (f"### berlin.de/kino ({url})\nlen={len(html)} "
                f"ld+json={low.count('application/ld+json')}\n@type: {types[:14]}\n"
                f"Film-Links: {film_links}\nINDEX-TEXT: {idx_text[:300]}{detail}")

    def _simple(self, name: str, url: str) -> str:
        try:
            r = requests.get(url, headers=BROWSER, timeout=25)
        except requests.RequestException as exc:
            return f"### {name}\nFEHLER {exc}"
        low = r.text.lower()
        types = sorted(set(re.findall(r'"@type"\s*:\s*"([^"]+)"', r.text)))
        return (f"### {name} ({url})\nstatus={r.status_code} len={len(r.text)} "
                f"ld+json={low.count('application/ld+json')}\n@type: {types[:14]}")
