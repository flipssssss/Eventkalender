"""Targeted diagnostics for Time to Shine (Squarespace HTML) and König Drag
Show (Google Sites). Dumps structure so the real parsers can be written.
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
        out = [self._timetoshine(), self._koenig()]
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "probe2.txt").write_text("\n\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []

    def _timetoshine(self) -> str:
        url = "https://www.timetoshinekink.com/all-events"
        try:
            html = requests.get(url, headers=BROWSER, timeout=25).text
        except requests.RequestException as exc:
            return f"### Time to Shine\nFEHLER {exc}"
        soup = BeautifulSoup(html, "html.parser")
        counts = {sel: len(soup.select(sel)) for sel in (
            ".eventlist-event", ".summary-item", ".eventlist-title",
            "iframe", "a[href*=eventbrite]", "a[href*=tickettailor]",
            "time", "[class*=event]")}
        iframes = [i.get("src") for i in soup.select("iframe") if i.get("src")][:5]
        ext = sorted(set(re.findall(
            r'https?://[\w.\-]*(?:eventbrite|tickettailor|ra\.co|fienta|'
            r'ticket|dice\.fm)[\w./\-?=&]*', html)))[:6]
        node = (soup.select_one(".eventlist-event")
                or soup.select_one(".summary-item"))
        sample = node.prettify()[:1200] if node else "(keine Event-Items)"
        return (f"### Time to Shine ({url})\nSelektoren: {counts}\n"
                f"iframes: {iframes}\nExterne Ticket-Links: {ext}\n"
                f"--- ITEM ---\n{sample}")

    def _koenig(self) -> str:
        url = "https://www.konigdragshow.com/dragshows"
        try:
            html = requests.get(url, headers=BROWSER, timeout=25).text
        except requests.RequestException as exc:
            return f"### König\nFEHLER {exc}"
        # Google Sites embeds visible text as quoted string literals.
        strings = re.findall(r'"((?:[^"\\]|\\.){12,})"', html)
        decoded = []
        for s in strings:
            try:
                t = s.encode().decode("unicode_escape")
            except Exception:  # noqa: BLE001
                t = s
            if re.search(r"[A-Za-zÄÖÜ]", t) and "http" not in t and "/" not in t[:4]:
                decoded.append(t.strip())
        # Keep ones that look like show listings (date or show words).
        interesting = [t for t in decoded if re.search(
            r"\d{1,2}[./]\d{1,2}|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|"
            r"Nov|Dec|drag|show|doors|tickets|Uhr)\b", t, re.IGNORECASE)]
        seen, uniq = set(), []
        for t in interesting:
            if t not in seen and len(t) < 300:
                seen.add(t)
                uniq.append(t)
        return (f"### König ({url})\nLange Strings: {len(decoded)} | "
                f"interessant: {len(uniq)}\n--- TEXTSCHNIPSEL ---\n"
                + "\n".join(uniq[:40]))
