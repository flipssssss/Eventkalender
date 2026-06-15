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

import datetime as _dt
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

# Events are headed like "Monday, 08.06 from 19pm -  Drag Support Line"
# (often without a year), so we anchor on the weekday + DD.MM[.YYYY] + title.
WEEKDAYS = (
    "Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|"
    "Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag"
)
HEADING_RE = re.compile(
    rf"(?:{WEEKDAYS})\s*,?\s*(\d{{1,2}})\.(\d{{1,2}})\.?(\d{{4}})?"
    r"[^\n-]*?-\s*([^\n]+)",
    re.IGNORECASE,
)
DATE_RE = re.compile(r"(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})")
# 12h times with am/pm (e.g. "7:30pm", "7pm") take priority so they aren't
# read as 07:30; otherwise a plain 24h "19:30".
TIME_AMPM_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])m\b", re.IGNORECASE)
TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")
EMOJI_STRIP = " .!|❤️🧡💛💚💙💖✨‼️⭐️🗓️📍⏰🎟️🏳️‍🌈🏳️‍⚧️"


def _parse_time(window: str) -> tuple[str, str]:
    """Best-effort show time from the text after a heading -> (HH, MM)."""
    m = TIME_AMPM_RE.search(window)
    if m:
        hh = int(m.group(1)) % 12
        if m.group(3).lower() == "p":
            hh += 12
        return f"{hh:02d}", m.group(2) or "00"
    m = TIME_RE.search(window)
    if m:
        return m.group(1), m.group(2)
    return "20", "00"


def _infer_year(day: int, mon: int) -> int:
    """Guess the year for a DD.MM date: this year, unless it's long past."""
    today = _dt.date.today()
    try:
        cand = _dt.date(today.year, mon, day)
    except ValueError:
        return today.year
    # Recently past (e.g. last week) stays this year -> gets filtered out as
    # past; only a date many months back rolls over to next year.
    return today.year + 1 if (today - cand).days > 60 else today.year


class SilverfutureScraper(BaseScraper):
    name = "Silverfuture"

    def __init__(self, url: str = URL, write_debug: bool = True):
        self.url = url
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        html = self.get(self.url, headers=BROWSER).text
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style", "header", "footer", "nav", "title"]):
            t.decompose()
        text = re.sub(r"[ \t]+", " ", soup.get_text("\n"))
        text = re.sub(r"\n\s*\n+", "\n", text)

        events: list[Event] = []
        seen: set[str] = set()
        for m in HEADING_RE.finditer(text):
            day, mon, year, title = m.groups()
            day, mon = int(day), int(mon)
            if not (1 <= mon <= 12 and 1 <= day <= 31):
                continue
            year = int(year) if year else _infer_year(day, mon)

            title = title.strip(EMOJI_STRIP).strip()
            if len(title) < 3:
                continue

            after = text[m.end():m.end() + 700]
            # Time: prefer "7:30pm"/"7pm" (12h) over a bare 24h "19:30".
            hh, mm = _parse_time(after)
            start = parse_datetime(f"{year}-{mon:02d}-{day:02d} {hh}:{mm}")
            if not start:
                continue

            key = f"{title.lower()}|{start.date()}"
            if key in seen:
                continue
            seen.add(key)

            # Short description: the longest line shortly after the heading.
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
                dates = ", ".join(m.group(0) for m in DATE_RE.finditer(text))
                (DEBUG_DIR / "silverfuture.txt").write_text(
                    f"Events geparst: {len(events)}\n{sample}\n\n"
                    f"--- gefundene Datumsangaben ---\n{dates}\n\n"
                    f"--- ROHTEXT (erste 2500 Zeichen) ---\n{text[:2500]}",
                    encoding="utf-8")
            except OSError:
                pass
        return events
