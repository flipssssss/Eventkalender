"""Einmal-Probe: Struktur der dertour.de Berliner-Wochenmärkte-Map dumpen
(JSON-LD, eingebettete JSON/GeoJSON-Daten, Skript-/Body-Hinweise).
Liefert selbst keine Events.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URL = "https://www.dertour.de/static/berliner-wochenmaerkte-map/"
DEBUG = (pathlib.Path(__file__).resolve().parents[1]
         / "docs" / "data" / "_debug" / "probe-wochenmarkt.txt")


class ProbeWochenmarktScraper(BaseScraper):
    name = "Probe Wochenmarkt"

    def fetch_events(self) -> Iterable[Event]:
        out: list[str] = [f"URL {URL}"]
        try:
            html = self.get(URL).text
        except Exception as exc:  # noqa: BLE001
            out.append(f"FEHLER: {exc}")
            self._dump(out)
            return []
        out.append(f"HTML-Länge: {len(html)}")
        soup = BeautifulSoup(html, "html.parser")

        # 1) JSON-LD
        lds = soup.find_all("script", type="application/ld+json")
        out.append(f"JSON-LD-Blöcke: {len(lds)}")
        for s in lds[:2]:
            out.append((s.string or s.get_text() or "")[:600])

        # 2) Verweise auf .json/.geojson
        refs = set(re.findall(r'["\'(]([^"\'()]+\.(?:geo)?json[^"\']*)', html, re.I))
        out.append("\nJSON/GeoJSON-Verweise:")
        out.extend("  " + r for r in list(refs)[:20])

        # 3) Inline-Skripte mit Markt-Daten (lat/lng/Uhr/Name)
        out.append("\nInline-Skripte mit Daten:")
        for sc in soup.find_all("script"):
            t = sc.string or sc.get_text() or ""
            if re.search(r'(lat|lng|coordinates|"name"|markt|öffnungs|uhr)', t, re.I):
                snippet = t.strip()
                out.append(f"--- Skript ({len(snippet)} Z.) ---")
                out.append(snippet[:1600])
                break

        # 4) Body-Hinweise (Listen/Tabellen mit Markt-Einträgen)
        for tag in soup.select("script, style"):
            tag.decompose()
        body_txt = soup.get_text(" ", strip=True)
        out.append("\nBody-Text (Anfang):")
        out.append(body_txt[:800])

        self._dump(out)
        return []

    def _dump(self, lines):
        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass
