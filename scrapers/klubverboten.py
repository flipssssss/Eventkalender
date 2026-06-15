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

        # Probe candidate event queries -- RA returns helpful errors that
        # reveal the valid fields.
        ev_fields = "id title date startTime endTime contentUrl flyerFront venue{ id name area{ id name urlName } }"
        queries = {
            "LATEST": "query($id: ID!){ promoter(id: $id){ id name events(type: LATEST, limit: 12){ " + ev_fields + " } } }",
            "UPCOMING": "query($id: ID!){ promoter(id: $id){ id name events(type: UPCOMING, limit: 12){ " + ev_fields + " } } }",
        }
        for label, q in queries.items():
            try:
                r = session.post("https://ra.co/graphql",
                                 data=json.dumps({"query": q, "variables": {"id": PROMOTER_ID}}),
                                 timeout=25)
                report.append(f"\nQuery {label} -> {r.status_code}:\n{r.text[:1500]}")
            except Exception as exc:  # noqa: BLE001
                report.append(f"Query {label} FEHLER: {exc}")

        if self.write_debug:
            try:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                (DEBUG_DIR / "klub-verboten.txt").write_text("\n".join(report),
                                                             encoding="utf-8")
            except OSError:
                pass
        return []
