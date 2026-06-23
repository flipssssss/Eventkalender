"""Einmal-Probe: dertour-Wochenmärkte (iCal-Link, Markt-Skripte) + ob berlin.de
eine Wochenmärkte-Seite mit rubric.geojson hat. Liefert selbst keine Events.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

DERTOUR = "https://www.dertour.de/static/berliner-wochenmaerkte-map/"
BERLIN_CANDIDATES = [
    "https://www.berlin.de/special/shopping/wochenmaerkte/",
    "https://www.berlin.de/special/shopping/wochenmaerkte/rubric.geojson",
    "https://www.berlin.de/special/shopping/wochenmaerkte/bezirk/",
]
DEBUG = (pathlib.Path(__file__).resolve().parents[1]
         / "docs" / "data" / "_debug" / "probe-wochenmarkt.txt")


class ProbeWochenmarktScraper(BaseScraper):
    name = "Probe Wochenmarkt"

    def fetch_events(self) -> Iterable[Event]:
        out: list[str] = []

        # 1) dertour: iCal/PDF/Calendar-Links + Markt-Daten-Skripte
        out.append(f"===== DERTOUR {DERTOUR} =====")
        try:
            soup = BeautifulSoup(self.get(DERTOUR).text, "html.parser")
            cal = [(a.get_text(" ", strip=True), a["href"])
                   for a in soup.find_all("a", href=True)
                   if re.search(r"ics|ical|calendar|\.pdf|kalender", a["href"], re.I)
                   or re.search(r"ical|pdf|kalender", a.get_text(), re.I)]
            out.append("Kalender-/PDF-Links:")
            out.extend(f"  {t} -> {h}" for t, h in cal[:15])
            for sc in soup.find_all("script"):
                t = sc.string or sc.get_text() or ""
                if re.search(r'(lat["\']?\s*[:=]|coordinates|geometry|markerData|'
                             r'markets|standorte)', t, re.I):
                    out.append(f"--- Markt-Skript ({len(t)} Z.) ---")
                    out.append(t.strip()[:1500])
                    break
            else:
                out.append("(kein offensichtliches Markt-Daten-Skript)")
        except Exception as exc:  # noqa: BLE001
            out.append(f"FEHLER: {exc}")

        # 2) berlin.de Wochenmärkte?
        out.append("\n===== BERLIN.DE Wochenmärkte? =====")
        for url in BERLIN_CANDIDATES:
            try:
                txt = self.get(url).text
            except Exception as exc:  # noqa: BLE001
                out.append(f"{url} -> FEHLER {exc}")
                continue
            if url.endswith(".geojson"):
                try:
                    n = len(json.loads(txt).get("features", []))
                    out.append(f"{url} -> GeoJSON OK, features={n}")
                except Exception:  # noqa: BLE001
                    out.append(f"{url} -> kein GeoJSON ({len(txt)} Z.)")
            else:
                s = BeautifulSoup(txt, "html.parser")
                teasers = s.select("article.modul-teaser")
                title = s.find("title")
                out.append(f"{url} -> {len(txt)} Z., title="
                           f"{title.get_text(strip=True) if title else '?'}, "
                           f"teaser={len(teasers)}")

        self._dump(out)
        return []

    def _dump(self, lines):
        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass
