"""tip Berlin -- probing scraper.

tip-berlin.de/event/ sits behind a "centinel-analytica"/Cloudflare bot
challenge: the first request returns a tiny interstitial that sets a
``_centinel`` cookie (printed inline) and reloads. Many such walls only
check that the cookie is present, so we read it from the response and
retry. This scraper probes that and records what the retry returns.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable

import requests

from .base import BaseScraper, Event

BASE = "https://www.tip-berlin.de/event/"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

COOKIE_RE = re.compile(r'document\.cookie\s*=\s*"([^"]+)"')


class TipBerlinScraper(BaseScraper):
    name = "tip Berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(BROWSER_HEADERS)
        report: list[str] = []

        r1 = session.get(BASE, timeout=25)
        report.append(f"1. Abruf: status={r1.status_code} len={len(r1.text)} "
                      f"jsonld={'application/ld+json' in r1.text}")

        # Set every cookie the interstitial declares via document.cookie.
        for m in COOKIE_RE.finditer(r1.text):
            decl = m.group(1)
            name_value = decl.split(";", 1)[0]
            if "=" in name_value:
                name, value = name_value.split("=", 1)
                session.cookies.set(name.strip(), value.strip(),
                                    domain=".tip-berlin.de")
                report.append(f"  Cookie gesetzt: {name.strip()}={value.strip()[:20]}…")

        r2 = session.get(BASE, timeout=25)
        report.append(f"2. Abruf: status={r2.status_code} len={len(r2.text)} "
                      f"jsonld={'application/ld+json' in r2.text}")
        report.append("  Snippet 2. Abruf:\n" + r2.text[:1500])

        if self.write_debug:
            self._dump_debug("\n".join(report))
        return []

    def _dump_debug(self, text: str) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "tip-berlin.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
