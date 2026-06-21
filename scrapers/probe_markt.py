"""Einmal-Probe: dumpt die HTML-Struktur der berlin.de-Flohmarkt-Seiten, damit
ein richtiger Ausleser gebaut werden kann. Liefert selbst keine Events.
"""

from __future__ import annotations

import pathlib
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URLS = [
    "https://www.berlin.de/special/shopping/flohmaerkte/",
    "https://www.berlin.de/special/shopping/flohmaerkte/bezirk/",
]
DEBUG = (pathlib.Path(__file__).resolve().parents[1]
         / "docs" / "data" / "_debug" / "probe-markt.txt")


class ProbeMarktScraper(BaseScraper):
    name = "Probe Markt"

    def fetch_events(self) -> Iterable[Event]:
        out: list[str] = []
        for url in URLS:
            out.append(f"\n========== {url} ==========")
            try:
                html = self.get(url).text
            except Exception as exc:  # noqa: BLE001
                out.append(f"FEHLER: {exc}")
                continue
            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.select("header, footer, nav, script, style"):
                tag.decompose()
            for sel in [".teaser", ".teaser-item", "article", ".html5-section",
                        ".modul-autoteaser", "table", "table tr", "dl", "dt",
                        "h2", "h3", "h4", ".list--teaser", ".row-fluid",
                        "[class*=flohmarkt]", "[class*=markt]", ".item"]:
                n = len(soup.select(sel))
                if n:
                    out.append(f"{sel}: {n}")
            main = (soup.select_one("#layout-grid__area--maincontent")
                    or soup.select_one("main")
                    or soup.select_one(".column-content")
                    or soup.select_one("#content")
                    or soup.body or soup)
            out.append("--- MAIN (gekürzt) ---")
            out.append(main.prettify()[:3500])
        try:
            DEBUG.parent.mkdir(parents=True, exist_ok=True)
            DEBUG.write_text("\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []
