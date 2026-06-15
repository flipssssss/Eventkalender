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

    BASE = "https://api-v2.kulturdaten.berlin"

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(HEADERS)
        report: list[str] = []

        def get(path):
            return session.get(self.BASE + path, timeout=25)

        # 1) Full sample objects to understand the structure.
        for res in ["events", "attractions", "locations"]:
            try:
                data = get(f"/api/{res}?page=1&pageSize=1").json().get("data", {})
                items = data.get(res) or []
                report.append(f"=== {res}: totalCount={data.get('totalCount')} ===")
                if items:
                    report.append(json.dumps(items[0], ensure_ascii=False)[:2200])
            except Exception as exc:  # noqa: BLE001
                report.append(f"{res}: FEHLER {exc}")
            report.append("")

        # 2) Date-filter / include candidates on /api/events.
        report.append("=== Query-Tests /api/events ===")
        for q in [
            "?page=1&pageSize=2",
            "?anyDate=true",
            "?startDate=2026-06-16",
            "?filter[schedule.startDate]=2026-06-16",
            "?include=attractions,locations",
            "?expand=attractions",
            "?pageSize=2&include=attractions",
        ]:
            try:
                r = get("/api/events" + q)
                snip = r.text[:200].replace("\n", " ")
                report.append(f"{q} -> {r.status_code}: {snip}")
            except Exception as exc:  # noqa: BLE001
                report.append(f"{q} -> FEHLER {exc}")
        report.append("")

        # 3) Try to fetch the OpenAPI spec (documents all query params).
        report.append("=== OpenAPI-Spec ===")
        for p in ["/api/docs/swagger.json", "/api/docs/json", "/api/openapi.json",
                  "/api/docs-json/", "/api/docs/?format=json"]:
            try:
                r = get(p)
                report.append(f"{p} -> {r.status_code} {r.headers.get('content-type','?')[:30]}")
                if r.status_code < 400 and "json" in r.headers.get("content-type", ""):
                    data = r.json()
                    if isinstance(data, dict) and isinstance(data.get("paths"), dict):
                        report.append("  Pfade: " + ", ".join(list(data["paths"].keys())[:40]))
            except Exception as exc:  # noqa: BLE001
                report.append(f"{p} -> FEHLER {exc}")

        if self.write_debug:
            try:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                (DEBUG_DIR / "kulturdaten.txt").write_text("\n".join(report), encoding="utf-8")
            except OSError:
                pass
        return []
