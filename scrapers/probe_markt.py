"""Einmal-Probe: berlin.de-Flohmärkte. Dumpt die Teaser (Titel/Datum/Link) und
den rubric.geojson-Feed, damit ein richtiger Ausleser gebaut werden kann.
Liefert selbst keine Events.
"""

from __future__ import annotations

import json
import pathlib
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

PAGES = [
    "https://www.berlin.de/special/shopping/flohmaerkte/",
    "https://www.berlin.de/special/shopping/flohmaerkte/bezirk/",
]
GEOJSON = "https://www.berlin.de/special/shopping/flohmaerkte/rubric.geojson"
DEBUG = (pathlib.Path(__file__).resolve().parents[1]
         / "docs" / "data" / "_debug" / "probe-markt.txt")


class ProbeMarktScraper(BaseScraper):
    name = "Probe Markt"

    def fetch_events(self) -> Iterable[Event]:
        out: list[str] = []
        for url in PAGES:
            out.append(f"\n===== TEASER {url} =====")
            try:
                soup = BeautifulSoup(self.get(url).text, "html.parser")
            except Exception as exc:  # noqa: BLE001
                out.append(f"FEHLER: {exc}")
                continue
            for art in soup.select("article.modul-teaser"):
                h = art.select_one("h3.title a, h3 a, .title a")
                meta = art.select_one(".teaser__meta, .text--meta")
                title = h.get_text(" ", strip=True) if h else "?"
                href = h.get("href") if h else ""
                m = meta.get_text(" ", strip=True) if meta else "(kein Datum)"
                out.append(f"- {title} || {m} || {href}")

        out.append(f"\n===== GEOJSON {GEOJSON} =====")
        try:
            data = json.loads(self.get(GEOJSON).text)
            feats = data.get("features", [])
            out.append(f"features: {len(feats)}")
            if feats:
                out.append("--- erstes Feature ---")
                out.append(json.dumps(feats[0], ensure_ascii=False, indent=1)[:2500])
                out.append("--- Property-Keys ---")
                out.append(", ".join((feats[0].get("properties") or {}).keys()))
        except Exception as exc:  # noqa: BLE001
            out.append(f"GEOJSON FEHLER: {exc}")

        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []
