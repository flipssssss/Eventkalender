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


def _extract_swaggerdoc(js: str) -> dict:
    """Pull the inline swaggerDoc JSON object out of swagger-ui-init.js."""
    marker = '"swaggerDoc":'
    start = js.index(marker) + len(marker)
    while js[start] != "{":
        start += 1
    depth, i = 0, start
    while i < len(js):
        if js[i] == "{":
            depth += 1
        elif js[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(js[start:i + 1])
        i += 1
    return {}

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

        # 2) Filter-Parameter testen (400 = unbekannt, 200 = unterstützt).
        report.append("=== Query-Tests /api/events ===")
        for q in [
            "?startDate=2026-06-16&endDate=2026-06-20",
            "?pageSize=200",
            "?category=Concerts",
            "?tags=attraction.category.Concerts",
            "?borough=Mitte",
            "?origin=bezirkskalender",
            "?searchterm=jazz",
            "?sort=schedule.startDate",
            "?attractionId=A_KPJGGWYZL5EK",
        ]:
            try:
                r = get("/api/events" + q)
                snip = r.text[:160].replace("\n", " ")
                report.append(f"{q} -> {r.status_code}: {snip}")
            except Exception as exc:  # noqa: BLE001
                report.append(f"{q} -> FEHLER {exc}")
        report.append("")

        # 3) Welche Kategorien (tags) und Herkünfte (origins) gibt es?
        report.append("=== Verteilung (Stichprobe 200 Attraktionen) ===")
        try:
            ats = get("/api/attractions?pageSize=200").json()["data"]["attractions"]
            cats, origins = {}, {}
            for a in ats:
                for t in a.get("tags", []):
                    cats[t] = cats.get(t, 0) + 1
                o = (a.get("metadata") or {}).get("origin", "?")
                origins[o] = origins.get(o, 0) + 1
            report.append("Kategorien: " + json.dumps(
                dict(sorted(cats.items(), key=lambda x: -x[1])), ensure_ascii=False))
            report.append("Origins: " + json.dumps(origins, ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            report.append(f"Verteilung FEHLER {exc}")

        # 4) Vollständige OpenAPI-Pfade aus der Swagger-UI extrahieren.
        report.append("\n=== OpenAPI-Pfade ===")
        try:
            js = get("/api/docs/swagger-ui-init.js").text
            spec = _extract_swaggerdoc(js)
            paths = spec.get("paths", {})
            for p in sorted(paths):
                methods = ",".join(paths[p].keys())
                report.append(f"  {p}  [{methods}]")
            # Query-Parameter von GET /api/events.
            ev = paths.get("/events") or paths.get("/api/events") or {}
            params = (ev.get("get") or {}).get("parameters", [])
            report.append("\nGET events Parameter: " + json.dumps(
                [pp.get("name") for pp in params], ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            report.append(f"Spec FEHLER {exc}")

        if self.write_debug:
            try:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                (DEBUG_DIR / "kulturdaten.txt").write_text("\n".join(report), encoding="utf-8")
            except OSError:
                pass
        return []
