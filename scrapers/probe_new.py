"""One-off probe for new sources -- gathers diagnostics only.

Fetches each candidate URL from the GitHub Action (our sandbox IP is blocked)
and records the site builder, JSON-LD presence/types, likely event-detail link
patterns and a text sample, so the real per-source scrapers can be written.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Iterable

import requests

from .base import BaseScraper, Event

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

TARGETS = {
    "König Drag Show": "https://www.konigdragshow.com/dragshows",
    "Boiler Berlin": "https://boiler-berlin.de",
    "Time to Shine Kink": "https://www.timetoshinekink.com/all-events",
    "Lab.oratory": "https://www.lab-oratory.de/",
    "Zum schmutzigen Hobby": "https://zumschmutzigenhobby.de/",
}

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

BUILDERS = [
    ("Wix", "wix.com"), ("Squarespace", "squarespace"),
    ("Shopify", "cdn.shopify"), ("WordPress", "wp-content"),
    ("Webflow", "webflow"), ("Jimdo", "jimdo"),
]


class ProbeNewScraper(BaseScraper):
    name = "Probe (neue Quellen)"

    def fetch_events(self) -> Iterable[Event]:
        out = []
        for label, url in TARGETS.items():
            out.append(self._probe(label, url))
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "probe-new.txt").write_text(
                "\n\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []

    def _probe(self, label: str, url: str) -> str:
        try:
            r = requests.get(url, headers=BROWSER, timeout=25)
        except requests.RequestException as exc:
            return f"### {label} ({url})\nFEHLER: {exc}"
        t = r.text
        low = t.lower()
        builder = next((n for n, m in BUILDERS if m in low), "unbekannt")
        ld_types = re.findall(r'"@type"\s*:\s*"([^"]+)"', t)
        detail = sorted(set(re.findall(
            r'(?:event-details|/events/|/event/|tribe_events|/tickets/)[\w\-/?=&.]{0,60}',
            t)))[:8]
        # Plain text sample.
        txt = re.sub(r"<[^>]+>", " ", t)
        txt = re.sub(r"\s+", " ", txt).strip()
        ical = "ical" in low or ".ics" in low
        return (
            f"### {label} ({url})\n"
            f"status={r.status_code} len={len(t)} builder={builder} "
            f"ld+json={low.count('application/ld+json')} ical_hint={ical}\n"
            f"@type-Werte: {sorted(set(ld_types))[:12]}\n"
            f"Detail-Link-Muster: {detail}\n"
            f"TEXT: {txt[:500]}"
        )
