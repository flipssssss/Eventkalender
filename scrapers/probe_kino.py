"""Diagnostics for the arthouse cinemas -- pick the cleanest scraping path."""

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
TARGETS = {
    "Sputnik": "https://www.sputnik-kino.com/",
    "Lichtblick": "https://lichtblick-kino.org/",
    "Zukunft": "https://kino-zukunft.de/programm.html",
    "Ladenkino": "https://ladenkino.de/",
    "Wolf": "https://wolfberlin.org/de/programm",
}
BUILDERS = [("Wix", "wix.com"), ("Squarespace", "squarespace"),
            ("WordPress", "wp-content"), ("Webflow", "webflow"),
            ("Jimdo", "jimdo"), ("Typo3", "typo3"), ("Joomla", "joomla")]


class ProbeKinoScraper(BaseScraper):
    name = "Probe Kino"

    def fetch_events(self) -> Iterable[Event]:
        out = [self._probe(n, u) for n, u in TARGETS.items()]
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "probe-kino.txt").write_text("\n\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []

    def _probe(self, name: str, url: str) -> str:
        try:
            r = requests.get(url, headers=BROWSER, timeout=25)
            html = r.text
        except requests.RequestException as exc:
            return f"### {name} ({url})\nFEHLER {exc}"
        low = html.lower()
        builder = next((n for n, m in BUILDERS if m in low), "unbekannt")
        ld_types = sorted(set(re.findall(r'"@type"\s*:\s*"([^"]+)"', html)))
        times = len(re.findall(r"\b\d{1,2}:\d{2}\b", html))
        # Detail/booking link patterns that hint at structured programmes.
        links = sorted(set(re.findall(
            r"/(?:film|movie|programm|vorstellung|screening|event)[\w\-/]{0,40}",
            low)))[:8]
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()
        return (f"### {name} ({url})\nstatus={r.status_code} len={len(html)} "
                f"builder={builder} ld+json={low.count('application/ld+json')} "
                f"HH:MM-Treffer={times}\n@type: {ld_types[:14]}\n"
                f"Link-Muster: {links}\nTEXT: {txt[:400]}")
