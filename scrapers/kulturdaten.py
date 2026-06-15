"""kulturdaten.berlin -- probing scraper (public read, no token).

Reading is open on this API (only writing needs an account). This scraper
tries a few candidate base URLs and endpoints and records what comes back,
so we can see the real structure before building the full integration.
"""

from __future__ import annotations

import json
import pathlib
from typing import Iterable

import requests

from .base import BaseScraper, Event

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

HEADERS = {
    "User-Agent": "EventkalenderBot/1.0 (+https://github.com/flipssssss/eventkalender)",
    "Accept": "application/json",
}

BASES = [
    "https://api-v2.kulturdaten.berlin",
]
PATHS = [
    "/api/docs-json",
    "/api-json",
    "/api/discover/attractions",
    "/api/discover/events",
    "/api/discover/locations",
    "/discover/attractions",
    "/api/attractions",
    "/api/events",
    "/api/locations",
]


class KulturdatenScraper(BaseScraper):
    name = "kulturdaten.berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(HEADERS)
        report: list[str] = []

        for base in BASES:
            report.append(f"=== BASE {base} ===")
            for path in PATHS:
                url = base + path
                try:
                    r = session.get(url, timeout=20)
                    ctype = r.headers.get("content-type", "?")[:40]
                    snippet = r.text[:240].replace("\n", " ")
                    report.append(f"GET {path} -> {r.status_code} {ctype}\n     {snippet}")
                    # If JSON came back, also list its top-level keys.
                    if "json" in ctype.lower() and r.status_code < 400:
                        try:
                            data = r.json()
                            if isinstance(data, dict):
                                report.append(f"     keys: {list(data.keys())}")
                                if isinstance(data.get("paths"), dict):
                                    report.append("     OpenAPI-Pfade:")
                                    for p in list(data["paths"].keys())[:60]:
                                        methods = list(data["paths"][p].keys())
                                        report.append(f"        {p}  {methods}")
                            else:
                                report.append(f"     list[{len(data)}]")
                        except Exception:
                            pass
                except Exception as exc:  # noqa: BLE001
                    report.append(f"GET {path} -> FEHLER {exc}")
            report.append("")

        if self.write_debug:
            try:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                (DEBUG_DIR / "kulturdaten.txt").write_text("\n".join(report), encoding="utf-8")
            except OSError:
                pass
        return []
