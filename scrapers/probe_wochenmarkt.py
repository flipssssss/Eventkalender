"""Diagnose: warum liefert /biomarkt/ keine Events? Teaser-URL ↔ GeoJSON-Match
und die <dl>-Labels der Detailseiten prüfen. Keine Events.
"""

from __future__ import annotations

import json
import pathlib
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

BASE = "https://www.berlin.de"
PAGE = "https://www.berlin.de/special/shopping/biomarkt/"
GEO = "https://www.berlin.de/special/shopping/biomarkt/rubric.geojson"
DEBUG = (pathlib.Path(__file__).resolve().parents[1]
         / "docs" / "data" / "_debug" / "probe-wochenmarkt.txt")


class ProbeWochenmarktScraper(BaseScraper):
    name = "Probe Wochenmarkt"

    def fetch_events(self) -> Iterable[Event]:
        out: list[str] = []
        geo_urls = set()
        try:
            data = json.loads(self.get(GEO).text)
            for f in data.get("features", []):
                u = (f.get("properties") or {}).get("url")
                if u:
                    geo_urls.add(u)
            out.append(f"GeoJSON-URLs: {len(geo_urls)}")
            out.append("Beispiel: " + (next(iter(geo_urls)) if geo_urls else "-"))
        except Exception as exc:  # noqa: BLE001
            out.append(f"GEO FEHLER: {exc}")

        try:
            soup = BeautifulSoup(self.get(PAGE).text, "html.parser")
        except Exception as exc:  # noqa: BLE001
            out.append(f"PAGE FEHLER: {exc}")
            self._dump(out)
            return []

        arts = soup.select("article.modul-teaser")
        out.append(f"\nTeaser: {len(arts)}")
        first_detail = None
        for art in arts:
            a = art.select_one("h3 a, .title a")
            if not a:
                continue
            url = urljoin(BASE, a.get("href", ""))
            inn = url in geo_urls
            out.append(f"  match={inn} | {a.get_text(' ', strip=True)[:30]} | {url}")
            if first_detail is None:
                first_detail = url

        if first_detail:
            out.append(f"\n--- Detailseite {first_detail} ---")
            try:
                ds = BeautifulSoup(self.get(first_detail).text, "html.parser")
                for dl in ds.select("dl"):
                    for dt, dd in zip(dl.find_all("dt"), dl.find_all("dd")):
                        out.append(f"  {dt.get_text(' ', strip=True)} :: "
                                   f"{dd.get_text(' ', strip=True)}")
            except Exception as exc:  # noqa: BLE001
                out.append(f"DETAIL FEHLER: {exc}")

        self._dump(out)
        return []

    def _dump(self, lines):
        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass
