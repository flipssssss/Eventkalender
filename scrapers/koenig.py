"""König Drag Show -- Google Sites page (text only).

The shows are described in prose, e.g. "König Theater - Graduation show /
5th and 6th September 2026 at Theater im Delphi". We read the rendered text,
extract the date(s), venue and the nearest "… show" title. Category Theater,
genre Queer (forced in genres.py).
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable

from .base import BaseScraper, Event, GERMAN_MONTHS

URL = "https://www.konigdragshow.com/dragshows"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en;q=0.9,de;q=0.8",
}

_EN_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}
_EN_ABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11,
            "dec": 12}
# Englisch (voll + abgekuerzt) UND deutsch -- die Seite wechselt die Sprache.
MONTHS = {**_EN_MONTHS, **_EN_ABBR, **GERMAN_MONTHS}

_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))
# "5th and 6th September 2026" / "12 October 2026" / "5. und 6. September"
# (zweiter Tag und Jahr optional, Veranstaltungsort optional).
DATE_RE = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\.?(?:\s*(?:and|und|&|,|-|–|to|bis|\+)\s*"
    r"(\d{1,2})(?:st|nd|rd|th)?\.?)?\s+"
    r"(" + _MONTH_ALT + r")\.?(?:\s+(\d{4}))?"
    r"(?:\s+(?:at|im|in der|in)\s+([A-ZÄÖÜ][\wäöüß.'’\-]+"
    r"(?:\s+(?:(?:im|am|an|der|den|de|of|the|zur|zum)\b"
    r"|[A-ZÄÖÜ][\wäöüß.'’\-]+))"
    r"{0,3}))?", re.IGNORECASE)
# Monat zuerst: "September 5, 2026" / "Sept 5th & 6th 2026".
MONTH_FIRST_RE = re.compile(
    r"\b(" + _MONTH_ALT + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?"
    r"(?:\s*(?:and|und|&|,|-|–|to|bis|\+)\s*(\d{1,2})(?:st|nd|rd|th)?\b(?!\d))?"
    r"(?:,?\s+(\d{4}))?", re.IGNORECASE)
# Rein numerisch: "05.09.2026", "5.9.", "2026-09-05".
NUM_DATE_RE = re.compile(
    r"\b(?:(\d{4})-(\d{1,2})-(\d{1,2})|(\d{1,2})\.(\d{1,2})\.(\d{4})?)")
SHOW_RE = re.compile(r"([A-ZÄÖÜ][\wäöüß'&./ \-]{2,55}?[Ss]how)\b")


def _infer_year(month: int, day: int) -> int:
    today = _dt.date.today()
    try:
        cand = _dt.date(today.year, month, day)
    except ValueError:
        return today.year
    return today.year + 1 if (today - cand).days > 60 else today.year


class KoenigScraper(BaseScraper):
    name = "König Drag Show"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(URL, headers=BROWSER).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        # Google Sites keeps the visible text (incl. show dates) inside quoted
        # JS string literals, not in the rendered DOM -- so read those.
        parts = []
        for s in re.findall(r'"((?:[^"\\]|\\.){8,})"', html):
            s = re.sub(r"\\u([0-9a-fA-F]{4})",
                       lambda m: chr(int(m.group(1), 16)), s)
            s = s.replace("\\/", "/").replace("\\n", " ").replace('\\"', '"')
            if re.search(r"[A-Za-zÄÖÜ]", s) and "function" not in s:
                parts.append(s.strip())
        text = re.sub(r"\s+", " ", " ".join(parts))

        shows = [(m.start(), m.group(1).strip()) for m in SHOW_RE.finditer(text)]
        events: list[Event] = []
        seen: set[str] = set()
        for pos, days, month, year, venue in self._dates(text):
            title = next((t for p, t in reversed(shows) if p < pos),
                         "König Drag Show")

            for day in days:
                try:
                    start = _dt.datetime(year, month, day)
                except ValueError:
                    continue
                key = f"{title.lower()}|{start.date()}"
                if key in seen:
                    continue
                seen.add(key)
                events.append(Event(
                    title=title[:140],
                    start=start,
                    source_url=URL,
                    source_name=self.name,
                    location=venue,
                    address=f"{venue}, Berlin" if venue else None,
                    time_known=False,
                    tags=["Theater"],
                ))

        diag = ""
        if not events:
            ctx = []
            for kw in ("September", "October", "November", "Delphi", "Theater",
                       "2026", "Tickets"):
                i = text.find(kw)
                if i >= 0:
                    ctx.append(f"[{kw}@{i}] …{text[max(0, i-40):i+60]}…")
            dates = [m.group(0) for m in DATE_RE.finditer(text)][:8]
            nums = [m.group(0) for m in NUM_DATE_RE.finditer(text)][:8]
            diag = (f"len(text)={len(text)} | DATE-Treffer={dates} | "
                    f"NUM-Treffer={nums}\n"
                    + "\n".join(ctx) + "\n"
                    + "\nTEXTPROBE (erste 3000 Zeichen), damit das Format "
                      "erkennbar ist:\n" + text[:3000] + "\n")
        self._dump(f"Events: {len(events)} | Shows erkannt: {len(shows)}\n{diag}" +
                   "\n".join(f"  {e.start.date()} | {e.title} @ {e.location}"
                             for e in events[:20]))
        return events

    @staticmethod
    def _dates(text: str):
        """All dates in ``text`` as (position, [days], month, year, venue).

        Reads the prose form ("5th and 6th September 2026 at Theater im
        Delphi") first and falls back to numeric dates, so a change of wording
        or language on the page does not silently zero the source out.
        """
        out = []
        covered: list[tuple[int, int]] = []
        for m in DATE_RE.finditer(text):
            month = MONTHS.get(m.group(3).lower().rstrip("."))
            if not month:
                continue
            days = [int(m.group(1))]
            if m.group(2):
                days.append(int(m.group(2)))
            year = int(m.group(4)) if m.group(4) else _infer_year(month, days[0])
            venue = (m.group(5) or "").strip(" .,") or None
            out.append((m.start(), days, month, year, venue))
            covered.append((m.start(), m.end()))
        for m in MONTH_FIRST_RE.finditer(text):
            if any(a <= m.start() < b for a, b in covered):
                continue
            month = MONTHS.get(m.group(1).lower().rstrip("."))
            if not month:
                continue
            days = [int(m.group(2))]
            if m.group(3):
                days.append(int(m.group(3)))
            year = int(m.group(4)) if m.group(4) else _infer_year(month, days[0])
            out.append((m.start(), days, month, year, None))
            covered.append((m.start(), m.end()))
        for m in NUM_DATE_RE.finditer(text):
            if any(a <= m.start() < b for a, b in covered):
                continue  # schon von der Prosa-Form erfasst
            if m.group(1):           # 2026-09-05
                year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
            else:                    # 05.09.2026 / 5.9.
                day, month = int(m.group(4)), int(m.group(5))
                year = int(m.group(6)) if m.group(6) else _infer_year(month, day)
            if not 1 <= month <= 12:
                continue
            out.append((m.start(), [day], month, year, None))
        out.sort(key=lambda t: t[0])
        return out

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "koenig.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
