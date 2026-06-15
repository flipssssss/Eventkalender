"""Silverfuture (queere Bar, Neukölln) -- Jimdo-Seite.

Die Events stehen als freier Text mit Emoji-Struktur im HTML, z. B.:

    Show Theme: LADY GAGA
    SilverFuture | Weserstraße 206, Neukölln 12047
    01.06.2026
    Show Starts at 19:30 …
    Free Entry!
    <Beschreibung>

Wir hängen die Events an den Datumsangaben (TT.MM.JJJJ) auf und ziehen
Titel/Zeit/Beschreibung aus dem umgebenden Text.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event, parse_datetime

URL = "https://www.silverfuture.net/events-1/"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

DATE_RE = re.compile(r"(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})")
THEME_RE = re.compile(r"(?:Show\s*)?Theme\s*:\s*(.+)", re.IGNORECASE)


class SilverfutureScraper(BaseScraper):
    name = "Silverfuture"

    def __init__(self, url: str = URL, write_debug: bool = True):
        self.url = url
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        html = self.get(self.url, headers=BROWSER).text
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style", "header", "footer", "nav"]):
            t.decompose()
        text = re.sub(r"[ \t]+", " ", soup.get_text("\n"))
        text = re.sub(r"\n\s*\n+", "\n", text)

        events: list[Event] = []
        seen: set[str] = set()
        for m in DATE_RE.finditer(text):
            day, mon, year = m.groups()
            before = text[max(0, m.start() - 500):m.start()]
            after = text[m.end():m.end() + 700]

            # Title: nearest "Theme: X" before the date, else first line after.
            themes = THEME_RE.findall(before)
            if themes:
                title = themes[-1].strip(" .!❤️🧡💛💚💙✨‼️")
            else:
                lines = [ln.strip(" .!❤️🧡💛💚💙✨‼️|") for ln in after.split("\n")]
                title = next((ln for ln in lines if len(ln) > 3), "Silverfuture")
            if not title:
                continue

            # Time: "Starts at HH:MM" or first HH:MM after the date.
            tmatch = TIME_RE.search(after)
            hh, mm = (tmatch.groups() if tmatch else ("20", "00"))
            start = parse_datetime(f"{year}-{int(mon):02d}-{int(day):02d} {hh}:{mm}")
            if not start:
                continue

            key = f"{title.lower()}|{start.date()}"
            if key in seen:
                continue
            seen.add(key)

            # Short description: the longest line shortly after the date.
            desc_lines = [ln.strip() for ln in after.split("\n") if len(ln.strip()) > 30]
            desc = desc_lines[0][:400] if desc_lines else None

            events.append(Event(
                title=title[:120],
                start=start,
                source_url=self.url,
                source_name=self.name,
                location="SilverFuture, Weserstraße 206, Neukölln",
                description=desc,
                tags=["Party"],
            ))

        if self.write_debug:
            try:
                DEBUG_DIR.mkdir(parents=True, exist_ok=True)
                sample = "\n".join(f"{e.start} | {e.title}" for e in events[:15])
                (DEBUG_DIR / "silverfuture.txt").write_text(
                    f"Events geparst: {len(events)}\n{sample}", encoding="utf-8")
            except OSError:
                pass
        return events
