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
from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from .jsonld import extract_events_from_html

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
        session = self._primed_session()
        report: list[str] = []

        wanted = ["musik+konzert", "musik+tanz", "musik+party",
                  "ausstellung+galerie", "ausstellung+kunst", "ausstellung+museen",
                  "ausstellung", "museum", "ausstellung+andere_orte"]
        report.append("Kategorie-Seiten:")
        for slug in wanted:
            try:
                r = session.get(BASE + slug + "/", timeout=25, allow_redirects=True)
                details = len(set(re.findall(
                    r"https://www\.tip-berlin\.de/event/[^/\"]+/[^/\"]+/", r.text)))
                report.append(f"  /event/{slug}/ -> {r.status_code}, "
                              f"Detail-Links={details}")
            except Exception as exc:  # noqa: BLE001
                report.append(f"  /event/{slug}/ -> FEHLER {exc}")

        # Try WordPress RSS feeds per category (clean, no detail scraping).
        report.append("\nRSS-Feeds:")
        for path in ["event/musik+konzert/feed/", "event/feed/", "feed/"]:
            try:
                r = session.get("https://www.tip-berlin.de/" + path, timeout=25)
                items = r.text.count("<item>")
                report.append(f"  /{path} -> {r.status_code} "
                              f"type={r.headers.get('content-type','?')[:30]} items={items}")
            except Exception as exc:  # noqa: BLE001
                report.append(f"  /{path} -> FEHLER {exc}")

        # Inspect a detail page: does it carry JSON-LD Event data?
        try:
            r = session.get(
                BASE + "musik-klassik/6-tischlereikonzert-quergeister-ensemblesolistinnen-und-musikerinnen-des-orchesters-der-deutschen-oper-berlin/",
                timeout=25)
            ev = extract_events_from_html(r.text, BASE, self.name)
            report.append(f"\nDetailseite: status={r.status_code} JSON-LD-Events={len(ev)}")
            for e in ev[:2]:
                report.append(f"   - {e.start} | {e.title[:40]} | {e.image_url}")
        except Exception as exc:  # noqa: BLE001
            report.append(f"Detailseite FEHLER: {exc}")

        if self.write_debug:
            self._dump_debug("\n".join(report))
        return []

    def _primed_session(self) -> requests.Session:
        session = requests.Session()
        session.headers.update(BROWSER_HEADERS)
        r1 = session.get(BASE, timeout=25)
        for m in COOKIE_RE.finditer(r1.text):
            name_value = m.group(1).split(";", 1)[0]
            if "=" in name_value:
                name, value = name_value.split("=", 1)
                session.cookies.set(name.strip(), value.strip(),
                                    domain=".tip-berlin.de")
        return session

    def _dump_debug(self, text: str) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "tip-berlin.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
