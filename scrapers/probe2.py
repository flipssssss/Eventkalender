"""Targeted diagnostics for Club Sauna Berlin -- dumps structure so the real
parser can be written.
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


class Probe2Scraper(BaseScraper):
    name = "Probe2"

    def fetch_events(self) -> Iterable[Event]:
        url = "https://clubsauna.berlin/events/"
        try:
            html = requests.get(url, headers=BROWSER, timeout=25).text
        except requests.RequestException as exc:
            self._dump(f"FEHLER {exc}")
            return []
        soup = BeautifulSoup(html, "html.parser")
        low = html.lower()
        builder = next((n for n, m in (
            ("Wix", "wix.com"), ("Squarespace", "squarespace"),
            ("WordPress", "wp-content"), ("Webflow", "webflow"),
            ("Shopify", "cdn.shopify")) if m in low), "unbekannt")
        counts = {sel: len(soup.select(sel)) for sel in (
            "article", ".tribe_events", ".mec-event-article", ".eventlist-event",
            "[class*=event]", "time", "a[href*=event]", "iframe")}
        ld = [(s.string or "")[:600] for s in
              soup.find_all("script", type="application/ld+json")]
        node = (soup.select_one("article") or soup.select_one("[class*=event]"))
        sample = node.prettify()[:1500] if node else "(kein Event-Element)"
        txt = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
        self._dump(
            f"### Club Sauna ({url})\nstatus ok | len={len(html)} builder={builder} "
            f"ical_hint={'ical' in low}\nSelektoren: {counts}\n"
            f"JSON-LD-Blöcke: {len(ld)} | erste: {ld[0] if ld else '-'}\n"
            f"--- ELEMENT ---\n{sample}\n--- TEXT ---\n{txt[:600]}")
        return []

    def _dump(self, text: str) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "probe2.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
