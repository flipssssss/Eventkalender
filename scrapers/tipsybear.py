"""Tipsy Bear (Berlin) -- probing scraper.

The public events page returns 403 to automated requests. Many site
builders expose alternative data endpoints (Squarespace ``?format=json``
/ ``?format=ical``, WordPress feeds, sitemaps) that are gated differently.
This scraper probes a list of candidates and records what each returns so
the real parser can be pointed at whatever works.

All events are forced onto the "Party" category.
"""

from __future__ import annotations

import pathlib
from typing import Iterable

import requests

from .base import BaseScraper, Event

BASE = "https://tipsybearberlin.com"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/json,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Referer": BASE + "/",
    "Upgrade-Insecure-Requests": "1",
}

CANDIDATES = [
    "/",
    "/events",
    "/events?format=json",
    "/events?format=ical",
    "/calendar?format=json",
    "/shows?format=json",
    "/sitemap.xml",
    "/robots.txt",
    "/events/feed/",
    "/wp-json/tribe/events/v1/events",
]


class TipsyBearScraper(BaseScraper):
    name = "Tipsy Bear"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(BROWSER_HEADERS)
        report: list[str] = []

        for path in CANDIDATES:
            url = BASE + path
            try:
                r = session.get(url, timeout=20, allow_redirects=True)
                ctype = r.headers.get("content-type", "?")
                builder = _detect_builder(r.text)
                snippet = r.text[:300].replace("\n", " ")
                report.append(
                    f"{path}\n  status={r.status_code} type={ctype} "
                    f"len={len(r.text)} builder={builder}\n  snippet={snippet}\n"
                    + "-" * 60
                )
            except Exception as exc:  # noqa: BLE001
                report.append(f"{path}\n  FEHLER: {exc}\n" + "-" * 60)

        if self.write_debug:
            self._dump_debug("\n".join(report))
        # No parser yet -- this run only gathers diagnostics.
        return []

    def _dump_debug(self, text: str) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "tipsy-bear.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass


def _detect_builder(html: str) -> str:
    low = html.lower()
    for name, marker in (
        ("Squarespace", "squarespace"),
        ("Wix", "wix.com"),
        ("Shopify", "cdn.shopify"),
        ("WordPress", "wp-content"),
        ("Webflow", "webflow"),
    ):
        if marker in low:
            return name
    return "unbekannt"
