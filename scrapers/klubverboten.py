"""Klub Verboten via Resident Advisor -- probing scraper.

The RA HTML pages return 403 (Cloudflare). RA also has a GraphQL endpoint
at ra.co/graphql -- this probe checks whether it is reachable and what a
promoter-events query returns. All events would be genre Kink, Berlin only.
"""

from __future__ import annotations

import json
import pathlib
from typing import Iterable

import requests

from .base import BaseScraper, Event

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
PROMOTER_ID = "84128"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Referer": "https://ra.co/",
    "Origin": "https://ra.co",
    "ra-content-language": "en",
}


class KlubVerbotenScraper(BaseScraper):
    name = "Klub Verboten"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(HEADERS)
        report: list[str] = []

        # A simple promoter query -- mainly to see if the endpoint answers.
        query = {
            "query": "query($id: ID!){ promoter(id: $id){ id name } }",
            "variables": {"id": PROMOTER_ID},
        }
        try:
            r = session.post("https://ra.co/graphql", data=json.dumps(query), timeout=25)
            report.append(f"graphql POST -> {r.status_code} "
                          f"{r.headers.get('content-type','?')[:30]}")
            report.append("  " + r.text[:600].replace("\n", " "))
        except Exception as exc:  # noqa: BLE001
            report.append(f"graphql FEHLER: {exc}")

        # Also probe the plain pages.
        for url in [f"https://ra.co/promoters/{PROMOTER_ID}/events",
                    f"https://ra.co/promoters/{PROMOTER_ID}"]:
            try:
                rr = session.get(url, timeout=20)
                report.append(f"GET {url} -> {rr.status_code}")
            except Exception as exc:  # noqa: BLE001
                report.append(f"GET {url} -> FEHLER {exc}")

        if self.write_debug:
            try:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                (DEBUG_DIR / "klub-verboten.txt").write_text("\n".join(report),
                                                             encoding="utf-8")
            except OSError:
                pass
        return []
