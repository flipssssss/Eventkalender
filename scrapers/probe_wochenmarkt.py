"""Einmal-Probe: dertour-Streetfood-.ics (aktuell? RRULE?) + berlin.de Öko-
Wochenmärkte (/biomarkt/) als mögliche Wochenmarkt-Quelle. Keine Events.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

ICS = ("https://www.dertour.de/static/berliner-wochenmaerkte-map/"
       "files/Berliner_Streetfood-Kalender.ics")
BIO = "https://www.berlin.de/special/shopping/biomarkt/"
BIO_GEO = "https://www.berlin.de/special/shopping/biomarkt/rubric.geojson"
DEBUG = (pathlib.Path(__file__).resolve().parents[1]
         / "docs" / "data" / "_debug" / "probe-wochenmarkt.txt")


class ProbeWochenmarktScraper(BaseScraper):
    name = "Probe Wochenmarkt"

    def fetch_events(self) -> Iterable[Event]:
        out: list[str] = []

        out.append(f"===== dertour .ics {ICS} =====")
        try:
            txt = self.get(ICS).text
            vevents = txt.count("BEGIN:VEVENT")
            dtstarts = re.findall(r"DTSTART[^:]*:(\d{8})", txt)
            years = sorted({d[:4] for d in dtstarts})
            out.append(f"VEVENTs: {vevents} | RRULE: {'RRULE' in txt}")
            out.append(f"Jahre der Termine: {years}")
            out.append("Beispiel-SUMMARYs: " + ", ".join(
                re.findall(r"SUMMARY:(.+)", txt)[:6]))
        except Exception as exc:  # noqa: BLE001
            out.append(f"FEHLER: {exc}")

        out.append(f"\n===== berlin.de /biomarkt/ =====")
        try:
            s = BeautifulSoup(self.get(BIO).text, "html.parser")
            teasers = s.select("article.modul-teaser")
            out.append(f"teaser: {len(teasers)}")
            for art in teasers[:8]:
                a = art.select_one("h3 a, .title a")
                meta = art.select_one(".teaser__meta, .text--meta")
                out.append(f"  - {a.get_text(' ', strip=True) if a else '?'} || "
                           f"{meta.get_text(' ', strip=True) if meta else '(kein Datum)'}")
        except Exception as exc:  # noqa: BLE001
            out.append(f"FEHLER: {exc}")
        try:
            n = len(json.loads(self.get(BIO_GEO).text).get("features", []))
            out.append(f"biomarkt rubric.geojson features: {n}")
        except Exception as exc:  # noqa: BLE001
            out.append(f"biomarkt geojson: FEHLER {exc}")

        self._dump(out)
        return []

    def _dump(self, lines):
        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass
